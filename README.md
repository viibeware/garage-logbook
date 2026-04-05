# Garage Logbook

A self-hosted car maintenance tracker built with Flask and SQLite. Keep a detailed record of every repair, service, upgrade, and inspection across all your vehicles — with photos, costs, mileage, and full export/import support.

Built and maintained by [viibeware Corp.](https://viibeware.com)

---

## Features

- **Vehicle Management** — Add, edit, and delete vehicles with year, make, model, VIN, purchase date, and photo
- **Maintenance Records** — Log repairs, maintenance, upgrades, and inspections with date, mileage, vendor, cost, notes, and photo galleries
- **Dashboard** — At-a-glance stats for total vehicles, service records, and money spent with configurable time ranges (monthly, yearly, all time)
- **Search & Sort** — Live AJAX search across vehicles and maintenance records with multiple sort options
- **CSV Import** — Import maintenance records from CSV files with field mapping and a dry-run preview before committing
- **CSV Export** — Export all maintenance records for any vehicle as a CSV file
- **Duplicate Records** — Quickly duplicate an existing maintenance record as a starting point
- **Role-Based Access** — Three user roles with enforced permissions:
  - **Admin** — Full access including user management and CSV import
  - **Editor** — Can create, edit, and delete vehicles and records
  - **Viewer** — Read-only access to all data
- **User Management** — Admins can create, edit, and delete user accounts with role assignment
- **First-Login Security** — Default admin account is forced to change password on first login
- **Image Gallery** — Upload multiple photos per maintenance record with a lightbox viewer
- **Per-User Settings** — Each user can customize their dashboard preferences
- **Dark Theme** — Clean, modern interface designed for readability
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

### 2. Download the compose file

```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/viibeware/garage-logbook/main/docker-compose.yml
```

Or create `docker-compose.yml` manually with the following contents:

```yaml
services:
  garage-logbook:
    image: viibeware/garage-logbook:latest
    container_name: garage-logbook
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - garage-data:/data
    environment:
      - SECRET_KEY=CHANGE-ME-generate-a-random-string
      - DATABASE_PATH=/data/garage_logbook.db
      - UPLOAD_FOLDER=/data/uploads

volumes:
  garage-data:
    driver: local
```

### 3. Generate a secret key

Replace the placeholder `SECRET_KEY` value in `docker-compose.yml` with a random string:

```bash
# Using Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# Or using OpenSSL
openssl rand -hex 32
```

Copy the output and paste it as the `SECRET_KEY` value in your compose file.

### 4. Start the application

```bash
docker compose up -d
```

### 5. Log in

Open your browser to `http://localhost:5000` (or your server's IP address).

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

Your data is stored in a Docker volume and is not affected by updates.

---

## Configuration

All configuration is done through environment variables in `docker-compose.yml`.

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session encryption key. **Must be changed.** | `CHANGE-ME-...` |
| `DATABASE_PATH` | Path to the SQLite database inside the container | `/data/garage_logbook.db` |
| `UPLOAD_FOLDER` | Path to uploaded images inside the container | `/data/uploads` |

### Changing the port

To run on a different port, modify the `ports` mapping. The left side is the host port:

```yaml
ports:
  - "8080:5000"  # Access on port 8080
```

### Running behind a reverse proxy

If you're running behind Nginx, Caddy, Nginx Proxy Manager, or similar, point the proxy to port `5000` on the container. No additional configuration is needed in the app itself.

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

This creates `garage-logbook-backup.tar.gz` in your current directory containing the database and all uploaded images.

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
docker build -t garage-logbook .
```

Then update your `docker-compose.yml` to use `build: .` instead of `image: viibeware/garage-logbook:latest`.

### Running without Docker

Garage Logbook can also run directly on a Linux system with Python 3.10+:

```bash
git clone https://github.com/viibeware/garage-logbook.git
cd garage-logbook
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app will be available at `http://localhost:5000`. The database and uploads will be stored in the project directory.

---

## User Roles

| Role | View Data | Add/Edit/Delete Records | Manage Users | Import CSV |
|---|---|---|---|---|
| **Viewer** | ✓ | — | — | — |
| **Editor** | ✓ | ✓ | — | — |
| **Admin** | ✓ | ✓ | ✓ | ✓ |

Only admin users can create new accounts. This is done from **Settings → Users** in the application.

---

## Project Structure

```
garage-logbook/
├── app.py                    # Flask application
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build instructions
├── docker-compose.yml        # Development compose file
├── static/
│   ├── css/style.css         # Stylesheet
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

Current version: **0.1.6**
