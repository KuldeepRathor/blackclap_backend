# BlackClap Backend — Development & Deployment Guide

Tech stack: **FastAPI · PostgreSQL · SQLAlchemy (async) · Alembic · Redis · Celery · Azure Blob Storage · Docker**

---

## Table of Contents

1. [Running Locally](#1-running-locally)
2. [Running in Production](#2-running-in-production)
3. [Database Migrations](#3-database-migrations)
4. [Inspecting the Database](#4-inspecting-the-database)

---

## 1. Running Locally

### Prerequisites

- Python 3.12+
- Docker + Docker Compose v2
- Git

---

### First-Time Setup

**Clone and install:**

```bash
git clone https://github.com/KuldeepRathor/blackclap_backend.git
cd blackclap_backend

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

**Create the environment file:**

```bash
cp .env.example ../ssot.development.env
```

The app reads env vars from `ssot.{ENV}.env` one level above the repo root.  
Open `../ssot.development.env` and fill in real values:

```env
APP_NAME=BlackClap
DEBUG=True

# Keep these for local Docker infra
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/blackclap
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# JWT
JWT_SECRET_KEY=any-long-local-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Azure (optional for local — upload endpoints will fail without it)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
AZURE_STORAGE_ACCOUNT_NAME=blackclapmedia
```

---

### Starting the Server (Recommended: infra in Docker, app native)

This gives you hot-reload and easy log reading.

**Step 1 — Start PostgreSQL and Redis:**

```bash
docker compose up -d db redis
```

**Step 2 — Apply database migrations:**

```bash
ENV=development alembic upgrade head
```

**Step 3 — Start FastAPI + Celery:**

```bash
ENV=development python3 scripts/start_services.py
```

Or in separate terminals:

```bash
# Terminal 1 — API server
ENV=development uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Celery worker
ENV=development celery -A app.workers.celery_app worker --loglevel=info
```

**Verify:**

```bash
curl http://localhost:8000/api/v1/health
# → {"status": "healthy"}
```

Swagger UI: http://localhost:8000/api/v1/docs

---

### Option B — Everything in Docker

Use when you don't want anything running natively.

```bash
# Build and start all services
docker compose up -d --build

# Apply migrations inside the container
docker compose exec api alembic upgrade head

# Check logs
docker compose logs -f api
```

> When running fully in Docker, use service hostnames in env vars:
> ```env
> DATABASE_URL=postgresql+asyncpg://user:password@db:5432/blackclap
> REDIS_URL=redis://redis:6379/0
> ```

---

## 2. Running in Production

### Server Requirements

- Ubuntu 22.04 (or any Linux)
- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Nginx (as reverse proxy)
- `systemd` or `supervisor` to keep processes alive

---

### Step-by-Step Deployment

**Step 1 — SSH into the server and clone the repo:**

```bash
git clone https://github.com/KuldeepRathor/blackclap_backend.git
cd blackclap_backend
```

**Step 2 — Create virtual environment and install:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

**Step 3 — Create the production env file:**

The app looks for `ssot.production.env` one level above the repo root.

```bash
# One level up from the repo
nano ../ssot.production.env
```

Fill in all production values:

```env
APP_NAME=BlackClap
DEBUG=False

DATABASE_URL=postgresql+asyncpg://<db_user>:<db_password>@<db_host>:5432/blackclap
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

JWT_SECRET_KEY=<long-random-secret-min-32-chars>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
AZURE_STORAGE_ACCOUNT_NAME=blackclapmedia
AZURE_SAS_EXPIRY_MINUTES=15
```

**Step 4 — Run database migrations:**

```bash
ENV=production alembic upgrade head
```

**Step 5 — Start the API with gunicorn/uvicorn:**

```bash
ENV=production uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-access-log
```

For a persistent process, create a systemd service at `/etc/systemd/system/blackclap-api.service`:

```ini
[Unit]
Description=BlackClap API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/blackclap_backend
Environment=ENV=production
ExecStart=/home/ubuntu/blackclap_backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable blackclap-api
sudo systemctl start blackclap-api
sudo systemctl status blackclap-api
```

**Step 6 — Start the Celery worker:**

```ini
# /etc/systemd/system/blackclap-worker.service
[Unit]
Description=BlackClap Celery Worker
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/blackclap_backend
Environment=ENV=production
ExecStart=/home/ubuntu/blackclap_backend/venv/bin/celery -A app.workers.celery_app worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable blackclap-worker
sudo systemctl start blackclap-worker
```

**Step 7 — Configure Nginx:**

```nginx
# /etc/nginx/sites-available/blackclap
server {
    listen 80;
    server_name api.blackclap.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
        client_max_body_size 50M;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/blackclap /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Add HTTPS with Certbot:

```bash
sudo certbot --nginx -d api.blackclap.com
```

**Step 8 — Deploying code updates:**

```bash
cd /home/ubuntu/blackclap_backend
git pull origin main
source venv/bin/activate
pip install -e .                          # if dependencies changed

ENV=production alembic upgrade head       # if models changed

sudo systemctl restart blackclap-api
sudo systemctl restart blackclap-worker
```

---

## 3. Database Migrations

All migrations are managed with **Alembic**. Always run these from inside `blackclap_backend/`.

### Apply all pending migrations (most common)

```bash
ENV=development alembic upgrade head
```

### Generate a new migration after changing a model

```bash
ENV=development alembic revision --autogenerate -m "add_posts_table"
```

This creates a file in `alembic/versions/`. **Always review it before running** — autogenerate is smart but not perfect.

### Roll back the last migration

```bash
ENV=development alembic downgrade -1
```

### Roll back to a specific revision

```bash
ENV=development alembic downgrade <revision_id>
# example:
ENV=development alembic downgrade f6cb4894f8e5
```

### Check current migration state

```bash
ENV=development alembic current
```

### View full migration history

```bash
ENV=development alembic history --verbose
```

### Show SQL without running it (dry run)

```bash
ENV=development alembic upgrade head --sql
```

---

### Workflow for a New Model Change

1. Edit or add a model file under `app/modules/<module>/models.py`
2. Import the model in `alembic/env.py` (so Alembic can detect it)
3. Generate migration: `ENV=development alembic revision --autogenerate -m "describe_change"`
4. Open the generated file in `alembic/versions/` and verify the `upgrade()` / `downgrade()` functions
5. Apply: `ENV=development alembic upgrade head`

---

## 4. Inspecting the Database

### Connect to PostgreSQL directly

**Local (Docker):**

```bash
docker compose exec db psql -U user -d blackclap
```

**Local (native psql):**

```bash
psql postgresql://user:password@localhost:5432/blackclap
```

**Production (SSH tunnel):**

```bash
# Open a tunnel first
ssh -L 5433:<db_host>:5432 ubuntu@api.blackclap.com -N &

# Then connect locally
psql postgresql://<db_user>:<db_password>@localhost:5433/blackclap
```

---

### Useful psql commands

```sql
-- List all tables
\dt

-- Describe a table's columns and types
\d users

-- Show indexes on a table
\di users*

-- Count rows
SELECT COUNT(*) FROM users;

-- View latest users
SELECT id, username, email, created_at FROM users ORDER BY created_at DESC LIMIT 10;

-- View a specific user
SELECT * FROM users WHERE email = 'cooldeep226@gmail.com';

-- Check avatar URLs stored
SELECT id, username, avatar_url FROM users WHERE avatar_url IS NOT NULL;

-- View alembic migration history recorded in DB
SELECT * FROM alembic_version;

-- Exit psql
\q
```

---

### GUI Clients (Recommended for development)

| Tool | Platform | Connection string |
|---|---|---|
| **TablePlus** | macOS/Windows | `postgresql://user:password@localhost:5432/blackclap` |
| **DBeaver** | All | Same |
| **pgAdmin** | All | Host: localhost, Port: 5432, DB: blackclap |

---

### Viewing What a Migration Will Change (Before Applying)

```bash
# Show the SQL Alembic would execute
ENV=development alembic upgrade head --sql

# Diff current DB schema vs. models (shows what's out of sync)
ENV=development alembic check
```

---

### Resetting the Local Database (Dev Only)

```bash
# Wipe all data and volumes
docker compose down -v

# Restart infra
docker compose up -d db redis

# Re-apply all migrations from scratch
ENV=development alembic upgrade head
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start local infra | `docker compose up -d db redis` |
| Start API server | `ENV=development uvicorn app.main:app --reload` |
| Apply migrations | `ENV=development alembic upgrade head` |
| New migration | `ENV=development alembic revision --autogenerate -m "description"` |
| Roll back 1 step | `ENV=development alembic downgrade -1` |
| Check migration state | `ENV=development alembic current` |
| Open local DB shell | `docker compose exec db psql -U user -d blackclap` |
| View API logs | `docker compose logs -f api` |
| Restart production API | `sudo systemctl restart blackclap-api` |
| Tail production logs | `sudo journalctl -u blackclap-api -f` |
| Health check | `curl https://api.blackclap.com/api/v1/health` |
| Swagger UI (local) | http://localhost:8000/api/v1/docs |
