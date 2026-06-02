"""MentalHealthCounsellorService — CRUD for campus counsellor roster (§9.3)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import MentalHealthCounsellor
from durgam.repositories.mental_health_counsellor import (
    MentalHealthCounsellorRepository,
)
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class CounsellorError(OrgServiceError):
    pass


class MentalHealthCounsellorService:
    def __init__(self, repo: MentalHealthCounsellorRepository) -> None:
        self._repo = repo

    def list_by_ay_campus(
        self, academic_year_id: UUID, campus_id: UUID,
    ) -> list[MentalHealthCounsellor]:
        return self._repo.list_by_ay_campus(academic_year_id, campus_id)

    def create(
        self,
        *,
        academic_year_id: UUID,
        campus_id: UUID,
        name: str,
        qualification: str,
        specialisation: str,
        mode_of_appointment: str,
        appointment_start: date,
        appointment_end: date,
        actor_id: UUID,
        phone: str | None = None,
        email: str | None = None,
        appointment_letter_file_id: UUID | None = None,
        qualification_proof_file_id: UUID | None = None,
        display_order: int = 0,
    ) -> MentalHealthCounsellor:
        name = name.strip()
        if not name:
            raise CounsellorError("Counsellor name is required.")
        if appointment_end < appointment_start:
            raise CounsellorError("Appointment end date must be on or after start date.")
        if mode_of_appointment not in ("inhouse", "external"):
            raise CounsellorError("Mode of appointment must be inhouse or external.")

        now = datetime.now(UTC)
        record = MentalHealthCounsellor(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            name=name,
            qualification=qualification.strip(),
            specialisation=specialisation.strip(),
            mode_of_appointment=mode_of_appointment,
            appointment_start=appointment_start,
            appointment_end=appointment_end,
            phone=phone,
            email=email,
            appointment_letter_file_id=appointment_letter_file_id,
            qualification_proof_file_id=qualification_proof_file_id,
            display_order=display_order,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("counsellor_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> MentalHealthCounsellor:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise CounsellorError("Counsellor not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("counsellor_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> MentalHealthCounsellor:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise CounsellorError("Counsellor not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("counsellor_deleted", id=str(record_id), actor=str(actor_id))
        return record
