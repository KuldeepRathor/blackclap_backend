from celery import Celery

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

# Autodiscover tasks from registered modules and worker tasks
celery_app.autodiscover_tasks(
    [
        "app.workers",
    ],
    force=True,
)
