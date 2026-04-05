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

### 2. Download the compose file and environment template

```bash
curl -O https://raw.githubusercontent.com/viibeware/garage-logbook/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/viibeware/garage-logbook/main/.env.example
```

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
cp .env.example .env
# Edit .env and set your SECRET_KEY
docker compose up -d --build
```

When building from source, the compose file will use `build: .` context. Update the `image:` line to `build: .` in `docker-compose.yml`, or simply remove the `image:` line and add `build: .` in its place.

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
├── docker-compose.yml        # Compose configuration
├── .env.example              # Environment variable template
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

Current version: **0.1.7**
