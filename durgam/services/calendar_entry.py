"""CalendarEntryService — three-phase collaboration chain, ownership (§8.5, §9.3 M4).

Phase 1 — Registrar framework: sem_begin, sem_end, holiday, class_suspension, cie,
          end_sem_exam, admission_exam, phd_admission, winter_vacation, summer_vacation,
          academic_council_meeting, finance_committee_meeting, executive_committee_meeting.
          Creatable when AY is unlocked, before or after master_calendar_locked.

Phase 2 — IQAC: activity.
          Creatable when master_calendar_locked=True AND iqac_confirmed=False AND NOT is_locked.

Phase 3 — All others: sports, cultural (restricted roles), academic_activity,
          other_activity (any role except STUDENT/BASIC_USER).
          Creatable when iqac_confirmed=True AND NOT is_locked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import CalendarEntry
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.calendar_entry import CalendarEntryRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)

_REGISTRAR_ROLES = frozenset({"REGISTRAR", "DEPUTY_REGISTRAR", "REGISTRAR_OFFICE", "SYSTEM_ADMIN"})

PHASE1_TYPES = frozenset({
    "sem_begin", "sem_end", "holiday", "class_suspension", "cie",
    "end_sem_exam", "admission_exam", "phd_admission",
    "winter_vacation", "summer_vacation",
    "academic_council_meeting", "finance_committee_meeting",
    "executive_committee_meeting",
})

PHASE2_TYPES = frozenset({"activity"})

PHASE3_RESTRICTED_TYPES = frozenset({"sports", "cultural"})

PHASE3_GENERIC_TYPES = frozenset({"academic_activity", "other_activity"})

EXCLUDED_ROLES = frozenset({"STUDENT", "BASIC_USER"})

ENTRY_TYPE_ROLE_MAP: dict[str, frozenset[str]] = {
    # Phase 1 — Registrar framework
    "sem_begin": _REGISTRAR_ROLES,
    "sem_end": _REGISTRAR_ROLES,
    "holiday": _REGISTRAR_ROLES,
    "class_suspension": _REGISTRAR_ROLES,
    "cie": _REGISTRAR_ROLES,
    "end_sem_exam": _REGISTRAR_ROLES,
    "admission_exam": _REGISTRAR_ROLES,
    "phd_admission": _REGISTRAR_ROLES,
    "winter_vacation": _REGISTRAR_ROLES,
    "summer_vacation": _REGISTRAR_ROLES,
    "academic_council_meeting": _REGISTRAR_ROLES,
    "finance_committee_meeting": _REGISTRAR_ROLES,
    "executive_committee_meeting": _REGISTRAR_ROLES,
    # Phase 2 — IQAC
    "activity": frozenset({"IQAC_COORDINATOR"}),
    # Phase 3 — restricted
    "sports": frozenset({"DIRECTOR", "DEPUTY_DIRECTOR", "DIRECTOR_OFFICE", "DEAN_STUDENT_WELFARE"}),
    "cultural": frozenset({"DIRECTOR", "DEPUTY_DIRECTOR", "DIRECTOR_OFFICE", "DEAN_STUDENT_WELFARE"}),
    # Phase 3 — generic (empty set = any non-excluded role)
    "academic_activity": frozenset(),
    "other_activity": frozenset(),
}

VALID_ENTRY_TYPES = frozenset(ENTRY_TYPE_ROLE_MAP.keys())


class CalendarEntryError(OrgServiceError):
    pass


class CalendarEntryService:
    def __init__(
        self,
        entry_repo: CalendarEntryRepository,
        ay_repo: AcademicYearRepository,
    ) -> None:
        self._entries = entry_repo
        self._ays = ay_repo

    def list_by_ay(self, academic_year_id: UUID) -> list[CalendarEntry]:
        return self._entries.list_by_ay(academic_year_id)

    def list_by_ay_and_type(self, academic_year_id: UUID, entry_type: str) -> list[CalendarEntry]:
        return self._entries.list_by_ay_and_type(academic_year_id, entry_type)

    def list_by_ay_and_owner(self, academic_year_id: UUID, owner_user_id: UUID) -> list[CalendarEntry]:
        return self._entries.list_by_ay_and_owner(academic_year_id, owner_user_id)

    def create(
        self,
        academic_year_id: UUID,
        title: str,
        entry_type: str,
        starts_at: datetime,
        ends_at: datetime,
        owner_user_id: UUID,
        owner_role_code: str,
        actor_id: UUID,
        *,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
        notes: str | None = None,
    ) -> CalendarEntry:
        title = title.strip()
        if not title:
            raise CalendarEntryError("Title is required.")
        if entry_type not in VALID_ENTRY_TYPES:
            raise CalendarEntryError(f"Invalid entry type: {entry_type!r}.")
        if starts_at >= ends_at:
            raise CalendarEntryError("Start must be before end.")

        # Role check
        allowed_roles = ENTRY_TYPE_ROLE_MAP[entry_type]
        if allowed_roles:
            if owner_role_code not in allowed_roles:
                raise CalendarEntryError(
                    f"Role {owner_role_code!r} cannot create {entry_type!r} entries."
                )
        else:
            # Generic types: any role except STUDENT/BASIC_USER
            if owner_role_code in EXCLUDED_ROLES:
                raise CalendarEntryError(
                    f"Role {owner_role_code!r} cannot create calendar entries."
                )

        ay = self._ays.get_by_id(academic_year_id)
        if ay is None:
            raise CalendarEntryError("Academic year not found.")

        # Phase gating
        if entry_type in PHASE1_TYPES:
            pass  # Phase 1: only needs AY unlocked (repo enforces)
        elif entry_type in PHASE2_TYPES:
            if not ay.master_calendar_locked:
                raise CalendarEntryError(
                    "The Registrar must confirm the master calendar before IQAC entries can be added."
                )
            if ay.iqac_confirmed:
                raise CalendarEntryError(
                    "IQAC has already confirmed. No further IQAC entries can be added."
                )
        elif entry_type in PHASE3_RESTRICTED_TYPES or entry_type in PHASE3_GENERIC_TYPES:
            if not ay.iqac_confirmed:
                raise CalendarEntryError(
                    "IQAC must confirm before other entries can be added."
                )

        now = datetime.now(UTC)
        entry = CalendarEntry(
            academic_year_id=academic_year_id,
            title=title,
            entry_type=entry_type,
            starts_at=starts_at,
            ends_at=ends_at,
            owner_user_id=owner_user_id,
            owner_role_code=owner_role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        entry = self._entries.save(entry)
        log.info(
            "calendar_entry_created",
            entry_id=str(entry.id),
            entry_type=entry_type,
            actor=str(actor_id),
        )
        return entry

    def update(
        self,
        entry_id: UUID,
        fields: dict,
        actor_user_id: UUID,
        actor_id: UUID,
    ) -> CalendarEntry:
        entry = self._entries.get_by_id(entry_id)
        if entry is None:
            raise CalendarEntryError("Calendar entry not found.")
        if entry.owner_user_id != actor_user_id:
            raise CalendarEntryError("Only the entry owner can edit this entry.")
        for key, value in fields.items():
            setattr(entry, key, value)
        entry.updated_by = actor_id
        entry = self._entries.save(entry)
        log.info("calendar_entry_updated", entry_id=str(entry_id), actor=str(actor_id))
        return entry

    def soft_delete(
        self,
        entry_id: UUID,
        actor_user_id: UUID,
        actor_id: UUID,
    ) -> CalendarEntry:
        entry = self._entries.get_by_id(entry_id)
        if entry is None:
            raise CalendarEntryError("Calendar entry not found.")
        if entry.owner_user_id != actor_user_id:
            raise CalendarEntryError("Only the entry owner can delete this entry.")
        entry = self._entries.soft_delete(entry, actor_id)
        log.info("calendar_entry_deleted", entry_id=str(entry_id), actor=str(actor_id))
        return entry
