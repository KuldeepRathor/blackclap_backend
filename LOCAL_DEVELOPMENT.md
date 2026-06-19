# Local Development Guide

Everything you need to run BlackClap backend on your machine.

---

## Prerequisites

- Python 3.12+
- Docker + Docker Compose v2
- Git

---

## First-Time Setup

### 1. Clone the repo

```bash
git clone https://github.com/KuldeepRathor/blackclap_backend.git
cd blackclap_backend
```

### 2. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .[dev]
```

### 3. Set up environment file

The project loads env vars from a SSOT file **one level above** the repo root.

```bash
# From inside blackclap_backend/
cp .env.example ../ssot.development.env
```

Open `../ssot.development.env` and fill in your values:

```env
APP_NAME=BlackClap
DEBUG=True

# Keep these as-is for local Docker setup
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/blackclap
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/service-account.json

# JWT
JWT_SECRET_KEY=any-local-dev-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## Running Locally

There are two ways to run the project. Pick one.

---

### Option A — Infra via Docker, App natively (recommended for development)

Runs PostgreSQL and Redis in Docker, but FastAPI and Celery run directly on your machine. Hot-reload works, debugger attaches, logs are easy to read.

**Step 1: Start infrastructure**

```bash
docker compose up -d db redis
```

**Step 2: Apply migrations**

```bash
ENV=development alembic upgrade head
```

**Step 3: Start FastAPI + Celery together**

```bash
source venv/bin/activate
ENV=development python3 scripts/start_services.py
```

To stop: press `Ctrl+C` in that terminal.

**Optional — run FastAPI and Celery in separate terminals**

Terminal 1:
```bash
source venv/bin/activate
ENV=development uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2:
```bash
source venv/bin/activate
ENV=development celery -A app.workers.celery_app worker --loglevel=info
```

---

### Option B — Everything in Docker

Runs all four services (api, db, redis, worker) inside Docker.

**Step 1: Ensure `.env` has Docker service hostnames**

Open `.env` (not the SSOT file) and use service names instead of `localhost`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/blackclap
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

**Step 2: Build and start all services**

```bash
docker compose up -d --build
```

**Step 3: Apply migrations inside the container**

```bash
docker compose exec api alembic upgrade head
```

**To stop:**

```bash
docker compose down
```

**To stop and wipe the database volume:**

```bash
docker compose down -v
```

---

## Verify It's Running

```bash
# Root endpoint
curl http://localhost:8000

# Health check
curl http://localhost:8000/api/v1/health
```

Open Swagger UI in browser:
```
http://localhost:8000/api/v1/docs
```

---

## Database Migrations (Alembic)

```bash
# Apply all pending migrations
ENV=development alembic upgrade head

# Generate a new migration after changing models
ENV=development alembic revision --autogenerate -m "describe_your_change"

# Roll back the last migration
ENV=development alembic downgrade -1

# Check current migration state
ENV=development alembic current

# View migration history
ENV=development alembic history
```

---

## Docker Commands Reference

```bash
# Start only infra (db + redis)
docker compose up -d db redis

# Start all services
docker compose up -d

# Rebuild and restart (after code/dependency changes)
docker compose up -d --build

# View logs for a specific service
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f db

# Open a shell inside a running container
docker compose exec api bash
docker compose exec db psql -U user -d blackclap

# Stop all containers (keep volumes)
docker compose down

# Stop and delete volumes (wipes database)
docker compose down -v

# Check running containers
docker ps
```

---

## Linting and Formatting

```bash
# Format with Black
black app/ scripts/

# Lint with Ruff
ruff check app/ scripts/

# Auto-fix lint issues
ruff check app/ scripts/ --fix

# Type check with mypy
mypy app/
```

---

## Running Tests

```bash
ENV=development pytest

# With verbose output
ENV=development pytest -v

# Run a specific test file
ENV=development pytest tests/test_auth.py
```

---

## Environment Variable Reference

| Variable | Description | Example |
|---|---|---|
| `ENV` | Environment name (loads SSOT file) | `development` |
| `PORT` | FastAPI port (start_services.py only) | `8000` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection for app | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Redis DB for Celery tasks | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Redis DB for Celery results | `redis://localhost:6379/1` |
| `JWT_SECRET_KEY` | Secret for signing JWTs | any long random string |
| `FIREBASE_PROJECT_ID` | Firebase project ID | `blackclap-prod` |

---

## Troubleshooting

**`Form data requires python-multipart`**
```bash
pip install python-multipart
# or it's already in pyproject.toml — reinstall:
pip install -e .[dev]
```

**`Connection refused` on port 5432 or 6379**

The Docker infra containers are not running. Start them:
```bash
docker compose up -d db redis
```

**Alembic `can't locate revision` error**

Your local DB is ahead of or behind the migration history. Reset:
```bash
docker compose down -v
docker compose up -d db redis
ENV=development alembic upgrade head
```

**`ModuleNotFoundError: No module named 'app'`**

You're not inside the venv or the package isn't installed:
```bash
source venv/bin/activate
pip install -e .[dev]
```

**Port 8000 already in use**

```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9

# Or run on a different port
ENV=development PORT=8080 python3 scripts/start_services.py
```
