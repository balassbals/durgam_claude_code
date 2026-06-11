"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from durgam.config import settings

app = Celery(
    "durgam",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["durgam.tasks.ay_rollover", "durgam.tasks.leave_jobs"],
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
        "leave-forfeit-late-cl": {
            "task": "durgam.tasks.leave_jobs.forfeit_late_cl",
            "schedule": crontab(hour=0, minute=30),
        },
        "leave-lapse-unavailed-cl": {
            "task": "durgam.tasks.leave_jobs.lapse_unavailed_cl",
            "schedule": crontab(month_of_year=12, day_of_month=31, hour=23, minute=0),
        },
        "leave-credit-el-hpl-jan": {
            "task": "durgam.tasks.leave_jobs.credit_periodic_el_hpl",
            "schedule": crontab(month_of_year=1, day_of_month=1, hour=2, minute=0),
        },
        "leave-credit-el-hpl-jul": {
            "task": "durgam.tasks.leave_jobs.credit_periodic_el_hpl",
            "schedule": crontab(month_of_year=7, day_of_month=1, hour=2, minute=0),
        },
        "leave-check-overstay": {
            "task": "durgam.tasks.leave_jobs.check_overstay",
            "schedule": crontab(hour=1, minute=0),
        },
        # M8.1 TD-036: credit annual CL entitlement on Jan 1 at 03:00 UTC.
        # Beat schedule is hardcoded here; see TD-040 for DB-driven scheduling.
        "leave-credit-annual-cl": {
            "task": "durgam.tasks.leave_jobs.credit_annual_cl",
            "schedule": crontab(hour=3, minute=0, day_of_month=1, month_of_year=1),
        },
    },
)
