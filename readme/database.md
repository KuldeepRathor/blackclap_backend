# Database

## Migrations (Alembic)

### Apply all pending migrations

```bash
ENV=development alembic upgrade head
```

### Generate migration after changing a model

```bash
ENV=development alembic revision --autogenerate -m "add_posts_table"
# Always review the generated file in alembic/versions/ before running
```

### Roll back last migration

```bash
ENV=development alembic downgrade -1
```

### Roll back to a specific revision

```bash
ENV=development alembic downgrade <revision_id>
```

### Check current state

```bash
ENV=development alembic current
```

### View migration history

```bash
ENV=development alembic history --verbose
```

### Preview SQL without running (dry run)

```bash
ENV=development alembic upgrade head --sql
```

### Check if DB is in sync with models

```bash
ENV=development alembic check
```

---

## Connecting to the Database

### Local (Docker)

```bash
docker compose exec db psql -U user -d blackclap
```

### Local (native psql)

```bash
psql postgresql://user:password@localhost:5432/blackclap
```

### Production (via SSH tunnel)

```bash
# Open tunnel
ssh -L 5433:<db_host>:5432 azureuser@<AZURE_PUBLIC_IP> -N &

# Connect
psql postgresql://<user>:<pass>@localhost:5433/blackclap
```

---

## Useful SQL Queries

```sql
-- List all tables
\dt

-- Describe a table
\d users

-- Latest users
SELECT id, username, email, created_at FROM users ORDER BY created_at DESC LIMIT 10;

-- Find a user
SELECT * FROM users WHERE email = 'you@example.com';

-- Check avatar URLs
SELECT id, username, avatar_url FROM users WHERE avatar_url IS NOT NULL;

-- Current migration in DB
SELECT * FROM alembic_version;

-- Exit
\q
```

---

## Reset Local DB

```bash
docker compose down -v
docker compose up -d db redis
ENV=development alembic upgrade head
```

---

## View Docker DB logs

```bash
docker compose logs -f db
```
