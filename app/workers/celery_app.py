from celery import Celery
from celery.schedules import crontab

from app.core.config.settings import settings

celery_app = Celery(
    "blackclap_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",  # India-first target timezone
    enable_utc=True,
    task_track_started=True,
)

# Periodic jobs (run by `celery -A app.workers.celery_app beat`).
celery_app.conf.beat_schedule = {
    # Permanently purge/anonymize accounts past the soft-delete grace period.
    "purge-deleted-accounts-daily": {
        "task": "account.purge_deleted_accounts",
        "schedule": crontab(hour=3, minute=0),  # daily at 03:00 (Asia/Kolkata)
    },
}

# Autodiscover tasks from registered modules and worker tasks
celery_app.autodiscover_tasks(
    [
        "app.workers",
    ],
    force=True,
)
