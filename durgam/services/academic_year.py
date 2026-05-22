"""AcademicYearService — CRUD, master-lock, and rollover for AcademicYear (§8.5 M4)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import AcademicYear
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.services.org_exceptions import AcademicYearLockedError, OrgServiceError

log = structlog.get_logger(__name__)

_CODE_RE = re.compile(r"^\d{4}-\d{2}$")


class AcademicYearError(OrgServiceError):
    pass


class AcademicYearService:
    def __init__(self, ay_repo: AcademicYearRepository) -> None:
        self._ays = ay_repo

    def list_all(self) -> list[AcademicYear]:
        return self._ays.list_active()

    def get(self, ay_id: UUID) -> AcademicYear:
        ay = self._ays.get_by_id(ay_id)
        if ay is None:
            raise AcademicYearError("Academic year not found.")
        return ay

    def create(
        self,
        code: str,
        starts_on: date,
        ends_on: date,
        actor_id: UUID,
    ) -> AcademicYear:
        code = code.strip()
        if not _CODE_RE.match(code):
            raise AcademicYearError("Code must be in YYYY-YY format (e.g. 2025-26).")
        if starts_on >= ends_on:
            raise AcademicYearError("Start date must be before end date.")
        if self._ays.get_by_code(code) is not None:
            raise AcademicYearError(f"Academic year '{code}' already exists.")
        now = datetime.now(UTC)
        ay = AcademicYear(
            code=code,
            starts_on=starts_on,
            ends_on=ends_on,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        ay = self._ays.save(ay)
        log.info("academic_year_created", code=code, actor=str(actor_id))
        return ay

    def update(self, ay_id: UUID, fields: dict, actor_id: UUID) -> AcademicYear:
        ay = self.get(ay_id)
        if ay.is_locked:
            raise AcademicYearLockedError()
        for key, value in fields.items():
            setattr(ay, key, value)
        ay.updated_by = actor_id
        ay = self._ays.save(ay)
        log.info("academic_year_updated", ay_id=str(ay_id), actor=str(actor_id))
        return ay

    def lock_master_calendar(self, ay_id: UUID, actor_id: UUID) -> AcademicYear:
        ay = self.get(ay_id)
        if ay.is_locked:
            raise AcademicYearLockedError()
        ay = self._ays.lock_master_calendar(ay_id)
        log.info("master_calendar_locked", ay_id=str(ay_id), actor=str(actor_id))
        return ay

    def lock_expired_academic_years(self, as_of: date | None = None) -> int:
        expired = self._ays.list_expired_unlocked(as_of)
        for ay in expired:
            self._ays.lock_for_rollover(ay.id)
            log.info("academic_year_locked_by_rollover", code=ay.code)
        return len(expired)
