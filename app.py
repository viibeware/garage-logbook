import os, uuid, sqlite3, hashlib, secrets, csv, io, json, re
from functools import wraps
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, g, Response, send_from_directory)

APP_VERSION = '0.1.7'

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-to-a-random-secret-key-in-production')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads'))
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif','webp'}
ROLES = {'admin','editor','viewer'}
DATABASE = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'garage_logbook.db'))

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(pw, salt=None):
    if not salt: salt = secrets.token_hex(16)
    return f"{salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 260000).hex()}"

def verify_password(pw, stored):
    salt = stored.split('$',1)[0]
    return hash_password(pw, salt) == stored

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password TEXT NOT NULL, display_name TEXT,
            role TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','editor','viewer')),
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL, make TEXT NOT NULL, model TEXT NOT NULL,
            vin TEXT, image TEXT, purchase_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL, title TEXT NOT NULL,
            maintenance_type TEXT NOT NULL CHECK(maintenance_type IN ('Repair','Maintenance','Upgrade','Inspection')),
            service_date TEXT NOT NULL, odometer INTEGER,
            parts_vendor TEXT, cost REAL, notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS maintenance_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maintenance_id INTEGER NOT NULL, filename TEXT NOT NULL,
            original_name TEXT, created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (maintenance_id) REFERENCES maintenance(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            settings TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    ''')
    if conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c'] == 0:
        conn.execute('INSERT INTO users (username,password,display_name,role,must_change_password) VALUES (?,?,?,?,?)',
                     ('admin', hash_password('admin'), 'Administrator', 'admin', 1))
        print("\n  Default admin: admin / admin — change immediately!\n")
    conn.commit()
    # Migration: add must_change_password column if missing
    try:
        cols = [r['name'] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if 'must_change_password' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
            conn.commit()
    except Exception: pass
    # Migration: add Inspection to CHECK constraint
    try:
        tbl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='maintenance'").fetchone()
        if tbl and 'Inspection' not in (tbl['sql'] or ''):
            conn.executescript("""
                PRAGMA foreign_keys=OFF;
                ALTER TABLE maintenance RENAME TO _maint_old;
                CREATE TABLE maintenance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    car_id INTEGER NOT NULL, title TEXT NOT NULL,
                    maintenance_type TEXT NOT NULL CHECK(maintenance_type IN ('Repair','Maintenance','Upgrade','Inspection')),
                    service_date TEXT NOT NULL, odometer INTEGER,
                    parts_vendor TEXT, cost REAL, notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
                );
                INSERT INTO maintenance SELECT * FROM _maint_old;
                DROP TABLE _maint_old;
                PRAGMA foreign_keys=ON;
            """)
            conn.commit()
    except Exception: pass
    conn.close()

def save_upload(file, subfolder):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.',1)[1].lower()
        fn = f"{uuid.uuid4().hex}.{ext}"
        folder = os.path.join(app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(folder, exist_ok=True)
        file.save(os.path.join(folder, fn))
        return fn
    return None

# ── Auth Middleware ─────────────────────────────────────
@app.before_request
def load_user():
    g.user = None
    uid = session.get('user_id')
    if uid:
        conn = get_db()
        u = conn.execute('SELECT id,username,display_name,role,must_change_password FROM users WHERE id=?',(uid,)).fetchone()
        conn.close()
        if u: g.user = dict(u)

def login_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if not g.user:
            if request.path.startswith('/api/'):
                return jsonify({'error':'Authentication required'}), 401
            return redirect(url_for('login_page'))
        return f(*a,**kw)
    return dec

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def dec(*a,**kw):
            if g.user['role'] not in roles:
                return jsonify({'error':'Insufficient permissions'}), 403
            return f(*a,**kw)
        return dec
    return decorator

# ── Pages ──────────────────────────────────────────────
@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/login')
def login_page():
    if g.user: return redirect(url_for('index'))
    return render_template('login.html', version=APP_VERSION)

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=g.user, version=APP_VERSION)

@app.route('/api/version')
def api_version():
    return jsonify({'version': APP_VERSION})

# ── Auth API ───────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    u, p = data.get('username','').strip(), data.get('password','')
    if not u or not p:
        return jsonify({'error':'Username and password are required'}), 400
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=?',(u,)).fetchone()
    conn.close()
    if not user or not verify_password(p, user['password']):
        return jsonify({'error':'Invalid username or password'}), 401
    session.clear()
    session['user_id'] = user['id']
    session.permanent = True
    mcp = 0
    try: mcp = user['must_change_password']
    except: pass
    return jsonify({'id':user['id'],'username':user['username'],
                    'display_name':user['display_name'],'role':user['role'],
                    'must_change_password': bool(mcp)})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success':True})

@app.route('/api/auth/me')
@login_required
def api_me():
    return jsonify(g.user)

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.get_json() or {}
    cur, new = data.get('current_password',''), data.get('new_password','')
    if not cur or not new:
        return jsonify({'error':'Both passwords required'}), 400
    if len(new) < 4:
        return jsonify({'error':'Min 4 characters'}), 400
    conn = get_db()
    u = conn.execute('SELECT password FROM users WHERE id=?',(g.user['id'],)).fetchone()
    if not verify_password(cur, u['password']):
        conn.close()
        return jsonify({'error':'Current password incorrect'}), 401
    conn.execute('UPDATE users SET password=?, must_change_password=0 WHERE id=?',
                 (hash_password(new), g.user['id']))
    conn.commit()
    conn.close()
    return jsonify({'success':True})

# ── Settings API ───────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    conn = get_db()
    row = conn.execute('SELECT settings FROM user_settings WHERE user_id=?',(g.user['id'],)).fetchone()
    conn.close()
    if row:
        return jsonify(json.loads(row['settings']))
    return jsonify({'dashboard_range':'all','show_vehicles':True,'show_records':True,'show_cost':True})

@app.route('/api/settings', methods=['PUT'])
@login_required
def save_settings():
    data = request.get_json() or {}
    conn = get_db()
    s = json.dumps(data)
    existing = conn.execute('SELECT user_id FROM user_settings WHERE user_id=?',(g.user['id'],)).fetchone()
    if existing:
        conn.execute('UPDATE user_settings SET settings=? WHERE user_id=?',(s,g.user['id']))
    else:
        conn.execute('INSERT INTO user_settings (user_id,settings) VALUES (?,?)',(g.user['id'],s))
    conn.commit()
    conn.close()
    return jsonify({'success':True})

# ── User Management (admin) ───────────────────────────
@app.route('/api/users', methods=['GET'])
@role_required('admin')
def get_users():
    conn = get_db()
    users = conn.execute('SELECT id,username,display_name,role,created_at FROM users ORDER BY created_at').fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/users', methods=['POST'])
@role_required('admin')
def create_user():
    data = request.get_json() or {}
    un = data.get('username','').strip().lower()
    pw = data.get('password','')
    dn = data.get('display_name','').strip()
    role = data.get('role','viewer').strip()
    if not un or not pw:
        return jsonify({'error':'Username and password required'}), 400
    if role not in ROLES:
        return jsonify({'error':'Invalid role'}), 400
    if len(pw) < 4:
        return jsonify({'error':'Min 4 chars'}), 400
    conn = get_db()
    if conn.execute('SELECT id FROM users WHERE username=?',(un,)).fetchone():
        conn.close()
        return jsonify({'error':'Username exists'}), 409
    conn.execute('INSERT INTO users (username,password,display_name,role) VALUES (?,?,?,?)',
                 (un, hash_password(pw), dn or un, role))
    conn.commit()
    u = conn.execute('SELECT id,username,display_name,role,created_at FROM users WHERE username=?',(un,)).fetchone()
    conn.close()
    return jsonify(dict(u)), 201

@app.route('/api/users/<int:uid>', methods=['PUT'])
@role_required('admin')
def update_user(uid):
    data = request.get_json() or {}
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    dn = data.get('display_name', user['display_name']).strip()
    role = data.get('role', user['role']).strip()
    npw = data.get('password','').strip()
    if role not in ROLES:
        conn.close()
        return jsonify({'error':'Invalid role'}), 400
    if user['role'] == 'admin' and role != 'admin':
        if conn.execute("SELECT COUNT(*) as c FROM users WHERE role='admin'").fetchone()['c'] <= 1:
            conn.close()
            return jsonify({'error':'Cannot remove last admin'}), 400
    if npw:
        if len(npw) < 4:
            conn.close()
            return jsonify({'error':'Min 4 chars'}), 400
        conn.execute('UPDATE users SET display_name=?,role=?,password=? WHERE id=?',
                     (dn, role, hash_password(npw), uid))
    else:
        conn.execute('UPDATE users SET display_name=?,role=? WHERE id=?', (dn, role, uid))
    conn.commit()
    u = conn.execute('SELECT id,username,display_name,role,created_at FROM users WHERE id=?',(uid,)).fetchone()
    conn.close()
    return jsonify(dict(u))

@app.route('/api/users/<int:uid>', methods=['DELETE'])
@role_required('admin')
def delete_user(uid):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    if uid == g.user['id']:
        conn.close()
        return jsonify({'error':'Cannot delete yourself'}), 400
    if user['role'] == 'admin':
        if conn.execute("SELECT COUNT(*) as c FROM users WHERE role='admin'").fetchone()['c'] <= 1:
            conn.close()
            return jsonify({'error':'Cannot delete last admin'}), 400
    conn.execute('DELETE FROM users WHERE id=?',(uid,))
    conn.commit()
    conn.close()
    return jsonify({'success':True})

# ── Car API ────────────────────────────────────────────
@app.route('/api/cars', methods=['GET'])
@login_required
def get_cars():
    q = request.args.get('q','').strip()
    conn = get_db()
    if q:
        cars = conn.execute("SELECT * FROM cars WHERE year LIKE ? OR make LIKE ? OR model LIKE ? OR vin LIKE ? ORDER BY created_at DESC",
            (f'%{q}%',f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    else:
        cars = conn.execute('SELECT * FROM cars ORDER BY created_at DESC').fetchall()
    result = []
    for car in cars:
        c = dict(car)
        s = conn.execute("SELECT COUNT(*) as count, COALESCE(SUM(cost),0) as total_cost, MAX(odometer) as max_odo FROM maintenance WHERE car_id=?",(c['id'],)).fetchone()
        c['maintenance_count'] = s['count']; c['total_cost'] = s['total_cost']; c['latest_odometer'] = s['max_odo']
        result.append(c)
    conn.close()
    return jsonify(result)

@app.route('/api/cars', methods=['POST'])
@role_required('admin','editor')
def add_car():
    year = request.form.get('year'); make = request.form.get('make','').strip()
    model = request.form.get('model','').strip(); vin = request.form.get('vin','').strip()
    pd = request.form.get('purchase_date','').strip()
    if not year or not make or not model:
        return jsonify({'error':'Year, make, model required'}), 400
    image = save_upload(request.files.get('image'), 'cars') if 'image' in request.files else None
    conn = get_db()
    cur = conn.execute('INSERT INTO cars (year,make,model,vin,image,purchase_date) VALUES (?,?,?,?,?,?)',
                       (int(year), make, model, vin or None, image, pd or None))
    conn.commit()
    car = dict(conn.execute('SELECT * FROM cars WHERE id=?',(cur.lastrowid,)).fetchone())
    conn.close()
    return jsonify(car), 201

@app.route('/api/cars/<int:cid>', methods=['GET'])
@login_required
def get_car(cid):
    conn = get_db()
    car = conn.execute('SELECT * FROM cars WHERE id=?',(cid,)).fetchone()
    conn.close()
    if not car:
        return jsonify({'error':'Not found'}), 404
    return jsonify(dict(car))

@app.route('/api/cars/<int:cid>', methods=['PUT'])
@role_required('admin','editor')
def update_car(cid):
    conn = get_db()
    car = conn.execute('SELECT * FROM cars WHERE id=?',(cid,)).fetchone()
    if not car:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    year = request.form.get('year', car['year']); make = request.form.get('make', car['make']).strip()
    model = request.form.get('model', car['model']).strip(); vin = request.form.get('vin', car['vin'] or '').strip()
    pd = request.form.get('purchase_date', car['purchase_date'] or '').strip()
    image = car['image']
    if 'image' in request.files and request.files['image'].filename:
        if car['image']:
            p = os.path.join(app.config['UPLOAD_FOLDER'], 'cars', car['image'])
            if os.path.exists(p): os.remove(p)
        image = save_upload(request.files['image'], 'cars')
    conn.execute('UPDATE cars SET year=?,make=?,model=?,vin=?,image=?,purchase_date=? WHERE id=?',
                 (int(year), make, model, vin or None, image, pd or None, cid))
    conn.commit()
    updated = dict(conn.execute('SELECT * FROM cars WHERE id=?',(cid,)).fetchone())
    conn.close()
    return jsonify(updated)

@app.route('/api/cars/<int:cid>', methods=['DELETE'])
@role_required('admin','editor')
def delete_car(cid):
    conn = get_db()
    car = conn.execute('SELECT * FROM cars WHERE id=?',(cid,)).fetchone()
    if not car:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    if car['image']:
        p = os.path.join(app.config['UPLOAD_FOLDER'], 'cars', car['image'])
        if os.path.exists(p): os.remove(p)
    for img in conn.execute("SELECT mi.filename FROM maintenance_images mi JOIN maintenance m ON mi.maintenance_id=m.id WHERE m.car_id=?",(cid,)).fetchall():
        p = os.path.join(app.config['UPLOAD_FOLDER'], 'maintenance', img['filename'])
        if os.path.exists(p): os.remove(p)
    conn.execute('DELETE FROM cars WHERE id=?',(cid,))
    conn.commit()
    conn.close()
    return jsonify({'success':True})

# ── Maintenance API ────────────────────────────────────
@app.route('/api/cars/<int:cid>/maintenance', methods=['GET'])
@login_required
def get_maintenance(cid):
    q = request.args.get('q','').strip()
    sort = request.args.get('sort','date_desc')
    order = {'date_asc':'service_date ASC','cost_desc':'cost DESC','cost_asc':'cost ASC','odo_desc':'odometer DESC'}.get(sort,'service_date DESC')
    conn = get_db()
    if q:
        entries = conn.execute(f"SELECT * FROM maintenance WHERE car_id=? AND (title LIKE ? OR maintenance_type LIKE ? OR parts_vendor LIKE ? OR notes LIKE ?) ORDER BY {order}",
            (cid,f'%{q}%',f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    else:
        entries = conn.execute(f'SELECT * FROM maintenance WHERE car_id=? ORDER BY {order}',(cid,)).fetchall()
    result = []
    for e in entries:
        d = dict(e)
        d['images'] = [dict(i) for i in conn.execute('SELECT * FROM maintenance_images WHERE maintenance_id=? ORDER BY created_at',(d['id'],)).fetchall()]
        result.append(d)
    conn.close()
    return jsonify(result)

@app.route('/api/cars/<int:cid>/maintenance', methods=['POST'])
@role_required('admin','editor')
def add_maintenance(cid):
    conn = get_db()
    if not conn.execute('SELECT id FROM cars WHERE id=?',(cid,)).fetchone():
        conn.close()
        return jsonify({'error':'Car not found'}), 404
    t = request.form.get('title','').strip(); mt = request.form.get('maintenance_type','').strip()
    sd = request.form.get('service_date','').strip(); odo = request.form.get('odometer','').strip()
    v = request.form.get('parts_vendor','').strip(); c = request.form.get('cost','').strip()
    n = request.form.get('notes','').strip()
    if not t or not mt or not sd:
        conn.close()
        return jsonify({'error':'Title, type, date required'}), 400
    if mt not in ('Repair','Maintenance','Upgrade','Inspection'):
        conn.close()
        return jsonify({'error':'Invalid type'}), 400
    cur = conn.execute('INSERT INTO maintenance (car_id,title,maintenance_type,service_date,odometer,parts_vendor,cost,notes) VALUES (?,?,?,?,?,?,?,?)',
        (cid, t, mt, sd, int(odo) if odo else None, v or None, float(c) if c else None, n or None))
    mid = cur.lastrowid
    for f in request.files.getlist('gallery'):
        fn = save_upload(f, 'maintenance')
        if fn: conn.execute('INSERT INTO maintenance_images (maintenance_id,filename,original_name) VALUES (?,?,?)',(mid,fn,f.filename))
    conn.commit()
    entry = dict(conn.execute('SELECT * FROM maintenance WHERE id=?',(mid,)).fetchone())
    entry['images'] = [dict(i) for i in conn.execute('SELECT * FROM maintenance_images WHERE maintenance_id=?',(mid,)).fetchall()]
    conn.close()
    return jsonify(entry), 201

@app.route('/api/maintenance/<int:mid>', methods=['PUT'])
@role_required('admin','editor')
def update_maintenance(mid):
    conn = get_db()
    entry = conn.execute('SELECT * FROM maintenance WHERE id=?',(mid,)).fetchone()
    if not entry:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    t = request.form.get('title', entry['title']).strip()
    mt = request.form.get('maintenance_type', entry['maintenance_type']).strip()
    sd = request.form.get('service_date', entry['service_date']).strip()
    odo = request.form.get('odometer','').strip()
    v = request.form.get('parts_vendor', entry['parts_vendor'] or '').strip()
    c = request.form.get('cost','').strip()
    n = request.form.get('notes', entry['notes'] or '').strip()
    if not t or not mt or not sd:
        conn.close()
        return jsonify({'error':'Title, type, date required'}), 400
    if mt not in ('Repair','Maintenance','Upgrade','Inspection'):
        conn.close()
        return jsonify({'error':'Invalid type'}), 400
    odo_val = int(odo) if odo else entry['odometer']
    cost_val = float(c) if c else entry['cost']
    conn.execute('UPDATE maintenance SET title=?,maintenance_type=?,service_date=?,odometer=?,parts_vendor=?,cost=?,notes=? WHERE id=?',
        (t, mt, sd, odo_val, v or None, cost_val, n or None, mid))
    for f in request.files.getlist('gallery'):
        fn = save_upload(f, 'maintenance')
        if fn: conn.execute('INSERT INTO maintenance_images (maintenance_id,filename,original_name) VALUES (?,?,?)',(mid,fn,f.filename))
    conn.commit()
    updated = dict(conn.execute('SELECT * FROM maintenance WHERE id=?',(mid,)).fetchone())
    updated['images'] = [dict(i) for i in conn.execute('SELECT * FROM maintenance_images WHERE maintenance_id=?',(mid,)).fetchall()]
    conn.close()
    return jsonify(updated)

@app.route('/api/maintenance/<int:mid>', methods=['DELETE'])
@role_required('admin','editor')
def delete_maintenance(mid):
    conn = get_db()
    entry = conn.execute('SELECT * FROM maintenance WHERE id=?',(mid,)).fetchone()
    if not entry:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    for img in conn.execute('SELECT filename FROM maintenance_images WHERE maintenance_id=?',(mid,)).fetchall():
        p = os.path.join(app.config['UPLOAD_FOLDER'], 'maintenance', img['filename'])
        if os.path.exists(p): os.remove(p)
    conn.execute('DELETE FROM maintenance WHERE id=?',(mid,))
    conn.commit()
    conn.close()
    return jsonify({'success':True})

@app.route('/api/maintenance/<int:mid>/duplicate', methods=['POST'])
@role_required('admin','editor')
def duplicate_maintenance(mid):
    conn = get_db()
    entry = conn.execute('SELECT * FROM maintenance WHERE id=?',(mid,)).fetchone()
    if not entry:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    cur = conn.execute(
        'INSERT INTO maintenance (car_id,title,maintenance_type,service_date,odometer,parts_vendor,cost,notes) VALUES (?,?,?,?,?,?,?,?)',
        (entry['car_id'], entry['title']+' (copy)', entry['maintenance_type'], entry['service_date'],
         entry['odometer'], entry['parts_vendor'], entry['cost'], entry['notes']))
    conn.commit()
    new_entry = dict(conn.execute('SELECT * FROM maintenance WHERE id=?',(cur.lastrowid,)).fetchone())
    new_entry['images'] = []
    conn.close()
    return jsonify(new_entry), 201

@app.route('/api/maintenance/<int:mid>/images', methods=['POST'])
@role_required('admin','editor')
def add_maintenance_images(mid):
    conn = get_db()
    if not conn.execute('SELECT id FROM maintenance WHERE id=?',(mid,)).fetchone():
        conn.close()
        return jsonify({'error':'Not found'}), 404
    added = []
    for f in request.files.getlist('gallery'):
        fn = save_upload(f, 'maintenance')
        if fn:
            conn.execute('INSERT INTO maintenance_images (maintenance_id,filename,original_name) VALUES (?,?,?)',(mid,fn,f.filename))
            added.append({'filename':fn,'original_name':f.filename})
    conn.commit()
    conn.close()
    return jsonify(added), 201

@app.route('/api/maintenance/images/<int:iid>', methods=['DELETE'])
@role_required('admin','editor')
def delete_maintenance_image(iid):
    conn = get_db()
    img = conn.execute('SELECT * FROM maintenance_images WHERE id=?',(iid,)).fetchone()
    if not img:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    p = os.path.join(app.config['UPLOAD_FOLDER'], 'maintenance', img['filename'])
    if os.path.exists(p): os.remove(p)
    conn.execute('DELETE FROM maintenance_images WHERE id=?',(iid,))
    conn.commit()
    conn.close()
    return jsonify({'success':True})

# ── CSV Export ─────────────────────────────────────────
@app.route('/api/cars/<int:cid>/export', methods=['GET'])
@login_required
def export_csv(cid):
    conn = get_db()
    car = conn.execute('SELECT * FROM cars WHERE id=?',(cid,)).fetchone()
    if not car:
        conn.close()
        return jsonify({'error':'Not found'}), 404
    entries = conn.execute('SELECT * FROM maintenance WHERE car_id=? ORDER BY service_date DESC',(cid,)).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title','Type','Service Date','Odometer','Vendor','Cost','Notes'])
    for e in entries:
        writer.writerow([e['title'],e['maintenance_type'],e['service_date'],e['odometer'] or '',e['parts_vendor'] or '',e['cost'] or '',e['notes'] or ''])
    fname = f"{car['year']}_{car['make']}_{car['model']}_maintenance.csv".replace(' ','_')
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment; filename="{fname}"'})

# ── CSV Import (admin) ────────────────────────────────
@app.route('/api/import/preview', methods=['POST'])
@role_required('admin')
def csv_preview():
    if 'file' not in request.files:
        return jsonify({'error':'No CSV'}), 400
    file = request.files['file']
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error':'Must be .csv'}), 400
    mapping_raw = request.form.get('mapping','{}')
    car_id = request.form.get('car_id','')
    try: mapping = json.loads(mapping_raw)
    except: return jsonify({'error':'Invalid mapping'}), 400
    if not car_id:
        return jsonify({'error':'Vehicle required'}), 400
    conn = get_db()
    car = conn.execute('SELECT id,year,make,model FROM cars WHERE id=?',(car_id,)).fetchone()
    conn.close()
    if not car:
        return jsonify({'error':'Vehicle not found'}), 404
    try:
        raw = file.read()
        try: text = raw.decode('utf-8-sig')
        except: text = raw.decode('latin-1')
        reader = csv.DictReader(io.StringIO(text))
        csv_headers = reader.fieldnames or []
    except Exception as e:
        return jsonify({'error':f'Parse error: {e}'}), 400
    if not csv_headers:
        return jsonify({'error':'No headers'}), 400
    if not mapping or all(v=='' for v in mapping.values()):
        return jsonify({'csv_headers':csv_headers,'row_count':sum(1 for _ in reader),'target_car':dict(car),'preview_rows':[],'errors':[],'valid_count':0})
    db_fields = ['title','maintenance_type','service_date','odometer','parts_vendor','cost','notes']
    field_map = {db_f:csv_c for csv_c,db_f in mapping.items() if db_f in db_fields}
    missing = []
    if 'title' not in field_map: missing.append('Title')
    if 'service_date' not in field_map: missing.append('Service Date')
    if missing:
        return jsonify({'error':f'Required: {", ".join(missing)}'}), 400
    valid_types = {'Repair','Maintenance','Upgrade','Inspection'}
    type_map = {'repair':'Repair','maintenance':'Maintenance','upgrade':'Upgrade','service':'Maintenance',
                'mod':'Upgrade','modification':'Upgrade','fix':'Repair','maint':'Maintenance',
                'inspection':'Inspection','inspect':'Inspection'}
    preview_rows = []; errors = []; valid_count = 0
    file.seek(0)
    try:
        raw = file.read()
        try: text = raw.decode('utf-8-sig')
        except: text = raw.decode('latin-1')
        reader = csv.DictReader(io.StringIO(text))
    except:
        return jsonify({'error':'Re-read failed'}), 400
    for rn, row in enumerate(reader, start=2):
        rec = {}; errs = []
        tv = row.get(field_map.get('title',''),'').strip()
        if not tv: errs.append('Title empty')
        rec['title'] = tv
        if 'maintenance_type' in field_map:
            rt = row.get(field_map['maintenance_type'],'').strip()
            n = type_map.get(rt.lower(), rt)
            if n not in valid_types:
                if rt: errs.append(f'Unknown type "{rt}"')
                n = 'Maintenance'
            rec['maintenance_type'] = n
        else: rec['maintenance_type'] = 'Maintenance'
        if 'service_date' in field_map:
            rd = row.get(field_map['service_date'],'').strip()
            pd = _parse_date(rd)
            if not pd: errs.append(f'Invalid date "{rd}"')
            rec['service_date'] = pd or rd
        else: rec['service_date'] = ''; errs.append('Date empty')
        if 'odometer' in field_map:
            ro = re.sub(r'[^\d.]','',row.get(field_map['odometer'],'').strip())
            if ro:
                try: rec['odometer'] = int(float(ro))
                except: errs.append('Bad odo'); rec['odometer'] = None
            else: rec['odometer'] = None
        else: rec['odometer'] = None
        rec['parts_vendor'] = row.get(field_map.get('parts_vendor',''),'').strip() or None
        if 'cost' in field_map:
            rc = re.sub(r'[^\d.]','',row.get(field_map['cost'],'').strip())
            if rc:
                try: rec['cost'] = round(float(rc),2)
                except: errs.append('Bad cost'); rec['cost'] = None
            else: rec['cost'] = None
        else: rec['cost'] = None
        rec['notes'] = row.get(field_map.get('notes',''),'').strip() or None
        crit = any('empty' in e.lower() or 'invalid date' in e.lower() for e in errs)
        rec['_row_num'] = rn; rec['_errors'] = errs; rec['_valid'] = not crit
        if rec['_valid']: valid_count += 1
        preview_rows.append(rec)
        for e in errs: errors.append(f'Row {rn}: {e}')
    return jsonify({'csv_headers':csv_headers,'row_count':len(preview_rows),'target_car':dict(car),
                    'preview_rows':preview_rows,'errors':errors,'valid_count':valid_count})

@app.route('/api/import/commit', methods=['POST'])
@role_required('admin')
def csv_commit():
    data = request.get_json() or {}
    car_id = data.get('car_id'); rows = data.get('rows',[])
    if not car_id or not rows:
        return jsonify({'error':'Car ID and rows required'}), 400
    conn = get_db()
    if not conn.execute('SELECT id FROM cars WHERE id=?',(car_id,)).fetchone():
        conn.close()
        return jsonify({'error':'Not found'}), 404
    imported = 0; skipped = 0
    for r in rows:
        if not r.get('_valid'): skipped += 1; continue
        t = r.get('title','').strip(); mt = r.get('maintenance_type','Maintenance')
        sd = r.get('service_date','').strip()
        if not t or not sd: skipped += 1; continue
        if mt not in ('Repair','Maintenance','Upgrade','Inspection'): mt = 'Maintenance'
        conn.execute('INSERT INTO maintenance (car_id,title,maintenance_type,service_date,odometer,parts_vendor,cost,notes) VALUES (?,?,?,?,?,?,?,?)',
            (car_id, t, mt, sd, r.get('odometer'), r.get('parts_vendor'), r.get('cost'), r.get('notes')))
        imported += 1
    conn.commit()
    conn.close()
    return jsonify({'imported':imported,'skipped':skipped})

def _parse_date(raw):
    if not raw: return None
    raw = raw.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', raw): return raw
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$', raw)
    if m: return f'{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}'
    m = re.match(r'^(\d{4})[/](\d{1,2})[/](\d{1,2})$', raw)
    if m: return f'{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}'
    try:
        from datetime import datetime as dt
        for fmt in ('%b %d, %Y','%B %d, %Y','%b %d %Y','%B %d %Y','%d %b %Y','%d %B %Y'):
            try: return dt.strptime(raw, fmt).strftime('%Y-%m-%d')
            except ValueError: continue
    except: pass
    return None

# ── Dashboard Stats ────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    range_filter = request.args.get('range','all')
    conn = get_db()
    date_clause = ''
    if range_filter == 'month':
        date_clause = "WHERE service_date >= date('now','start of month')"
    elif range_filter == 'year':
        date_clause = "WHERE service_date >= date('now','start of year')"
    tc = conn.execute('SELECT COUNT(*) as c FROM cars').fetchone()['c']
    tm = conn.execute(f'SELECT COUNT(*) as c FROM maintenance {date_clause}').fetchone()['c']
    cost = conn.execute(f'SELECT COALESCE(SUM(cost),0) as c FROM maintenance {date_clause}').fetchone()['c']
    recent = conn.execute(
        "SELECT m.*, c.year, c.make, c.model FROM maintenance m JOIN cars c ON m.car_id=c.id ORDER BY m.created_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return jsonify({'total_cars':tc,'total_maintenance':tm,'total_cost':round(cost,2),
                    'recent_entries':[dict(r) for r in recent]})

init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
