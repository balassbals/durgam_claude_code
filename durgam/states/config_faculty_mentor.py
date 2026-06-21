"""FacultyMentorConfigState — AY+campus-scoped faculty mentor assignment CRUD."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import reflex as rx

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.models.config_anchors import (
    FacultyMentorAssignment,
    FacultyMentorConfirmation,
)
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.assignment import AssignmentRepository
from durgam.repositories.campus import CampusRepository
from durgam.repositories.document_template import DocumentTemplateRepository
from durgam.repositories.file_asset import FileAssetRepository
from durgam.services.assignment import (
    AssignmentError,
    FacultyMentorService,
    faculty_display,
    resolve_faculty_id_by_employee_id,
)
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.states.base import BaseState
from durgam.storage import get_storage_backend


def _svc(session) -> FacultyMentorService:
    return FacultyMentorService(
        repo=AssignmentRepository(FacultyMentorAssignment, session),
    )


class FacultyMentorConfigState(BaseState):
    # AY selector
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    # Campus selector
    campus_options: list[dict[str, str]] = []
    selected_campus_id: str = ""

    # List
    mentors: list[dict[str, str]] = []
    loading: bool = True

    # Form
    show_form: bool = False
    editing_id: str = ""
    form_faculty: str = ""
    form_student: str = ""
    form_notes: str = ""

    # Roster confirmation
    is_confirmed: bool = False
    confirmed_info: str = ""

    # Confirmation dialog
    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_mentors(self) -> None:
        guard = self._config_guard("faculty_mentor_assignment", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.mentors = []
        self.show_form = False
        self.ay_options = []
        self.campus_options = []

        with open_session() as session:
            ay_repo = AcademicYearRepository(session)
            for ay in ay_repo.list_active():
                self.ay_options.append({
                    "value": str(ay.id),
                    "label": ay.code,
                    "is_locked": "1" if ay.is_locked else "0",
                })
            if self.ay_options and not self.selected_ay_id:
                self.selected_ay_id = self.ay_options[0]["value"]

            campus_repo = CampusRepository(session)
            for c in campus_repo.list_active():
                self.campus_options.append({
                    "value": str(c.id),
                    "label": f"{c.code} — {c.name}",
                })
            if self.campus_options and not self.selected_campus_id:
                self.selected_campus_id = self.campus_options[0]["value"]

            self._load_data(session)

        self._load_nav_entries()
        self.loading = False

    def _load_data(self, session) -> None:
        from sqlmodel import select

        self.mentors = []
        self.is_confirmed = False
        self.confirmed_info = ""
        if not self.selected_ay_id or not self.selected_campus_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        confirmation = session.exec(
            select(FacultyMentorConfirmation).where(
                FacultyMentorConfirmation.academic_year_id == UUID(self.selected_ay_id),
                FacultyMentorConfirmation.campus_id == UUID(self.selected_campus_id),
                FacultyMentorConfirmation.is_deleted == False,  # noqa: E712
            )
        ).first()
        if confirmation and confirmation.confirmed_at:
            self.is_confirmed = True
            self.confirmed_info = (
                f"Confirmed on {confirmation.confirmed_at.strftime('%b %-d, %Y %I:%M %p')}"
            )

        repo = AssignmentRepository(FacultyMentorAssignment, session)
        for m in repo.list_by_ay_and_scope(
            UUID(self.selected_ay_id), UUID(self.selected_campus_id), "campus_id",
        ):
            self.mentors.append({
                "id": str(m.id),
                "faculty": faculty_display(session, m.faculty_id),
                "student": m.student_id_placeholder,
                "notes": m.notes or "",
            })

    async def on_ay_change(self, value: str) -> None:
        self.selected_ay_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)
        matched = [o for o in self.ay_options if o["value"] == value]
        self.ay_is_locked = bool(matched and matched[0]["is_locked"] == "1")

    async def on_campus_change(self, value: str) -> None:
        self.selected_campus_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)

    # ── Form setters ──────────────────────────────────────────────────────────

    def set_form_faculty(self, v: str) -> None:
        self.form_faculty = v

    def set_form_student(self, v: str) -> None:
        self.form_student = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    # ── Form open / cancel ────────────────────────────────────────────────────

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_faculty = ""
        self.form_student = ""
        self.form_notes = ""
        self.show_form = True

    def open_edit(self, mid: str, faculty: str, student: str, notes: str):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = mid
        self.form_faculty = faculty
        self.form_student = student
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    # ── Save (create / update) ────────────────────────────────────────────────

    @require_role(action="write", resource="faculty_mentor_assignment")
    @audit_action(action="write", resource="faculty_mentor_assignment")
    async def save_mentor(self, form_data: dict) -> None:
        faculty = form_data.get("form_faculty", "").strip()
        student = form_data.get("form_student", "").strip()
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        try:
            with open_session() as session:
                svc = _svc(session)
                repo = AssignmentRepository(FacultyMentorAssignment, session)
                actor_id = UUID(self.current_user_id)
                faculty_id = resolve_faculty_id_by_employee_id(session, faculty)
                if not editing_id:
                    entity = svc.create(
                        academic_year_id=UUID(self.selected_ay_id),
                        campus_id=UUID(self.selected_campus_id),
                        faculty_id=faculty_id,
                        student_id_placeholder=student,
                        actor_id=actor_id,
                        notes=notes,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    before_snap = audit_snapshot(repo.get_by_id(UUID(editing_id)))
                    entity = svc.update(
                        UUID(editing_id),
                        {
                            "faculty_id": faculty_id,
                            "student_id_placeholder": student,
                            "notes": notes,
                        },
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
        except (AssignmentError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_mentors()
        self.flash = "Mentor assignment saved."
        self.flash_type = "success"

    # ── Soft delete ───────────────────────────────────────────────────────────

    def open_deactivate_confirm(self, record_id: str, faculty: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate assignment for '{faculty}'?"
        self.confirm_body = "This will remove the faculty mentor assignment."
        self.confirm_open = True

    @require_role(action="delete", resource="faculty_mentor_assignment")
    @audit_action(action="delete", resource="faculty_mentor_assignment")
    async def soft_delete_mentor(self) -> None:
        try:
            with open_session() as session:
                repo = AssignmentRepository(FacultyMentorAssignment, session)
                entity = repo.get_by_id(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
        except (AssignmentError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_mentors()
        self.flash = "Mentor assignment deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""

    # ── Roster confirmation (Director-only) ──────────────────────────────────

    @require_role(action="write", resource="faculty_mentor_assignment")
    @audit_action(action="write", resource="faculty_mentor_assignment")
    async def confirm_roster(self) -> None:
        if not self.selected_ay_id or not self.selected_campus_id:
            self.flash = "Select an academic year and campus first."
            self.flash_type = "error"
            return
        try:
            with open_session() as session:
                confirmation = FacultyMentorConfirmation(
                    academic_year_id=UUID(self.selected_ay_id),
                    campus_id=UUID(self.selected_campus_id),
                    confirmed_at=datetime.now(UTC),
                    confirmed_by_user_id=UUID(self.current_user_id),
                    created_by=UUID(self.current_user_id),
                    updated_by=UUID(self.current_user_id),
                )
                session.add(confirmation)
                session.flush()
                after_snap = audit_snapshot(confirmation)
                confirmation_id = str(confirmation.id)
                session.commit()
                self._set_audit(resource_id=confirmation_id, after=after_snap)
        except Exception as e:
            self.flash = f"Confirmation failed: {e}"
            self.flash_type = "error"
            return
        await self.load_mentors()
        self.flash = "Faculty mentor roster confirmed."
        self.flash_type = "success"

    # ── Roster download ──────────────────────────────────────────────────────

    @require_role(action="read", resource="faculty_mentor_assignment")
    @audit_action(action="read", resource="faculty_mentor_assignment")
    async def download_roster(self) -> None:
        from durgam.docgen.merge import DocgenError, render_docx_template

        if not self.selected_ay_id or not self.selected_campus_id:
            self.flash = "Select an academic year and campus first."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                dt_repo = DocumentTemplateRepository(session)
                letterhead = dt_repo.get_letterhead_by_role("DIRECTOR")
                if letterhead is None:
                    self.flash = (
                        "No Director letterhead configured — upload one "
                        "under Config → Letterheads before downloading the roster."
                    )
                    self.flash_type = "error"
                    return

                file_asset_repo = FileAssetRepository(session)
                lh_asset = file_asset_repo.get_by_id(letterhead.file_id)
                if lh_asset is None:
                    self.flash = "Director letterhead file not found."
                    self.flash_type = "error"
                    return

                backend = get_storage_backend()
                template_bytes = backend.get(lh_asset.storage_key)

                repo = AssignmentRepository(FacultyMentorAssignment, session)
                rows = repo.list_by_ay_and_scope(
                    UUID(self.selected_ay_id), UUID(self.selected_campus_id), "campus_id",
                )

                ay_label = ""
                for opt in self.ay_options:
                    if opt["value"] == self.selected_ay_id:
                        ay_label = opt["label"]
                        break
                campus_label = ""
                for opt in self.campus_options:
                    if opt["value"] == self.selected_campus_id:
                        campus_label = opt["label"]
                        break

                mentor_list = [
                    {
                        "sno": i + 1,
                        "faculty": faculty_display(session, m.faculty_id),
                        "student": m.student_id_placeholder,
                        "notes": m.notes or "",
                    }
                    for i, m in enumerate(rows)
                ]
                record_count = len(mentor_list)
                context = {
                    "academic_year": ay_label,
                    "campus": campus_label,
                    "mentors": mentor_list,
                }
                rendered, docgen_warnings = render_docx_template(template_bytes, context)

        except DocgenError as e:
            self.flash = f"Export failed: {e}"
            self.flash_type = "error"
            return
        except Exception as e:
            self.flash = f"Export failed: {e}"
            self.flash_type = "error"
            return

        roster_filename = f"faculty_mentor_roster_{ay_label}_{campus_label}.docx"
        self._set_audit(
            resource_id=self.selected_ay_id,
            after={"format": "docx", "record_count": record_count},
        )
        if docgen_warnings:
            self.flash = docgen_warnings[0]
            self.flash_type = "warning"
        else:
            self.flash = "Roster exported."
            self.flash_type = "success"
        return rx.download(data=rendered, filename=roster_filename)
