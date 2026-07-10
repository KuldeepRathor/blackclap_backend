FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and setup files
COPY pyproject.toml /app/

# Create a dummy structure so pip install -e . doesn't fail
RUN mkdir -p /app/app && touch /app/app/__init__.py

# Install dependencies
RUN pip install --no-cache-dir -e .[dev]

# Copy the rest of the project
COPY . /app/

# Expose port
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--proxy-headers", "--forwarded-allow-ips=*"]
