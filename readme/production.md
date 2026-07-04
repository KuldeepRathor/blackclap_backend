# Production Deployment

### SSH into server

```bash
ssh -i ~/.ssh/blackclap-api-vm_key.pem azureuser@<AZURE_PUBLIC_IP>
```

### First-time setup on server

```bash
git clone https://github.com/KuldeepRathor/blackclap_backend.git
cd blackclap_backend

python3 -m venv venv
source venv/bin/activate
pip install -e .
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

### Run migrations

```bash
ENV=production alembic upgrade head
```

### Start API (systemd)

```bash
# /etc/systemd/system/blackclap-api.service
[Unit]
Description=BlackClap API
After=network.target

[Service]
User=azureuser
WorkingDirectory=/home/azureuser/blackclap_backend
Environment=ENV=production
ExecStart=/home/azureuser/blackclap_backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable blackclap-api
sudo systemctl start blackclap-api
```

### Start Celery worker (systemd)

```bash
# /etc/systemd/system/blackclap-worker.service
[Unit]
Description=BlackClap Celery Worker
After=network.target

[Service]
User=azureuser
WorkingDirectory=/home/azureuser/blackclap_backend
Environment=ENV=production
ExecStart=/home/azureuser/blackclap_backend/venv/bin/celery -A app.workers.celery_app worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable blackclap-worker
sudo systemctl start blackclap-worker
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
         git fetch + git reset --hard origin/main
         pip install -e .
         ENV=production alembic upgrade head
         sudo systemctl restart blackclap-api blackclap-worker
         curl health check (retries 10× before failing)
```

Notes:

- The deploy job runs **on the VM itself** via a self-hosted runner, so the NSG stays locked down (no SSH from GitHub needed) and no SSH secrets are stored in GitHub.
- The deploy uses `git reset --hard origin/main` (not `git pull`) so the VM clone always matches `main` exactly, even if it was edited manually.
- Migrations run automatically. Migration files are generated **locally** (`alembic revision --autogenerate`), committed, and pushed — production only applies them with `alembic upgrade head`, it never generates new ones.
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

3. **Allow passwordless service restarts** (skip if `azureuser` already has full NOPASSWD sudo):

   ```bash
   echo 'azureuser ALL=(root) NOPASSWD: /usr/bin/systemctl restart blackclap-api blackclap-worker, /usr/bin/systemctl restart blackclap-api, /usr/bin/systemctl restart blackclap-worker, /usr/bin/systemctl status blackclap-api --no-pager -l' | sudo tee /etc/sudoers.d/blackclap-deploy
   sudo chmod 440 /etc/sudoers.d/blackclap-deploy
   ```

4. Push any commit to `main` and watch the Actions tab — the runner should pick up the deploy job.

The manual steps below remain valid as a **fallback** if the pipeline is ever down.

### Deploy a code update (manual fallback)

```bash
git pull origin main
source venv/bin/activate
pip install -e .                        # only if dependencies changed
ENV=production alembic upgrade head     # only if models changed
sudo systemctl restart blackclap-api
sudo systemctl restart blackclap-worker
```

### Check service status

```bash
sudo systemctl status blackclap-api
sudo systemctl status blackclap-worker
```

### Tail production logs

```bash
sudo journalctl -u blackclap-api -f
sudo journalctl -u blackclap-worker -f
```

### Health check

```bash
curl https://api.blackclap.com/api/v1/health
```
