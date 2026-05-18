"""AdminCoursesState — course list, create, edit, soft-delete (/admin/config/courses)."""

from __future__ import annotations

from uuid import UUID

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.course import CourseRepository
from durgam.repositories.department import DepartmentRepository, SubDepartmentRepository
from durgam.repositories.program import ProgramRepository
from durgam.services.course import CourseError, CourseService
from durgam.services.department import DepartmentService
from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.services.program import ProgramService
from durgam.states.base import BaseState


def _svc(session) -> CourseService:
    return CourseService(course_repo=CourseRepository(session))


class AdminCoursesState(BaseState):
    # List
    courses: list[dict] = []
    loading: bool = True

    # Form (create/edit)
    show_form: bool = False
    editing_id: str = ""   # empty = create mode
    form_code: str = ""
    form_name: str = ""
    form_program_id: str = ""
    form_department_id: str = ""
    form_credits: str = ""
    form_lecture: str = ""
    form_tutorial: str = ""
    form_practical: str = ""
    form_evaluation: str = "I"   # default: Internal

    # Dropdowns for form
    programs_dropdown: list[dict] = []    # {"id": str, "code": str, "name": str}
    departments_dropdown: list[dict] = []  # {"id": str, "code": str, "name": str}

    # Confirmation dialog (soft delete)
    confirm_open: bool = False
    confirm_course_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    # ── Load ──────────────────────────────────────────────────────────────────

    async def load_courses(self) -> None:
        # course:write:* gates this page — SYSTEM_ADMIN only.
        guard = self._config_guard("course", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.courses = []   # reset before query (page-on-load data refresh rule)
        self.show_form = False
        with open_session() as session:
            dept_by_id = {
                str(d.id): d.code
                for d in DepartmentService(
                    DepartmentRepository(session),
                    SubDepartmentRepository(session),
                ).list()
            }
            prog_by_id = {
                str(p.id): p.code
                for p in ProgramService(ProgramRepository(session)).list()
            }
            for c in _svc(session).list():
                self.courses.append({
                    "id": str(c.id),
                    "code": c.code,
                    "name": c.name,
                    "program_id": str(c.program_id),
                    "program_code": prog_by_id.get(str(c.program_id), ""),
                    "department_id": str(c.department_id),
                    "department_code": dept_by_id.get(str(c.department_id), ""),
                    "credits": str(c.credits),
                    "lecture": str(c.lecture),
                    "tutorial": str(c.tutorial),
                    "practical": str(c.practical),
                    "evaluation": c.evaluation,
                })
        self._load_nav_entries()
        self.loading = False

    # ── Dropdowns ─────────────────────────────────────────────────────────────

    def _load_dropdowns(self) -> None:
        with open_session() as session:
            self.programs_dropdown = [
                {"id": str(p.id), "label": f"{p.code} — {p.name}"}
                for p in ProgramService(ProgramRepository(session)).list()
            ]
            self.departments_dropdown = [
                {"id": str(d.id), "label": f"{d.code} — {d.name}"}
                for d in DepartmentService(
                    DepartmentRepository(session),
                    SubDepartmentRepository(session),
                ).list()
            ]

    # ── Setters (Reflex 0.9.x does not auto-generate set_* for sub-states) ────

    def set_form_code(self, value: str) -> None:
        self.form_code = value

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_program_id(self, value: str) -> None:
        self.form_program_id = value

    def set_form_department_id(self, value: str) -> None:
        self.form_department_id = value

    def set_form_credits(self, value: str) -> None:
        self.form_credits = value

    def set_form_lecture(self, value: str) -> None:
        self.form_lecture = value

    def set_form_tutorial(self, value: str) -> None:
        self.form_tutorial = value

    def set_form_practical(self, value: str) -> None:
        self.form_practical = value

    def set_form_evaluation(self, value: str) -> None:
        self.form_evaluation = value

    # ── Form open/close ───────────────────────────────────────────────────────

    def open_create(self) -> None:
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_program_id = ""
        self.form_department_id = ""
        self.form_credits = ""
        self.form_lecture = ""
        self.form_tutorial = ""
        self.form_practical = ""
        self.form_evaluation = "I"
        self._load_dropdowns()
        self.show_form = True

    def open_edit(
        self,
        course_id: str,
        code: str,
        name: str,
        program_id: str,
        department_id: str,
        credits: str,
        lecture: str,
        tutorial: str,
        practical: str,
        evaluation: str,
    ) -> None:
        self.editing_id = course_id
        self.form_code = code
        self.form_name = name
        self.form_program_id = program_id
        self.form_department_id = department_id
        self.form_credits = credits
        self.form_lecture = lecture
        self.form_tutorial = tutorial
        self.form_practical = practical
        self.form_evaluation = evaluation
        self._load_dropdowns()
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_program_id = ""
        self.form_department_id = ""
        self.form_credits = ""
        self.form_lecture = ""
        self.form_tutorial = ""
        self.form_practical = ""
        self.form_evaluation = "I"
        self.flash = ""
        self.flash_type = "info"

    # ── Save ──────────────────────────────────────────────────────────────────

    @require_role(action="write", resource="course")
    @audit_action(action="write", resource="course")
    async def save_course(self, form_data: dict) -> None:
        """Receives form_data from rx.form on_submit — authoritative values."""
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        # Dropdowns use rx.select.root (no name= attr) — read from state vars.
        program_id_str = self.form_program_id.strip()
        department_id_str = self.form_department_id.strip()
        evaluation = self.form_evaluation.strip() or "I"
        editing_id = form_data.get("editing_id", "").strip()

        try:
            credits = int(form_data.get("form_credits", "0") or "0")
            lecture = int(form_data.get("form_lecture", "0") or "0")
            tutorial = int(form_data.get("form_tutorial", "0") or "0")
            practical = int(form_data.get("form_practical", "0") or "0")
        except ValueError:
            self.flash = "Credits and hours must be integers."
            self.flash_type = "error"
            return

        if not program_id_str or not department_id_str:
            self.flash = "Program and department are required."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                actor_id = UUID(self.current_user_id)
                svc = _svc(session)
                if not editing_id:
                    svc.create(
                        code, name,
                        UUID(program_id_str), UUID(department_id_str),
                        credits, lecture, tutorial, practical, evaluation,
                        actor_id,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {
                            "name": name,
                            "program_id": UUID(program_id_str),
                            "department_id": UUID(department_id_str),
                            "credits": credits,
                            "lecture": lecture,
                            "tutorial": tutorial,
                            "practical": practical,
                            "evaluation": evaluation,
                        },
                        actor_id,
                    )
                session.commit()  # open_session() does NOT auto-commit
        except CourseError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_courses()
        self.flash = "Course saved."
        self.flash_type = "success"

    # ── Soft delete ───────────────────────────────────────────────────────────

    def open_soft_delete_confirm(self, course_id: str, name: str) -> None:
        self.confirm_course_id = course_id
        self.confirm_title = f"Deactivate '{name}'?"
        self.confirm_body = (
            "This will deactivate the course. Existing data referencing it is preserved."
        )
        self.confirm_open = True

    @require_role(action="delete", resource="course")
    @audit_action(action="delete", resource="course")
    async def soft_delete_course(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_course_id), UUID(self.current_user_id)
                )
                session.commit()  # open_session() does NOT auto-commit
        except (CourseError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            return
        self.confirm_open = False
        self.confirm_course_id = ""
        await self.load_courses()
        self.flash = "Course deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_course_id = ""


# Alias so durgam/durgam.py keeps its existing import unchanged.
CourseConfigState = AdminCoursesState
