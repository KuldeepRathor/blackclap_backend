"""Celery task modules. Imported here so autodiscover registers the tasks."""

from app.workers.tasks.account_purge import purge_deleted_accounts

__all__ = ["purge_deleted_accounts"]
