# Local Development

### Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Create env file

```bash
cp .env.example ../ssot.development.env
# Edit ../ssot.development.env with your values
```

### Start infra (PostgreSQL + Redis)

```bash
docker compose up -d db redis
```

### Apply migrations

```bash
ENV=development alembic upgrade head
```

### Run the server

```bash
ENV=development python3 scripts/start_services.py
```

Or separately:

```bash
# Terminal 1 — API
ENV=development uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Celery worker
ENV=development celery -A app.workers.celery_app worker --loglevel=info
```

### Verify

```bash
curl http://localhost:8000/api/v1/health
```

Swagger UI → http://localhost:8000/api/v1/docs

---

### Kill port 8000

```bash
lsof -ti:8000 | xargs kill -9
```

### Stop infra

```bash
docker compose down
```

### Wipe database and start fresh

```bash
docker compose down -v
docker compose up -d db redis
ENV=development alembic upgrade head
```

### Lint / format

```bash
ruff check app/ --fix
black app/
mypy app/
```
