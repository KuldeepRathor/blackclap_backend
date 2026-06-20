import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine target environment from 'ENV' environment variable
env_name = os.getenv("ENV", "development")

# Default env file path is local '.env'
env_file_path = ".env"

# Compute absolute path to parent directory of the project
# File location: app/core/config/settings.py
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
parent_dir = os.path.dirname(project_root)

# Target SSOT file path in parent directory:
# /Users/kuldeeprathor/codes/backend/blackclap/ssot.{ENV}.env
ssot_env_file = os.path.join(parent_dir, f"ssot.{env_name}.env")

if os.path.exists(ssot_env_file):
    env_file_path = ssot_env_file
else:
    # Check if the SSOT env file exists in project root as a secondary fallback
    project_ssot_env = os.path.join(project_root, f"ssot.{env_name}.env")
    if os.path.exists(project_ssot_env):
        env_file_path = project_ssot_env

print(f"[*] Config: Loading env file from {env_file_path}")


class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "BlackClap"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/blackclap"

    # Firebase
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_PATH: Optional[str] = None

    # JWT Security Config
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = None
    AZURE_POST_MEDIA_CONTAINER: str = "post-media"
    AZURE_PROFILE_CONTAINER: str = "profile-images"
    AZURE_THUMBNAIL_CONTAINER: str = "thumbnails"
    AZURE_TEMP_CONTAINER: str = "temp"
    AZURE_SAS_EXPIRY_MINUTES: int = 15

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    model_config = SettingsConfigDict(env_file=env_file_path, extra="ignore")


settings = Settings()
