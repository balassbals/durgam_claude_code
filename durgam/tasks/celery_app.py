"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from durgam.config import settings

app = Celery(
    "durgam",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["durgam.tasks.ay_rollover"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "lock-expired-academic-years": {
            "task": "durgam.tasks.ay_rollover.lock_expired_academic_years",
            "schedule": crontab(hour=1, minute=0),
        },
    },
)
