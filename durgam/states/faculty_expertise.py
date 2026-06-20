"""FacultyExpertiseState — expertise CRUD for /faculty/profile/expertise (M10 Phase P3c).

Mirrors FacultyEducationState (P3a) with P3a.1 modal-close pattern baked in.
Simpler than P3a/P3b — two fields (area required, proficiency optional), no dates.
"""

from __future__ import annotations

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
    ExpertiseNotFoundError,
    FacultyNotFoundError,
    FacultyService,
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


class FacultyExpertiseState(BaseState):
    loading: bool = True
    faculty_id: str = ""
    has_faculty_record: bool = False
    records: list[dict] = []

    # Form state
    show_form: bool = False
    form_exp_id: str = ""
    form_area: str = ""
    form_proficiency: str = ""

    # Delete confirm
    show_delete_confirm: bool = False
    deleting_id: str = ""
    deleting_area: str = ""

    # ── Setters ──────────────────────────────────────────────────────────────

    def set_form_area(self, v: str) -> None:
        self.form_area = v

    def set_form_proficiency(self, v: str) -> None:
        self.form_proficiency = v

    # ── Modal open / close helpers ────────────────────────────────────────────

    def _clear_form(self) -> None:
        self.form_exp_id = ""
        self.form_area = ""
        self.form_proficiency = ""

    def open_create_modal(self) -> None:
        self._clear_form()
        self.show_form = True

    def open_edit_by_id(self, exp_id: str) -> None:
        self._clear_form()
        self.form_exp_id = exp_id
        for r in self.records:
            if r["id"] == exp_id:
                self.form_area = r.get("area", "")
                self.form_proficiency = r.get("proficiency", "")
                break
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self._clear_form()

    def open_delete_confirm_by_id(self, exp_id: str) -> None:
        self.deleting_id = exp_id
        self.deleting_area = ""
        for r in self.records:
            if r["id"] == exp_id:
                self.deleting_area = r.get("area", "")
                break
        self.show_delete_confirm = True

    def cancel_delete(self) -> None:
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_area = ""

    # ── On-load ───────────────────────────────────────────────────────────────

    async def load_expertise(self) -> None:
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
            exp_list = svc.list_expertise(faculty.id)
            self.records = [
                {
                    "id": str(e.id),
                    "area": e.area,
                    "proficiency": e.proficiency or "",
                }
                for e in exp_list
            ]

        self.loading = False

    # ── Save (create or update) ───────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_expertise(self, form_data: dict) -> rx.event.EventSpec | None:
        area = form_data.get("form_area", "").strip()
        proficiency = form_data.get("form_proficiency", "").strip() or None
        editing_id = self.form_exp_id.strip()

        if not area:
            return rx.toast.error("Area of expertise is required.")

        after_snap: dict = {}
        resource_id_for_audit: str = ""
        with open_session() as session:
            svc = _build_svc(session)
            try:
                if not editing_id:
                    exp = svc.add_expertise(
                        UUID(self.faculty_id),
                        area=area,
                        proficiency=proficiency,
                        actor_id=UUID(self.current_user_id),
                    )
                else:
                    fields = {"area": area, "proficiency": proficiency}
                    exp = svc.update_expertise(
                        UUID(editing_id), fields, UUID(self.current_user_id)
                    )
                after_snap = audit_snapshot(exp)
                resource_id_for_audit = str(exp.id)
                session.commit()
            except (
                ExpertiseNotFoundError,
                FacultyNotFoundError,
                NotOwnerError,
            ) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=resource_id_for_audit, after=after_snap)
        self.show_form = False
        self._clear_form()
        return [
            rx.toast.success("Expertise record saved."),
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
            exp_repo = FacultyExpertiseRepository(session)
            exp_before = exp_repo.get(UUID(self.deleting_id))
            if exp_before is None:
                return rx.toast.error("Expertise record not found.")
            before_snap = audit_snapshot(exp_before)
            svc = _build_svc(session)
            try:
                svc.remove_expertise(UUID(self.deleting_id), UUID(self.current_user_id))
                session.commit()
            except (ExpertiseNotFoundError, NotOwnerError) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=self.deleting_id, before=before_snap)
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_area = ""
        return [
            rx.toast.success("Expertise record deleted."),
            rx.call_script("window.location.reload()"),
        ]
