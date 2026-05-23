"""Nightly task to lock expired academic years."""

from __future__ import annotations

from datetime import date

import structlog
from sqlmodel import select

from durgam.db import open_session
from durgam.models.config_anchors import AcademicYear
from durgam.tasks.celery_app import app

log = structlog.get_logger(__name__)


@app.task(name="durgam.tasks.ay_rollover.lock_expired_academic_years")
def lock_expired_academic_years() -> dict:
    today = date.today()
    locked_codes: list[str] = []

    with open_session() as session:
        expired_unlocked = session.exec(
            select(AcademicYear).where(
                AcademicYear.ends_on < today,
                AcademicYear.is_locked == False,  # noqa: E712
                AcademicYear.is_deleted == False,  # noqa: E712
            )
        ).all()

        for ay in expired_unlocked:
            ay.is_locked = True
            session.add(ay)
            locked_codes.append(ay.code)
            log.info("ay_rollover_locked", code=ay.code, ends_on=str(ay.ends_on))

        if locked_codes:
            session.commit()

    if not locked_codes:
        log.info("ay_rollover_noop", today=str(today))

    return {"locked": locked_codes, "date": str(today)}
