# Production Deployment

### SSH into server

```bash
ssh -i ~/.ssh/blackclap-api-vm_key.pem azureuser@<AZURE_PUBLIC_IP>
```

### First-time setup on server

The VM runs the stack via Docker Compose (`api`, `worker`, `db`, `redis` — see [docker-compose.yml](../docker-compose.yml)), cloned at `/home/azureuser/apps/blackclap_backend`.

```bash
git clone https://github.com/KuldeepRathor/blackclap_backend.git /home/azureuser/apps/blackclap_backend
cd /home/azureuser/apps/blackclap_backend
```

### Create production env file

```bash
nano ../ssot.production.env
```

Required values:

```env
APP_NAME=BlackClap
DEBUG=False
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:5432/blackclap
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
JWT_SECRET_KEY=<min-32-char-random-string>
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
AZURE_STORAGE_ACCOUNT_NAME=blackclapmedia
```

### Build and start the stack

```bash
docker compose build
docker compose up -d
```

### Run migrations

```bash
docker compose run --rm api alembic upgrade head
```

### Nginx config

```nginx
# /etc/nginx/sites-available/blackclap
server {
    listen 80;
    server_name api.blackclap.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 50M;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/blackclap /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Add HTTPS

```bash
sudo certbot --nginx -d api.blackclap.com
```

---

## CI/CD — Automated Deploys (GitHub Actions)

Every push to `main` triggers [.github/workflows/deploy.yml](../.github/workflows/deploy.yml):

```text
push to main
    │
    ├─ checks job (GitHub cloud runner)
    │    ruff check . / ruff format --check . / mypy --strict app
    │
    └─ deploy job (self-hosted runner ON the Azure VM, runs only if checks pass)
         cd /home/azureuser/apps/blackclap_backend
         git fetch + git reset --hard origin/main
         docker compose build
         docker compose run --rm api alembic upgrade head
         docker compose up -d
         curl health check (retries 10× before failing)
```

Notes:

- The deploy job runs **on the VM itself** via a self-hosted runner, so the NSG stays locked down (no SSH from GitHub needed) and no SSH secrets are stored in GitHub.
- The deploy uses `git reset --hard origin/main` (not `git pull`) so the VM clone always matches `main` exactly, even if it was edited manually.
- Migrations run automatically via a throwaway `api` container (`docker compose run --rm`), built from the freshly-updated image, before the running containers are recreated. Migration files are generated **locally** (`alembic revision --autogenerate`), committed, and pushed — production only applies them with `alembic upgrade head`, it never generates new ones.
- `docker compose up -d` recreates any container whose image or config changed; unaffected services (db, redis) are left running.
- Overlapping deploys queue (concurrency group `production-deploy`), they never race.
- Manual re-deploy: GitHub → Actions → "CI / Deploy to Production" → Run workflow.

### One-time VM setup for the self-hosted runner

1. **Install the runner** (GitHub repo → Settings → Actions → Runners → New self-hosted runner → Linux x64, then follow the shown download/config commands on the VM as `azureuser`, e.g. in `/home/azureuser/actions-runner`). When `./config.sh` asks for extra labels, add: `blackclap-prod`.

2. **Run it as a service** so it survives reboots:

   ```bash
   cd /home/azureuser/actions-runner
   sudo ./svc.sh install azureuser
   sudo ./svc.sh start
   sudo ./svc.sh status
   ```

3. **Make sure `azureuser` can run Docker without a password prompt** — add it to the `docker` group (skip if already a member):

   ```bash
   sudo usermod -aG docker azureuser
   # then restart the runner service (or re-login) for the group change to take effect
   sudo ./svc.sh stop && sudo ./svc.sh start
   ```

4. Push any commit to `main` and watch the Actions tab — the runner should pick up the deploy job.

The manual steps below remain valid as a **fallback** if the pipeline is ever down.

### Deploy a code update (manual fallback)

```bash
cd /home/azureuser/apps/blackclap_backend
git pull origin main
docker compose build
docker compose run --rm api alembic upgrade head   # only if models changed
docker compose up -d
```

### Check service status

```bash
docker compose ps
```

### Tail production logs

```bash
docker compose logs -f api
docker compose logs -f worker
```

### Health check

```bash
curl https://api.blackclap.com/api/v1/health
```
