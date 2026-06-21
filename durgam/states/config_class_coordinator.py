"""ClassCoordinatorConfigState — AY+department-scoped coordinator assignment CRUD.

Max-2-coordinator enforcement: ClassCoordinatorService.create raises
AssignmentError("Maximum 2 coordinators per class per academic year.")
when the limit is reached. This state catches the error and surfaces it
as a flash message.
"""

from __future__ import annotations

from uuid import UUID

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.models.config_anchors import ClassCoordinatorAssignment
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.assignment import AssignmentRepository
from durgam.repositories.department import DepartmentRepository
from durgam.services.assignment import (
    AssignmentError,
    ClassCoordinatorService,
    faculty_display,
    resolve_faculty_id_by_employee_id,
)
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.states.base import BaseState


def _svc(session) -> ClassCoordinatorService:
    return ClassCoordinatorService(
        repo=AssignmentRepository(ClassCoordinatorAssignment, session),
    )


class ClassCoordinatorConfigState(BaseState):
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    dept_options: list[dict[str, str]] = []
    selected_dept_id: str = ""
    dept_locked: bool = False
    dept_name_display: str = ""

    coordinators: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_faculty: str = ""
    form_class: str = ""
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_coordinators(self) -> None:
        guard = self._config_guard("class_coordinator_assignment", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.coordinators = []
        self.show_form = False
        self.ay_options = []
        self.dept_options = []

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

            dept_repo = DepartmentRepository(session)
            all_depts = dept_repo.list_active()
            user_dept_id = self._resolve_user_dept_scope(session)
            if user_dept_id:
                self.dept_locked = True
                self.selected_dept_id = str(user_dept_id)
                matched = [d for d in all_depts if d.id == user_dept_id]
                self.dept_name_display = f"{matched[0].code} — {matched[0].name}" if matched else ""
                self.dept_options = [{"value": str(user_dept_id), "label": self.dept_name_display}]
            else:
                self.dept_locked = False
                for d in all_depts:
                    self.dept_options.append({
                        "value": str(d.id),
                        "label": f"{d.code} — {d.name}",
                    })
                if self.dept_options and not self.selected_dept_id:
                    self.selected_dept_id = self.dept_options[0]["value"]

            self._load_data(session)

        self._load_nav_entries()
        self.loading = False

    def _load_data(self, session) -> None:
        self.coordinators = []
        if not self.selected_ay_id or not self.selected_dept_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        svc = _svc(session)
        for c in svc.list_by_ay_dept(UUID(self.selected_ay_id), UUID(self.selected_dept_id)):
            self.coordinators.append({
                "id": str(c.id),
                "faculty": faculty_display(session, c.faculty_id),
                "class": c.class_identifier,
                "notes": c.notes or "",
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

    async def on_dept_change(self, value: str) -> None:
        self.selected_dept_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)

    def set_form_faculty(self, v: str) -> None:
        self.form_faculty = v

    def set_form_class(self, v: str) -> None:
        self.form_class = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_faculty = ""
        self.form_class = ""
        self.form_notes = ""
        self.show_form = True

    def open_edit(self, cid: str, faculty: str, cls: str, notes: str):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = cid
        self.form_faculty = faculty
        self.form_class = cls
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="class_coordinator_assignment")
    @audit_action(action="write", resource="class_coordinator_assignment")
    async def save_coordinator(self, form_data: dict) -> None:
        faculty = form_data.get("form_faculty", "").strip()
        cls = form_data.get("form_class", "").strip()
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        try:
            with open_session() as session:
                svc = _svc(session)
                repo = AssignmentRepository(ClassCoordinatorAssignment, session)
                actor_id = UUID(self.current_user_id)
                faculty_id = resolve_faculty_id_by_employee_id(session, faculty)
                if not editing_id:
                    entity = svc.create(
                        academic_year_id=UUID(self.selected_ay_id),
                        department_id=UUID(self.selected_dept_id),
                        faculty_id=faculty_id,
                        class_identifier=cls,
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
                            "class_identifier": cls,
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
        await self.load_coordinators()
        self.flash = "Class coordinator assignment saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, faculty: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate assignment for '{faculty}'?"
        self.confirm_body = "This will remove the class coordinator assignment."
        self.confirm_open = True

    @require_role(action="delete", resource="class_coordinator_assignment")
    @audit_action(action="delete", resource="class_coordinator_assignment")
    async def soft_delete_coordinator(self) -> None:
        try:
            with open_session() as session:
                repo = AssignmentRepository(ClassCoordinatorAssignment, session)
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
        await self.load_coordinators()
        self.flash = "Class coordinator assignment deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
