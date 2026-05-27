"""PurchaseCommitteeTemplateService — CRUD for standing committee composition (E-007).

M7/M10 forward-concern: rank-preference enforcement, availability/fatigue
checks, and justification capture are M7 RUNTIME — they require the Faculty
model (M10) for who-exists/who's-available and a purchase-request artifact
(M7) for the justification. M5b stores the ranked policy ONLY.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import PurchaseCommitteeTemplate
from durgam.repositories.purchase_committee_template import (
    PurchaseCommitteeTemplateRepository,
)
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)

_VALID_COMMITTEE_TYPES = ("campus_purchase_committee", "central_purchase_committee")
_VALID_TOPOLOGIES = ("concurrent", "sequential")
_VALID_EXPERT_MODES = ("guest_user", "proxied_with_proof")


class PurchaseCommitteeTemplateError(OrgServiceError):
    pass


class PurchaseCommitteeTemplateService:
    def __init__(self, repo: PurchaseCommitteeTemplateRepository) -> None:
        self._repo = repo

    def list_all(self) -> list[PurchaseCommitteeTemplate]:
        return self._repo.list_all_active()

    def create(
        self,
        *,
        committee_type: str,
        eligible_designations: list[str],
        faculty_member_count: int,
        members_from_different_departments: bool,
        fixed_role_members: list[str],
        director_excluded: bool = False,
        escalation_designate_role_code: str | None = None,
        external_expert_mode: str = "proxied_with_proof",
        topology: str = "concurrent",
        actor_id: UUID,
        notes: str | None = None,
    ) -> PurchaseCommitteeTemplate:
        committee_type = committee_type.strip()
        self._validate(
            committee_type, eligible_designations, faculty_member_count,
            topology, external_expert_mode,
        )

        now = datetime.now(UTC)
        record = PurchaseCommitteeTemplate(
            committee_type=committee_type,
            eligible_designations=eligible_designations,
            faculty_member_count=faculty_member_count,
            members_from_different_departments=members_from_different_departments,
            fixed_role_members=fixed_role_members,
            director_excluded=director_excluded,
            escalation_designate_role_code=escalation_designate_role_code,
            external_expert_mode=external_expert_mode,
            topology=topology,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("purchase_committee_template_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> PurchaseCommitteeTemplate:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise PurchaseCommitteeTemplateError("Purchase committee template not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("purchase_committee_template_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> PurchaseCommitteeTemplate:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise PurchaseCommitteeTemplateError("Purchase committee template not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("purchase_committee_template_deleted", id=str(record_id), actor=str(actor_id))
        return record

    def _validate(
        self,
        committee_type: str,
        eligible_designations: list[str],
        faculty_member_count: int,
        topology: str,
        external_expert_mode: str,
    ) -> None:
        if committee_type not in _VALID_COMMITTEE_TYPES:
            raise PurchaseCommitteeTemplateError(
                f"Committee type must be one of: {', '.join(_VALID_COMMITTEE_TYPES)}."
            )
        if not eligible_designations:
            raise PurchaseCommitteeTemplateError(
                "At least one eligible designation is required."
            )
        if faculty_member_count < 1:
            raise PurchaseCommitteeTemplateError(
                "Faculty member count must be 1 or greater."
            )
        if topology not in _VALID_TOPOLOGIES:
            raise PurchaseCommitteeTemplateError(
                f"Topology must be one of: {', '.join(_VALID_TOPOLOGIES)}."
            )
        if external_expert_mode not in _VALID_EXPERT_MODES:
            raise PurchaseCommitteeTemplateError(
                f"External expert mode must be one of: {', '.join(_VALID_EXPERT_MODES)}."
            )
