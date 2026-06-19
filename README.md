# BlackClap Backend

Instagram/TikTok-style social media platform — short-form videos, image posts, realtime interactions. Modular monolith built to ship fast and scale later.

---

## Tech Stack

| Layer                | Technology                             |
| -------------------- | -------------------------------------- |
| Framework            | FastAPI (Python 3.12)                  |
| ORM                  | SQLAlchemy 2 (Async)                   |
| Migrations           | Alembic                                |
| Database             | PostgreSQL 15                          |
| Cache / Queue Broker | Redis 7                                |
| Background Workers   | Celery                                 |
| Auth                 | Firebase Authentication + JWT          |
| Media Storage        | Azure Blob Storage (SAS direct upload) |
| Containerization     | Docker + Docker Compose                |
| Reverse Proxy        | Nginx                                  |

---

## Architecture

```
Internet
    │
Azure NSG (Firewall)
    │
Nginx :80 / :443          ← SSL termination, reverse proxy
    │
localhost:8000
    │
FastAPI (Docker)          ← API + business logic
    │
    ├── PostgreSQL (Docker internal, port not exposed)
    ├── Redis (Docker internal, port not exposed)
    └── Celery Worker (Docker, consumes Redis queue)
```

### Port Exposure Policy

| Service | Public | External | Localhost | Docker Network |
|---|---|---|---|---|
| Nginx | 80, 443 | ✅ | ✅ | — |
| FastAPI (8000) | ❌ | ❌ | ✅ only | ✅ |
| PostgreSQL (5432) | ❌ | ❌ | ❌ | ✅ only |
| Redis (6379) | ❌ | ❌ | ❌ | ✅ only |

---

## Production Infrastructure (Azure)

### Resource Group

| Field | Value |
|---|---|
| Name | `blackclap-prod-rg` |
| Region | Central India |
| Reason | Low latency for India-first users |

### Virtual Machine

| Field | Value |
|---|---|
| Name | `blackclap-api-vm` |
| OS | Ubuntu Server 24.04 LTS x64 Gen2 |
| Size | Standard_B2s_v2 (2 vCPU, 8 GB RAM) |
| Disk | 64 GB Premium SSD LRS |
| Auth | SSH key — `~/.ssh/blackclap-api-vm_key.pem` |
| Username | `azureuser` |

SSH into VM:
```bash
ssh -i ~/.ssh/blackclap-api-vm_key.pem azureuser@<AZURE_PUBLIC_IP>
```

### Network Security Group (NSG) Rules

| Rule | Port | Source | Purpose |
|---|---|---|---|
| SSH | 22 | My IP only (`49.36.xx.xx/32`) | Secure shell access |
| HTTP | 80 | Any | Web traffic |
| HTTPS | 443 | Any | Secure web traffic |

No DB or cache ports are open to the public or any external source.

### Software Installed on VM

```
Docker, Docker Compose v2, Git, Curl, Nginx
```

---

## Project Structure

```
blackclap_backend/
├── app/
│   ├── main.py                  # FastAPI app, routers, middleware
│   └── modules/
│       ├── auth/                # Auth routes, JWT logic
│       ├── users/               # User profile routes
│       └── media/               # Media upload routes
├── alembic/                     # Database migration scripts
├── scripts/
│   └── start_services.py        # Concurrent FastAPI + Celery launcher
├── static/                      # Local static file serving (dev only)
├── docs/                        # Flow documentation
│   ├── auth_flow.md
│   └── profile_flow.md
├── rules.md                     # Architecture rules and design decisions
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Welcome message + version |
| `/api/v1/health` | GET | Health check |
| `/api/v1/docs` | GET | Swagger UI |
| `/api/v1/redoc` | GET | ReDoc UI |
| `/api/v1/openapi.json` | GET | OpenAPI schema |

---

## Environment Variables

The project uses a **Single Source of Truth (SSOT)** pattern for environment files. The env file lives **one directory above** the repo root to prevent accidental commits.

### SSOT File Location

```
/path/to/blackclap/                   ← parent directory
├── ssot.development.env              ← loaded for ENV=development
├── ssot.staging.env                  ← loaded for ENV=staging
├── ssot.production.env               ← loaded for ENV=production
└── blackclap_backend/                ← repo root
    └── .env                          ← fallback if SSOT not found
```

### Required Variables

```env
# App
APP_NAME=BlackClap
DEBUG=True

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/blackclap

# Firebase Auth
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/service-account.json

# Azure Blob Storage (media uploads via SAS URLs)
AZURE_STORAGE_ACCOUNT_NAME=your-account
AZURE_STORAGE_ACCOUNT_KEY=your-key
AZURE_STORAGE_CONTAINER_NAME=blackclap-media

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# JWT
JWT_SECRET_KEY=change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> For Docker Compose, replace `localhost` with the service name: `db` for PostgreSQL and `redis` for Redis.

---

## Media Upload Architecture

Flutter never uploads media through the API server. Direct SAS upload keeps the VM load-free.

```
Flutter App
    │  POST /api/v1/media/upload-url
    ▼
FastAPI  →  Generates Azure Blob SAS URL  →  Returns URL to Flutter
    │
Flutter uploads file directly to Azure Blob Storage
    │
Flutter sends POST /api/v1/media/confirm with blob URL
    │
FastAPI saves metadata to PostgreSQL
```

---

## Nginx Configuration (Production)

Located at `/etc/nginx/sites-available/blackclap-api` on the VM:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Planned Next Steps

- [ ] Domain: point `api.blackclap.com` DNS A record to Azure VM IP
- [ ] HTTPS: Nginx + Certbot + Let's Encrypt (open port 443 in NSG)
- [ ] Azure Blob Storage: wire up SAS URL generation endpoint
- [ ] CI/CD: GitHub Actions → SSH deploy on push to `main`
- [ ] Managed DB: migrate to Azure Database for PostgreSQL (Flexible Server)
- [ ] Monitoring: Azure Monitor + structured logging via structlog
- [ ] Scaling: Azure VM Scale Sets or AKS when load demands it

---

## Design Decisions

See [rules.md](rules.md) for architecture rules, coding conventions, and database guidelines.
