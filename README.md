# BlackClap Backend

BlackClap is a startup-focused social media backend designed with a **Modular Monolith** architecture for short-form video content, image posts, and realtime interactions.

---

## 🏗️ Architecture & Stack
This project follows a strict Modular Monolith pattern to ensure ease of deployment and future scalability without premature microservice overhead.

- **Framework:** FastAPI (Python 3.10+)
- **ORM:** SQLAlchemy 2 (Async)
- **Database:** PostgreSQL
- **Migration Tool:** Alembic (Async migrations)
- **Authentication:** Firebase Authentication
- **Storage:** AWS S3 + CloudFront CDN
- **Background Jobs:** Celery + Redis
- **Containerization:** Docker & Docker Compose

For a detailed list of design decisions, coding rules, and database guidelines, please refer to [rules.md](file:///Users/kuldeeprathor/codes/backend/blackclap/blackclap_backend/rules.md).

---

## 🔑 Environment Variables Setup (SSOT)

To keep secrets and environments isolated and prevent sensitive files from being accidentally pushed to Git, the configuration uses a Single Source of Truth (SSOT) pattern.

### External SSOT Path
The environment file resides **one level above** the main repository directory:
`/Users/kuldeeprathor/codes/backend/blackclap/ssot.{ENV}.env`

For example:
- **Development:** `/Users/kuldeeprathor/codes/backend/blackclap/ssot.development.env`
- **Staging:** `/Users/kuldeeprathor/codes/backend/blackclap/ssot.staging.env`
- **Production:** `/Users/kuldeeprathor/codes/backend/blackclap/ssot.production.env`

### Fallback Path
If no file is found at the external SSOT path, the project will automatically fall back to the local `.env` file in the root of the project workspace (`/Users/kuldeeprathor/codes/backend/blackclap/blackclap_backend/.env`).

---

## ⚡ Quick Start Guide

Follow these steps to set up and run your development environment.

### 1. Prerequisites
Ensure you have the following installed on your system:
- Python 3.10 or later
- Docker & Docker Compose

### 2. Dependency Setup
Create a Python virtual environment and install the backend package along with its development dependencies:

```bash
# Create virtual environment (from the project root directory)
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install the dependencies in editable/development mode
pip install -e .[dev]
```

### 3. Setup the External Environment File
Create the parent directory if necessary and initialize the development SSOT environment file:

```bash
# Copy the example file to the external SSOT path
cp .env.example ../ssot.development.env
```
*(Open `../ssot.development.env` and configure your Database URLs, Firebase Keys, and AWS configurations).*

### 4. Start Infrastructure (PostgreSQL & Redis)
Run Docker Compose in the background to spin up the local PostgreSQL database and Redis services:

```bash
docker compose up -d db redis
```

### 5. Apply Database Migrations
Run Alembic to apply existing migrations and update your database schema to the latest version:

```bash
ENV=development alembic upgrade head
```

---

## 🚀 Running the Services

Instead of running FastAPI and Celery in separate terminals manually, you can launch them concurrently using the provided startup script.

```bash
# Ensure virtual environment is active
source venv/bin/activate

# Start the services (API on port 8000 and Celery Worker)
ENV=development python3 scripts/start_services.py
```

### Configuration Options
You can customize the environment and the FastAPI port using shell variables:
- **Environment (`ENV`):** `development`, `staging`, or `production` (loads the corresponding `ssot.{ENV}.env` file). Default is `development`.
- **FastAPI Port (`PORT`):** The port on which the FastAPI API runs. Default is `8000`.

Example running on port `8080` in staging mode:
```bash
ENV=staging PORT=8080 python3 scripts/start_services.py
```

To stop all services cleanly, press `Ctrl+C` in the terminal where the script is running.

---

## 🛠️ Common Operations & Development Commands

### Database Migrations (Alembic)
Use these commands when making changes to database models:

```bash
# Generate a new migration file after modifying models
ENV=development alembic revision --autogenerate -m "describe_your_changes"

# Apply migrations
ENV=development alembic upgrade head

# Rollback the last migration
ENV=development alembic downgrade -1
```

### Linting and Formatting
To keep the codebase clean and adhering to project styling guidelines, run:

```bash
# Format code using Black
black app/ scripts/ tests/

# Run Ruff check to lint code and import ordering
ruff check app/ scripts/ tests/

# Auto-fix linting issues where possible
ruff check app/ scripts/ tests/ --fix
```

### Running Tests
To run unit and integration tests:

```bash
ENV=development pytest
```
