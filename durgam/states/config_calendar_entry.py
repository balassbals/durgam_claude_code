"""CalendarEntryConfigState — AY-scoped calendar with three-phase collaboration chain."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import reflex as rx
import structlog
from sqlmodel import select

log = structlog.get_logger(__name__)

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.models.identity import Role, UserRole
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.calendar_entry import CalendarEntryRepository
from durgam.services.calendar_entry import (
    CalendarEntryError,
    CalendarEntryService,
    ENTRY_TYPE_ROLE_MAP,
    EXCLUDED_ROLES,
    PHASE1_TYPES,
    PHASE2_TYPES,
    PHASE3_GENERIC_TYPES,
    PHASE3_RESTRICTED_TYPES,
    VALID_ENTRY_TYPES,
)
from durgam.services.calendar_export import CalendarExportService
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.states.base import BaseState


def _svc(session) -> CalendarEntryService:
    return CalendarEntryService(
        entry_repo=CalendarEntryRepository(session),
        ay_repo=AcademicYearRepository(session),
    )


_TYPE_LABELS: dict[str, str] = {
    "sem_begin": "Semester Begin",
    "sem_end": "Semester End",
    "holiday": "Holiday",
    "class_suspension": "Class Suspension",
    "cie": "CIE",
    "end_sem_exam": "End Semester Exam",
    "admission_exam": "Admission Exam",
    "phd_admission": "PhD Admission",
    "winter_vacation": "Winter Vacation",
    "summer_vacation": "Summer Vacation",
    "academic_council_meeting": "Academic Council Meeting",
    "finance_committee_meeting": "Finance Committee Meeting",
    "executive_committee_meeting": "Executive Committee Meeting",
    "activity": "Activity (IQAC)",
    "sports": "Sports",
    "cultural": "Cultural",
    "academic_activity": "Academic Activity",
    "other_activity": "Other Activity",
}


class CalendarEntryConfigState(BaseState):
    # AY selector
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False
    master_calendar_locked: bool = False
    iqac_confirmed: bool = False
    can_configure_ay: bool = False
    can_confirm_iqac: bool = False

    # User's calendar-owning roles: [{code, scope_type, scope_id}]
    _user_roles: list[dict[str, str]] = []

    # Entry type options available to this user (phase-aware)
    allowed_type_options: list[dict[str, str]] = []

    # Filters ("all" = no filter)
    filter_type: str = "all"
    filter_date_from: str = ""
    filter_date_to: str = ""
    filter_owner_role: str = "all"
    owner_role_options: list[dict[str, str]] = []

    # List
    entries: list[dict[str, str]] = []
    loading: bool = True

    # Form
    show_form: bool = False
    editing_id: str = ""
    form_title: str = ""
    form_entry_type: str = ""
    form_starts_at: str = ""
    form_ends_at: str = ""
    form_notes: str = ""

    # Confirmation dialog
    confirm_open: bool = False
    confirm_entry_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    # Lock master calendar confirmation
    lock_confirm_open: bool = False
    # IQAC confirm confirmation
    iqac_confirm_open: bool = False

    async def load_entries(self) -> None:
        guard = self._config_guard("calendar_entry", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.entries = []
        self.show_form = False
        self.ay_options = []
        self._user_roles = []
        self.allowed_type_options = []

        with open_session() as session:
            ay_repo = AcademicYearRepository(session)
            for ay in ay_repo.list_active():
                self.ay_options.append({
                    "value": str(ay.id),
                    "label": ay.code,
                    "is_locked": "1" if ay.is_locked else "0",
                    "master_locked": "1" if ay.master_calendar_locked else "0",
                    "iqac_confirmed": "1" if ay.iqac_confirmed else "0",
                })
            if self.ay_options and not self.selected_ay_id:
                self.selected_ay_id = self.ay_options[0]["value"]

            self._load_user_roles(session)
            self._compute_allowed_types()

            from durgam.auth.permissions import can
            self.can_configure_ay = can(
                UUID(self.current_user_id), "configure", "academic_year",
                None, None, session,
            )
            # IQAC confirm: user must be IQAC_COORDINATOR
            user_role_codes = {r["code"] for r in self._user_roles}
            self.can_confirm_iqac = "IQAC_COORDINATOR" in user_role_codes

            self._load_entries_for_ay(session)

        self._load_nav_entries()
        self.loading = False

    def _load_user_roles(self, session) -> None:
        self._user_roles = []
        if not self.current_user_id:
            return
        user_id = UUID(self.current_user_id)
        ur_rows = session.exec(
            select(UserRole, Role)
            .join(Role, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        ).all()
        for ur, role in ur_rows:
            self._user_roles.append({
                "code": role.code,
                "scope_type": ur.scope_type or "",
                "scope_id": str(ur.scope_id) if ur.scope_id else "",
            })

    def _compute_allowed_types(self) -> None:
        user_role_codes = {r["code"] for r in self._user_roles}
        self.allowed_type_options = []
        for entry_type in VALID_ENTRY_TYPES:
            allowed_roles = ENTRY_TYPE_ROLE_MAP[entry_type]
            if allowed_roles:
                if allowed_roles & user_role_codes:
                    self.allowed_type_options.append({
                        "value": entry_type,
                        "label": _TYPE_LABELS.get(entry_type, entry_type),
                    })
            else:
                # Generic types: any role except STUDENT/BASIC_USER
                if user_role_codes - EXCLUDED_ROLES:
                    self.allowed_type_options.append({
                        "value": entry_type,
                        "label": _TYPE_LABELS.get(entry_type, entry_type),
                    })
        self.allowed_type_options.sort(key=lambda o: o["label"])

    def _resolve_role_for_type(self, entry_type: str) -> dict[str, str] | None:
        allowed_roles = ENTRY_TYPE_ROLE_MAP[entry_type]
        if allowed_roles:
            user_role_codes = {r["code"] for r in self._user_roles}
            matching_codes = allowed_roles & user_role_codes
            if not matching_codes:
                return None
            code = next(iter(matching_codes))
            for r in self._user_roles:
                if r["code"] == code:
                    return r
            return None
        else:
            # Generic types: use first non-excluded role
            for r in self._user_roles:
                if r["code"] not in EXCLUDED_ROLES:
                    return r
            return None

    def _load_entries_for_ay(self, session) -> None:
        self.entries = []
        self.owner_role_options = []
        if not self.selected_ay_id:
            self.ay_is_locked = False
            self.master_calendar_locked = False
            self.iqac_confirmed = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False
        self.master_calendar_locked = ay.master_calendar_locked if ay else False
        self.iqac_confirmed = ay.iqac_confirmed if ay else False

        svc = _svc(session)
        all_entries = svc.list_by_ay(UUID(self.selected_ay_id))

        seen_roles: set[str] = set()
        for e in all_entries:
            if e.owner_role_code not in seen_roles:
                seen_roles.add(e.owner_role_code)
                self.owner_role_options.append({
                    "value": e.owner_role_code,
                    "label": e.owner_role_code,
                })
        self.owner_role_options.sort(key=lambda o: o["label"])

        from datetime import date as date_type
        filter_date_from: date_type | None = None
        filter_date_to: date_type | None = None
        if self.filter_date_from:
            try:
                filter_date_from = date_type.fromisoformat(self.filter_date_from)
            except ValueError:
                pass
        if self.filter_date_to:
            try:
                filter_date_to = date_type.fromisoformat(self.filter_date_to)
            except ValueError:
                pass

        current_user_id = self.current_user_id
        for e in all_entries:
            if self.filter_type and self.filter_type != "all":
                if e.entry_type != self.filter_type:
                    continue
            entry_start_date = e.starts_at.date()
            if filter_date_from and entry_start_date < filter_date_from:
                continue
            if filter_date_to and entry_start_date > filter_date_to:
                continue
            if self.filter_owner_role and self.filter_owner_role != "all":
                if e.owner_role_code != self.filter_owner_role:
                    continue

            self.entries.append({
                "id": str(e.id),
                "title": e.title,
                "type": _TYPE_LABELS.get(e.entry_type, e.entry_type),
                "type_raw": e.entry_type,
                "starts_at": e.starts_at.strftime("%Y-%m-%d %H:%M"),
                "ends_at": e.ends_at.strftime("%Y-%m-%d %H:%M"),
                "owner_role": e.owner_role_code,
                "owner_user_id": str(e.owner_user_id),
                "is_owner": "1" if str(e.owner_user_id) == current_user_id else "0",
                "notes": e.notes or "",
            })

    async def on_ay_change(self, value: str) -> None:
        self.selected_ay_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_entries_for_ay(session)
        matched = [o for o in self.ay_options if o["value"] == value]
        if matched:
            self.ay_is_locked = matched[0]["is_locked"] == "1"
            self.master_calendar_locked = matched[0]["master_locked"] == "1"
            self.iqac_confirmed = matched[0]["iqac_confirmed"] == "1"

    async def on_filter_type_change(self, value: str) -> None:
        self.filter_type = value
        with open_session() as session:
            self._load_entries_for_ay(session)

    async def on_filter_date_from_change(self, value: str) -> None:
        self.filter_date_from = value
        with open_session() as session:
            self._load_entries_for_ay(session)

    async def on_filter_date_to_change(self, value: str) -> None:
        self.filter_date_to = value
        with open_session() as session:
            self._load_entries_for_ay(session)

    async def on_filter_owner_role_change(self, value: str) -> None:
        self.filter_owner_role = value
        with open_session() as session:
            self._load_entries_for_ay(session)

    async def clear_filters(self) -> None:
        self.filter_type = "all"
        self.filter_date_from = ""
        self.filter_date_to = ""
        self.filter_owner_role = "all"
        with open_session() as session:
            self._load_entries_for_ay(session)

    # ── Form handlers ──────────────────────────────────────────────────────

    def set_form_title(self, v: str) -> None:
        self.form_title = v

    def set_form_entry_type(self, v: str) -> None:
        self.form_entry_type = v

    def set_form_starts_at(self, v: str) -> None:
        self.form_starts_at = v

    def set_form_ends_at(self, v: str) -> None:
        self.form_ends_at = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def _phase_eligible_types(self) -> list[str]:
        """Return the subset of allowed_type_options that the current phase permits."""
        eligible = []
        for opt in self.allowed_type_options:
            t = opt["value"]
            if t in PHASE1_TYPES:
                eligible.append(t)
            elif t in PHASE2_TYPES:
                if self.master_calendar_locked and not self.iqac_confirmed:
                    eligible.append(t)
            elif t in PHASE3_RESTRICTED_TYPES or t in PHASE3_GENERIC_TYPES:
                if self.iqac_confirmed:
                    eligible.append(t)
        return eligible

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        if self.ay_is_locked:
            self.flash = "This academic year is locked. No entries can be added."
            self.flash_type = "error"
            return
        if not self._phase_eligible_types():
            user_types = {o["value"] for o in self.allowed_type_options}
            has_phase2 = bool(user_types & PHASE2_TYPES)
            if has_phase2 and not self.master_calendar_locked:
                self.flash = (
                    "The Registrar must confirm the master calendar "
                    "before you can add activities."
                )
            else:
                self.flash = (
                    "The calendar is not yet open for entries. "
                    "You'll be able to add your entries once IQAC "
                    "confirms the calendar."
                )
            self.flash_type = "error"
            return
        self.editing_id = ""
        self.form_title = ""
        self.form_entry_type = ""
        self.form_starts_at = ""
        self.form_ends_at = ""
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self, entry_id: str, title: str, entry_type: str,
        starts_at: str, ends_at: str, notes: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = entry_id
        self.form_title = title
        self.form_entry_type = entry_type
        self.form_starts_at = starts_at.replace(" ", "T")
        self.form_ends_at = ends_at.replace(" ", "T")
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.form_title = ""
        self.form_entry_type = ""
        self.form_starts_at = ""
        self.form_ends_at = ""
        self.form_notes = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="calendar_entry")
    @audit_action(action="write", resource="calendar_entry")
    async def save_entry(self, form_data: dict) -> None:
        title = form_data.get("form_title", "").strip()
        entry_type = form_data.get("form_entry_type", "").strip()
        starts_at_raw = form_data.get("form_starts_at", "").strip()
        ends_at_raw = form_data.get("form_ends_at", "").strip()
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        if not title:
            self.flash = "Title is required."
            self.flash_type = "error"
            return
        if not entry_type:
            self.flash = "Entry type is required."
            self.flash_type = "error"
            return
        if not starts_at_raw or not ends_at_raw:
            self.flash = "Start and end date/time are required."
            self.flash_type = "error"
            return

        try:
            starts_at = datetime.fromisoformat(starts_at_raw)
            ends_at = datetime.fromisoformat(ends_at_raw)
        except ValueError:
            self.flash = "Invalid date/time format."
            self.flash_type = "error"
            return

        role_info = self._resolve_role_for_type(entry_type)
        if role_info is None:
            self.flash = f"You do not have a role that can create {entry_type!r} entries."
            self.flash_type = "error"
            return

        scope_type = role_info["scope_type"] if role_info["scope_type"] else None
        scope_id = UUID(role_info["scope_id"]) if role_info["scope_id"] else None

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        academic_year_id=UUID(self.selected_ay_id),
                        title=title,
                        entry_type=entry_type,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        owner_user_id=actor_id,
                        owner_role_code=role_info["code"],
                        actor_id=actor_id,
                        scope_type=scope_type,
                        scope_id=scope_id,
                        notes=notes,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {"title": title, "starts_at": starts_at, "ends_at": ends_at, "notes": notes},
                        actor_user_id=actor_id,
                        actor_id=actor_id,
                    )
                session.commit()
        except (CalendarEntryError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_entries()
        self.flash = "Calendar entry saved."
        self.flash_type = "success"

    # ── Delete ─────────────────────────────────────────────────────────────

    def open_delete_confirm(self, entry_id: str, title: str) -> None:
        self.confirm_entry_id = entry_id
        self.confirm_title = f"Delete '{title}'?"
        self.confirm_body = "This will remove the calendar entry."
        self.confirm_open = True

    @require_role(action="write", resource="calendar_entry")
    @audit_action(action="delete", resource="calendar_entry")
    async def soft_delete_entry(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_entry_id),
                    actor_user_id=UUID(self.current_user_id),
                    actor_id=UUID(self.current_user_id),
                )
                session.commit()
        except (CalendarEntryError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_entry_id = ""
            return
        self.confirm_open = False
        self.confirm_entry_id = ""
        await self.load_entries()
        self.flash = "Calendar entry deleted."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_entry_id = ""

    # ── Export ─────────────────────────────────────────────────────────────

    def _get_ay_code(self) -> str:
        for o in self.ay_options:
            if o["value"] == self.selected_ay_id:
                return o["label"]
        return "calendar"

    @require_role(action="read", resource="calendar_entry")
    async def export_csv(self):
        return self._do_export("csv")

    @require_role(action="read", resource="calendar_entry")
    async def export_excel(self):
        return self._do_export("excel")

    @require_role(action="read", resource="calendar_entry")
    async def export_pdf(self):
        return self._do_export("pdf")

    @require_role(action="read", resource="calendar_entry")
    async def export_docx(self):
        return self._do_export("docx")

    def _do_export(self, fmt: str):
        if not self.selected_ay_id:
            self.flash = "Select an academic year first."
            self.flash_type = "error"
            return
        with open_session() as session:
            svc = _svc(session)
            entries_raw = svc.list_by_ay(UUID(self.selected_ay_id))
            ay_code = self._get_ay_code()

        export_svc = CalendarExportService()
        ext_map = {
            "csv": "csv",
            "excel": "xlsx",
            "pdf": "pdf",
            "docx": "docx",
        }
        ext = ext_map[fmt]
        method = getattr(export_svc, f"export_{fmt}")
        data = method(entries_raw, ay_code)
        filename = f"calendar_{ay_code}.{ext}"
        return rx.download(data=data, filename=filename)

    # ── Lock Master Calendar ───────────────────────────────────────────────

    def open_lock_master_confirm(self) -> None:
        ay_code = self._get_ay_code()
        self.lock_confirm_open = True
        self.confirm_title = f"Confirm Registrar calendar for '{ay_code}'?"
        self.confirm_body = (
            "Once confirmed, the Registrar framework calendar is finalized. "
            "IQAC can then add their activity entries. "
            "This action cannot be undone."
        )

    def cancel_lock_master(self) -> None:
        self.lock_confirm_open = False

    @require_role(action="configure", resource="academic_year")
    @audit_action(action="configure", resource="academic_year")
    async def lock_master_calendar(self) -> None:
        try:
            with open_session() as session:
                ay_repo = AcademicYearRepository(session)
                from durgam.services.academic_year import AcademicYearService
                ay_svc = AcademicYearService(ay_repo=ay_repo)
                ay_svc.lock_master_calendar(
                    UUID(self.selected_ay_id), UUID(self.current_user_id)
                )
                session.commit()
        except Exception as e:
            self.flash = str(e)
            self.flash_type = "error"
            self.lock_confirm_open = False
            return
        self.lock_confirm_open = False
        ay_code = self._get_ay_code()
        try:
            from durgam.notifications.calendar_emails import send_registrar_confirmed_email
            asyncio.create_task(send_registrar_confirmed_email(ay_code))
        except Exception:
            log.exception("calendar_email_registrar_confirm_failed", ay_code=ay_code)
        await self.load_entries()
        self.flash = "Registrar calendar confirmed. IQAC may now add activity entries."
        self.flash_type = "success"

    # ── IQAC Confirm ───────────────────────────────────────────────────────

    def open_iqac_confirm(self) -> None:
        ay_code = self._get_ay_code()
        self.iqac_confirm_open = True
        self.confirm_title = f"Confirm IQAC calendar for '{ay_code}'?"
        self.confirm_body = (
            "Once confirmed, IQAC activity entries are finalized. "
            "Directors, Deans, HoDs, and other roles can then add their entries. "
            "This action cannot be undone."
        )

    def cancel_iqac_confirm(self) -> None:
        self.iqac_confirm_open = False

    @require_role(action="write", resource="calendar_entry")
    @audit_action(action="configure", resource="academic_year")
    async def confirm_iqac(self) -> None:
        try:
            with open_session() as session:
                ay_repo = AcademicYearRepository(session)
                from durgam.services.academic_year import AcademicYearService
                ay_svc = AcademicYearService(ay_repo=ay_repo)
                ay_svc.confirm_iqac(
                    UUID(self.selected_ay_id), UUID(self.current_user_id)
                )
                session.commit()
        except Exception as e:
            self.flash = str(e)
            self.flash_type = "error"
            self.iqac_confirm_open = False
            return
        self.iqac_confirm_open = False
        ay_code = self._get_ay_code()
        try:
            from durgam.notifications.calendar_emails import send_iqac_confirmed_email
            asyncio.create_task(send_iqac_confirmed_email(ay_code))
        except Exception:
            log.exception("calendar_email_iqac_confirm_failed", ay_code=ay_code)
        await self.load_entries()
        self.flash = "IQAC calendar confirmed. All other roles may now add entries."
        self.flash_type = "success"
