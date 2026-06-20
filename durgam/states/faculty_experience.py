"""FacultyExperienceState — experience CRUD for /faculty/profile/experience (M10 Phase P3b).

Mirrors FacultyEducationState (P3a) with P3a.1 modal-close pattern baked in.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import reflex as rx

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import (
    ExperienceNotFoundError,
    FacultyNotFoundError,
    FacultyService,
    InvalidDateError,
    NotOwnerError,
)
from durgam.states.base import BaseState


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


def _build_svc(session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


class FacultyExperienceState(BaseState):
    loading: bool = True
    faculty_id: str = ""
    has_faculty_record: bool = False
    records: list[dict] = []

    # Form state
    show_form: bool = False
    form_exp_id: str = ""
    form_organization: str = ""
    form_designation_held: str = ""
    form_from_date_str: str = ""
    form_to_date_str: str = ""
    form_responsibilities: str = ""

    # Delete confirm
    show_delete_confirm: bool = False
    deleting_id: str = ""
    deleting_organization: str = ""

    # ── Setters ──────────────────────────────────────────────────────────────

    def set_form_organization(self, v: str) -> None:
        self.form_organization = v

    def set_form_designation_held(self, v: str) -> None:
        self.form_designation_held = v

    def set_form_from_date_str(self, v: str) -> None:
        self.form_from_date_str = v

    def set_form_to_date_str(self, v: str) -> None:
        self.form_to_date_str = v

    def set_form_responsibilities(self, v: str) -> None:
        self.form_responsibilities = v

    # ── Modal open / close helpers ────────────────────────────────────────────

    def _clear_form(self) -> None:
        self.form_exp_id = ""
        self.form_organization = ""
        self.form_designation_held = ""
        self.form_from_date_str = ""
        self.form_to_date_str = ""
        self.form_responsibilities = ""

    def open_create_modal(self) -> None:
        self._clear_form()
        self.show_form = True

    def open_edit_by_id(self, exp_id: str) -> None:
        self._clear_form()
        self.form_exp_id = exp_id
        for r in self.records:
            if r["id"] == exp_id:
                self.form_organization = r.get("organization", "")
                self.form_designation_held = r.get("designation_held", "")
                self.form_from_date_str = r.get("from_date", "")
                self.form_to_date_str = r.get("to_date", "")
                self.form_responsibilities = r.get("responsibilities", "")
                break
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self._clear_form()

    def open_delete_confirm_by_id(self, exp_id: str) -> None:
        self.deleting_id = exp_id
        self.deleting_organization = ""
        for r in self.records:
            if r["id"] == exp_id:
                self.deleting_organization = r.get("organization", "")
                break
        self.show_delete_confirm = True

    def cancel_delete(self) -> None:
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_organization = ""

    # ── On-load ───────────────────────────────────────────────────────────────

    async def load_experience(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.loading = True
        self.records = []
        self.has_faculty_record = False
        self.faculty_id = ""
        self._load_nav_entries()

        with open_session() as session:
            repo = FacultyRepository(session)
            faculty = repo.get_by_user_id(UUID(self.current_user_id))
            if faculty is None:
                self.loading = False
                self.has_faculty_record = False
                return

            self.has_faculty_record = True
            self.faculty_id = str(faculty.id)

            svc = _build_svc(session)
            exp_list = svc.list_experience(faculty.id)
            self.records = [
                {
                    "id": str(e.id),
                    "organization": e.organization,
                    "designation_held": e.designation_held,
                    "from_date": e.from_date.isoformat(),
                    "to_date": e.to_date.isoformat() if e.to_date else "",
                    "date_range": (
                        e.from_date.isoformat()
                        + " – "
                        + (e.to_date.isoformat() if e.to_date else "Present")
                    ),
                    "responsibilities": e.responsibilities or "",
                    "responsibilities_short": _truncate(e.responsibilities or "", 60),
                }
                for e in exp_list
            ]

        self.loading = False

    # ── Save (create or update) ───────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_experience(self, form_data: dict) -> rx.event.EventSpec | None:
        organization = form_data.get("form_organization", "").strip()
        designation_held = form_data.get("form_designation_held", "").strip()
        from_str = form_data.get("form_from_date_str", "").strip()
        to_str = form_data.get("form_to_date_str", "").strip()
        responsibilities = form_data.get("form_responsibilities", "").strip() or None
        editing_id = self.form_exp_id.strip()

        if not organization:
            return rx.toast.error("Organization is required.")
        if not designation_held:
            return rx.toast.error("Designation held is required.")
        if not from_str:
            return rx.toast.error("From date is required.")
        try:
            from_date = date.fromisoformat(from_str)
        except ValueError:
            return rx.toast.error("From date is not a valid date.")
        to_date: date | None = None
        if to_str:
            try:
                to_date = date.fromisoformat(to_str)
            except ValueError:
                return rx.toast.error("To date is not a valid date.")

        after_snap: dict = {}
        resource_id_for_audit: str = ""
        with open_session() as session:
            svc = _build_svc(session)
            try:
                if not editing_id:
                    exp = svc.add_experience(
                        UUID(self.faculty_id),
                        organization=organization,
                        designation_held=designation_held,
                        from_date=from_date,
                        to_date=to_date,
                        responsibilities=responsibilities,
                        actor_id=UUID(self.current_user_id),
                    )
                else:
                    fields = {
                        "organization": organization,
                        "designation_held": designation_held,
                        "from_date": from_date,
                        "to_date": to_date,
                        "responsibilities": responsibilities,
                    }
                    exp = svc.update_experience(
                        UUID(editing_id), fields, UUID(self.current_user_id)
                    )
                after_snap = audit_snapshot(exp)
                resource_id_for_audit = str(exp.id)
                session.commit()
            except (
                ExperienceNotFoundError,
                InvalidDateError,
                FacultyNotFoundError,
                NotOwnerError,
            ) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=resource_id_for_audit, after=after_snap)
        self.show_form = False
        self._clear_form()
        return [
            rx.toast.success("Experience record saved."),
            rx.call_script("window.location.reload()"),
        ]

    # ── Delete ────────────────────────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def confirm_delete(self) -> rx.event.EventSpec | None:
        if not self.deleting_id:
            return rx.toast.error("No record selected for deletion.")

        before_snap: dict = {}
        with open_session() as session:
            exp_repo = FacultyExperienceRepository(session)
            exp_before = exp_repo.get(UUID(self.deleting_id))
            if exp_before is None:
                return rx.toast.error("Experience record not found.")
            before_snap = audit_snapshot(exp_before)
            svc = _build_svc(session)
            try:
                svc.remove_experience(UUID(self.deleting_id), UUID(self.current_user_id))
                session.commit()
            except (ExperienceNotFoundError, NotOwnerError) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=self.deleting_id, before=before_snap)
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_organization = ""
        return [
            rx.toast.success("Experience record deleted."),
            rx.call_script("window.location.reload()"),
        ]


def _truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[:length] + "…"
