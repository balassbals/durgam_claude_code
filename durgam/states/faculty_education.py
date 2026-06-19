"""FacultyEducationState — education CRUD for /faculty/profile/education (M10 Phase P3a)."""

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
    EducationNotFoundError,
    FacultyNotFoundError,
    FacultyService,
    InvalidYearError,
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


class FacultyEducationState(BaseState):
    loading: bool = True
    faculty_id: str = ""
    has_faculty_record: bool = False
    records: list[dict] = []

    # Form state
    show_form: bool = False
    form_edu_id: str = ""
    form_degree_name: str = ""
    form_specialization: str = ""
    form_awarding_institution: str = ""
    form_year_str: str = ""
    form_distinction: str = ""

    # Delete confirm
    show_delete_confirm: bool = False
    deleting_id: str = ""
    deleting_degree: str = ""

    # ── Setters ──────────────────────────────────────────────────────────────

    def set_form_degree_name(self, v: str) -> None:
        self.form_degree_name = v

    def set_form_specialization(self, v: str) -> None:
        self.form_specialization = v

    def set_form_awarding_institution(self, v: str) -> None:
        self.form_awarding_institution = v

    def set_form_year_str(self, v: str) -> None:
        self.form_year_str = v

    def set_form_distinction(self, v: str) -> None:
        self.form_distinction = v

    # ── Modal open / close helpers ────────────────────────────────────────────

    def open_create_modal(self) -> None:
        self.form_edu_id = ""
        self.form_degree_name = ""
        self.form_specialization = ""
        self.form_awarding_institution = ""
        self.form_year_str = ""
        self.form_distinction = ""
        self.show_form = True

    def open_edit_by_id(self, edu_id: str) -> None:
        self.form_edu_id = edu_id
        self.form_degree_name = ""
        self.form_specialization = ""
        self.form_awarding_institution = ""
        self.form_year_str = ""
        self.form_distinction = ""
        for r in self.records:
            if r["id"] == edu_id:
                self.form_degree_name = r.get("degree_name", "")
                self.form_specialization = r.get("specialization", "")
                self.form_awarding_institution = r.get("awarding_institution", "")
                self.form_year_str = r.get("year_of_award", "")
                self.form_distinction = r.get("distinction", "")
                break
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.form_edu_id = ""
        self.form_degree_name = ""
        self.form_specialization = ""
        self.form_awarding_institution = ""
        self.form_year_str = ""
        self.form_distinction = ""

    def open_delete_confirm_by_id(self, edu_id: str) -> None:
        self.deleting_id = edu_id
        self.deleting_degree = ""
        for r in self.records:
            if r["id"] == edu_id:
                self.deleting_degree = r.get("degree_name", "")
                break
        self.show_delete_confirm = True

    def cancel_delete(self) -> None:
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_degree = ""

    # ── On-load ───────────────────────────────────────────────────────────────

    async def load_education(self) -> None:
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
            edu_list = svc.list_education(faculty.id)
            self.records = [
                {
                    "id": str(e.id),
                    "degree_name": e.degree_name,
                    "specialization": e.specialization or "",
                    "awarding_institution": e.awarding_institution,
                    "year_of_award": str(e.year_of_award),
                    "distinction": e.distinction or "",
                }
                for e in edu_list
            ]

        self.loading = False

    # ── Save (create or update) ───────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_education(self, form_data: dict) -> rx.event.EventSpec | None:
        degree_name = form_data.get("form_degree_name", "").strip()
        awarding_institution = form_data.get("form_awarding_institution", "").strip()
        year_str = form_data.get("form_year_str", "").strip()
        specialization = form_data.get("form_specialization", "").strip() or None
        distinction = form_data.get("form_distinction", "").strip() or None
        editing_id = self.form_edu_id.strip()

        if not degree_name:
            return rx.toast.error("Degree name is required.")
        if not awarding_institution:
            return rx.toast.error("Awarding institution is required.")
        if not year_str:
            return rx.toast.error("Year of award is required.")
        try:
            year_of_award = int(year_str)
        except ValueError:
            return rx.toast.error("Year of award must be a 4-digit number.")

        after_snap: dict = {}
        resource_id_for_audit: str = ""
        with open_session() as session:
            svc = _build_svc(session)
            try:
                if not editing_id:
                    edu = svc.add_education(
                        UUID(self.faculty_id),
                        degree_name=degree_name,
                        awarding_institution=awarding_institution,
                        year_of_award=year_of_award,
                        actor_id=UUID(self.current_user_id),
                        specialization=specialization,
                        distinction=distinction,
                    )
                else:
                    fields = {
                        "degree_name": degree_name,
                        "awarding_institution": awarding_institution,
                        "year_of_award": year_of_award,
                        "specialization": specialization,
                        "distinction": distinction,
                    }
                    edu = svc.update_education(
                        UUID(editing_id), fields, UUID(self.current_user_id)
                    )
                after_snap = audit_snapshot(edu)
                resource_id_for_audit = str(edu.id)
                session.commit()
            except (
                EducationNotFoundError,
                InvalidYearError,
                FacultyNotFoundError,
                NotOwnerError,
            ) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=resource_id_for_audit, after=after_snap)
        return [
            rx.toast.success("Education record saved."),
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
            edu_repo = FacultyEducationRepository(session)
            edu_before = edu_repo.get(UUID(self.deleting_id))
            if edu_before is None:
                return rx.toast.error("Education record not found.")
            before_snap = audit_snapshot(edu_before)
            svc = _build_svc(session)
            try:
                svc.remove_education(UUID(self.deleting_id), UUID(self.current_user_id))
                session.commit()
            except (EducationNotFoundError, NotOwnerError) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=self.deleting_id, before=before_snap)
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_degree = ""
        return [
            rx.toast.success("Education record deleted."),
            rx.call_script("window.location.reload()"),
        ]
