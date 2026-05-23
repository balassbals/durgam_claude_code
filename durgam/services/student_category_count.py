"""StudentCategoryCountService — per-AY singleton CRUD (§8.5 M4)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import StudentCategoryCount
from durgam.repositories.student_category_count import StudentCategoryCountRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)

_COUNT_FIELDS = frozenset({"sc_count", "st_count", "obc_count", "ews_count", "general_count"})


class StudentCategoryCountError(OrgServiceError):
    pass


class StudentCategoryCountService:
    def __init__(self, scc_repo: StudentCategoryCountRepository) -> None:
        self._sccs = scc_repo

    def get_by_ay(self, academic_year_id: UUID) -> StudentCategoryCount | None:
        return self._sccs.get_by_ay(academic_year_id)

    def get_or_create_by_ay(
        self,
        academic_year_id: UUID,
        actor_id: UUID,
    ) -> StudentCategoryCount:
        existing = self._sccs.get_by_ay(academic_year_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        scc = StudentCategoryCount(
            academic_year_id=academic_year_id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        scc = self._sccs.save(scc)
        log.info("student_category_count_created", ay_id=str(academic_year_id), actor=str(actor_id))
        return scc

    def update(
        self,
        scc_id: UUID,
        fields: dict,
        actor_id: UUID,
    ) -> StudentCategoryCount:
        scc = self._sccs.get_by_id(scc_id)
        if scc is None:
            raise StudentCategoryCountError("Student category count not found.")
        for key, value in fields.items():
            if key in _COUNT_FIELDS:
                if not isinstance(value, int) or value < 0:
                    raise StudentCategoryCountError(
                        f"Count field '{key}' must be a non-negative integer."
                    )
            setattr(scc, key, value)
        scc.updated_by = actor_id
        scc = self._sccs.save(scc)
        log.info("student_category_count_updated", scc_id=str(scc_id), actor=str(actor_id))
        return scc
