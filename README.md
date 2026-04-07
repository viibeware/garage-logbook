# Garage Logbook

Garage Logbook tracks your vehicle's service history from an elegantly simple, self-hosted web interface. It has image and document upload support (think pictures of repairs or receipt PDFs), role-based authentication, CSV import and export for existing maintenance records, and a performant dark-mode interface running in a Docker container for easy deployment.

Built and maintained by [viibeware Corp.](https://viibeware.com)

---

## Features

- **Multi-User Support** — Each user has their own garage with isolated vehicles and maintenance records
- **Vehicle Management** — Add, edit, and delete vehicles with year, make, model, VIN, purchase date, and photo
- **Maintenance Records** — Log repairs, maintenance, upgrades, and inspections with date, mileage, vendor, cost, notes, and photo galleries
- **PDF Receipts** — Upload PDF documents (receipts, invoices, estimates) to any maintenance record
- **Dashboard** — At-a-glance stats for total vehicles, service records, and money spent with configurable time ranges
- **Search & Sort** — Live search across vehicles and maintenance records with multiple sort options
- **CSV Import & Export** — Import maintenance records from CSV files with field mapping and dry-run preview, or export all records for any vehicle
- **Duplicate Records** — Quickly duplicate an existing maintenance record as a starting point
- **Role-Based Access** — Two user roles with enforced permissions:
  - **Admin** — Full access to all users' data, user management, and all features
  - **Editor** — Configurable per-user permissions (see below)
- **Granular Permissions** — Admins can toggle individual capabilities for each editor:
  - Add / Edit / Delete vehicles
  - Add / Edit / Delete maintenance records
  - Import CSV / Export CSV
- **First-Login Security** — Default admin account is forced to change password on first login
- **Image Gallery** — Upload multiple photos per maintenance record with a lightbox viewer
- **Light & Dark Theme** — Toggle between light and dark mode in Settings, saved per-user
- **Per-User Settings** — Each user can customize their dashboard preferences and theme
- **Mobile Responsive** — Works on desktop, tablet, and mobile
- **Docker Ready** — Ships as a Docker image with persistent volume storage

---

## Requirements

- Docker and Docker Compose

That's it. Everything else is handled by the container.

---

## Quick Start

### 1. Create a project directory

```bash
mkdir ~/garage-logbook && cd ~/garage-logbook
```

### 2. Download the compose file and environment template

```bash
curl -O https://raw.githubusercontent.com/viibeware/garage-logbook/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/viibeware/garage-logbook/main/.env.example
```

Or create the files manually:

<details>
<summary><strong>docker-compose.yml</strong></summary>

```yaml
services:
  garage-logbook:
    image: viibeware/garage-logbook:latest
    container_name: garage-logbook
    restart: unless-stopped
    ports:
      - "${APP_PORT:-5000}:5000"
    volumes:
      - garage-data:/data
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/login')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

volumes:
  garage-data:
    driver: local
```

</details>

<details>
<summary><strong>.env.example</strong></summary>

```bash
# Garage Logbook — Environment Configuration
# Copy this file to .env and update the values below.
#
#   cp .env.example .env
#

# ─── REQUIRED ──────────────────────────────────────────
# Session encryption key. Generate one with:
#   python3 -c "import secrets; print(secrets.token_hex(32))"
# or:
#   openssl rand -hex 32
SECRET_KEY=CHANGE-ME-replace-with-a-random-string

# ─── OPTIONAL ──────────────────────────────────────────
# Port the app is accessible on (default: 5000)
APP_PORT=5000

# Database path inside the container (typically no need to change)
DATABASE_PATH=/data/garage_logbook.db

# Upload folder inside the container (typically no need to change)
UPLOAD_FOLDER=/data/uploads
```

</details>

### 3. Create your environment file

```bash
cp .env.example .env
```

### 4. Generate a secret key and update the .env file

Generate a key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Open `.env` in your editor and replace the `SECRET_KEY` placeholder with the generated value:

```
SECRET_KEY=your-generated-key-here
```

You can also change the port here if `5000` is already in use:

```
APP_PORT=8080
```

### 5. Start the application

```bash
docker compose up -d
```

### 6. Log in

Open your browser to `http://localhost:5000` (or whatever port you configured).

| | |
|---|---|
| **Username** | `admin` |
| **Password** | `admin` |

You will be prompted to set a new password on first login.

---

## Updating

When a new version is released:

```bash
docker compose pull
docker compose up -d
```

Your data is stored in a Docker volume and is not affected by updates. Your `.env` file remains untouched.

---

## Configuration

All configuration is managed through the `.env` file. The `.env.example` file documents every available option.

| Variable | Required | Description | Default |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | Flask session encryption key | — |
| `APP_PORT` | No | Port the app is accessible on | `5000` |
| `DATABASE_PATH` | No | Database path inside the container | `/data/garage_logbook.db` |
| `UPLOAD_FOLDER` | No | Upload path inside the container | `/data/uploads` |

> **Note:** The `.env` file contains your secret key and should not be committed to version control or shared publicly.

### Running behind a reverse proxy

If you're running behind Nginx, Caddy, Nginx Proxy Manager, or similar, point the proxy to the port specified in `APP_PORT` (default `5000`). No additional configuration is needed in the app itself.

---

## Multi-User Support

Each user has their own isolated garage. Vehicles and maintenance records created by one user are not visible to other users.

**Admin users** can see all vehicles and records across every user, with owner labels displayed on each car card. This makes it easy to manage a shared instance where multiple household members or team members each track their own vehicles.

To create additional users, go to **Settings → Users → Add User** (admin only).

---

## User Roles & Permissions

Garage Logbook uses two roles. The viewer role has been removed in favor of granular permission toggles on the editor role.

### Admin

Full, unrestricted access to everything: all vehicles and records across all users, user management, import, export, and all CRUD operations.

### Editor

Access is limited to the user's own vehicles and records. Admins can configure exactly what each editor is allowed to do by toggling individual permissions:

| Permission | Default | Description |
|---|---|---|
| Add vehicles | ✓ | Create new vehicles |
| Edit vehicles | ✓ | Modify existing vehicles |
| Delete vehicles | ✓ | Remove vehicles and all associated records |
| Add records | ✓ | Create maintenance records |
| Edit records | ✓ | Modify existing records |
| Delete records | ✓ | Remove maintenance records |
| Import CSV | — | Import records from CSV files |
| Export CSV | ✓ | Export records to CSV files |

Permissions are configured per-user from **Settings → Users → Edit**.

---

## Backup & Restore

### Backup

```bash
docker compose stop
docker run --rm \
  -v garage-logbook_garage-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/garage-logbook-backup.tar.gz -C /data .
docker compose up -d
```

This creates `garage-logbook-backup.tar.gz` in your current directory containing the database and all uploaded images and documents.

### Restore

```bash
docker compose stop
docker run --rm \
  -v garage-logbook_garage-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/garage-logbook-backup.tar.gz -C /data"
docker compose up -d
```

---

## Building from Source

If you prefer to build the Docker image yourself rather than pulling from Docker Hub:

```bash
git clone https://github.com/viibeware/garage-logbook.git
cd garage-logbook
cp .env.example .env
# Edit .env and set your SECRET_KEY
```

Update `docker-compose.yml` to use `build: .` instead of `image: viibeware/garage-logbook:latest`, then:

```bash
docker compose up -d --build
```

### Running without Docker

Garage Logbook can also run directly on a Linux system with Python 3.10+:

```bash
git clone https://github.com/viibeware/garage-logbook.git
cd garage-logbook
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
python app.py
```

The app will be available at `http://localhost:5000`. The database and uploads will be stored in the project directory.

---

## Project Structure

```
garage-logbook/
├── app.py                    # Flask application
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build instructions
├── docker-compose.yml        # Compose configuration
├── .env.example              # Environment variable template
├── .github/
│   └── workflows/
│       └── release.yml       # Auto-create GitHub releases on tag push
├── static/
│   ├── css/style.css         # Stylesheet (dark + light themes)
│   ├── js/app.js             # Frontend JavaScript
│   ├── garage-logbook_logo.svg
│   ├── viibeware_logo.svg
│   └── favicon.png
└── templates/
    ├── index.html            # Main application template
    └── login.html            # Login page
```

---

## License

This project is provided as-is for personal and internal use. See the repository for license details.

---

## About

Garage Logbook is developed by [viibeware Corp.](https://viibeware.com)

Current version: **0.1.9**
