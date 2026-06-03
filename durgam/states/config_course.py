"""AdminCoursesState — course list, create, edit, soft-delete (/admin/config/courses).

Credit computation rule (M3 default):
    credits = lecture + tutorial + (practical // PRACTICAL_CREDIT_RATIO)

This applies a global 2:1 practical-to-credit ratio. At M13, the ratio will become
a field on ProgramRegulation so different programs can have different ratios. See
docs/milestones/M13.md → 'Inherited from M3'.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.audit.snapshot import audit_snapshot
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


# Global practical-to-credit ratio for M3. Moves to ProgramRegulation at M13.
PRACTICAL_CREDIT_RATIO = 2


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
    # Credits are derived from L/T/P; not a user-editable field.
    computed_credits_display: str = "0"
    form_lecture: str = "0"
    form_tutorial: str = "0"
    form_practical: str = "0"
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
        self.flash = ""
        self.flash_type = "info"
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

    def _update_credits_display(self) -> None:
        """Recompute computed_credits_display from current L/T/P state vars."""
        try:
            lec = int(self.form_lecture or "0")
            tut = int(self.form_tutorial or "0")
            prac = int(self.form_practical or "0")
            self.computed_credits_display = str(
                lec + tut + (prac // PRACTICAL_CREDIT_RATIO)
            )
        except (ValueError, ZeroDivisionError):
            self.computed_credits_display = "0"

    def set_form_lecture(self, value: str) -> None:
        self.form_lecture = value
        self._update_credits_display()

    def set_form_tutorial(self, value: str) -> None:
        self.form_tutorial = value
        self._update_credits_display()

    def set_form_practical(self, value: str) -> None:
        self.form_practical = value
        self._update_credits_display()

    def set_form_evaluation(self, value: str) -> None:
        self.form_evaluation = value

    # ── Form open/close ───────────────────────────────────────────────────────

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_program_id = ""
        self.form_department_id = ""
        self.form_lecture = "0"
        self.form_tutorial = "0"
        self.form_practical = "0"
        self.form_evaluation = "I"
        self.computed_credits_display = "0"
        self._load_dropdowns()
        self.show_form = True
        return rx.scroll_to("course-page-top")

    def open_edit(
        self,
        course_id: str,
        code: str,
        name: str,
        program_id: str,
        department_id: str,
        lecture: str,
        tutorial: str,
        practical: str,
        evaluation: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = course_id
        self.form_code = code
        self.form_name = name
        self.form_program_id = program_id
        self.form_department_id = department_id
        self.form_lecture = lecture
        self.form_tutorial = tutorial
        self.form_practical = practical
        self.form_evaluation = evaluation
        self._update_credits_display()
        self._load_dropdowns()
        self.show_form = True
        return rx.scroll_to("course-page-top")

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_program_id = ""
        self.form_department_id = ""
        self.form_lecture = "0"
        self.form_tutorial = "0"
        self.form_practical = "0"
        self.form_evaluation = "I"
        self.computed_credits_display = "0"
        self.flash = ""
        self.flash_type = "info"
        return rx.scroll_to("course-page-top")

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
            lecture = int(form_data.get("form_lecture", "0") or "0")
            tutorial = int(form_data.get("form_tutorial", "0") or "0")
            practical = int(form_data.get("form_practical", "0") or "0")
        except ValueError:
            self.flash = "Contact hours must be integers."
            self.flash_type = "error"
            return

        if lecture + tutorial + practical == 0:
            self.flash = "Course must have at least one contact hour (lecture, tutorial, or practical)."
            self.flash_type = "error"
            return
        if practical % PRACTICAL_CREDIT_RATIO != 0:
            self.flash = (
                f"Practical hours must be a multiple of {PRACTICAL_CREDIT_RATIO} "
                f"(1 credit per {PRACTICAL_CREDIT_RATIO} practical hours)."
            )
            self.flash_type = "error"
            return

        # Credits are derived — never from user input.
        credits = lecture + tutorial + (practical // PRACTICAL_CREDIT_RATIO)

        missing = []
        # Code is disabled in edit mode — not submitted by browser (Bug 1 fix).
        if not editing_id and not code:
            missing.append("code")
        if not name:
            missing.append("name")
        if not program_id_str:
            missing.append("program")
        if not department_id_str:
            missing.append("department")
        if missing:
            self.flash = f"Required: {', '.join(missing)}"
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                actor_id = UUID(self.current_user_id)
                svc = _svc(session)
                if not editing_id:
                    entity = svc.create(
                        code, name,
                        UUID(program_id_str), UUID(department_id_str),
                        credits, lecture, tutorial, practical, evaluation,
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    before_snap = audit_snapshot(svc.get(UUID(editing_id)))
                    entity = svc.update(
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
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
        except CourseError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_courses()
        self.flash = "Course saved."
        self.flash_type = "success"
        return rx.scroll_to("course-page-top")

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
                svc = _svc(session)
                entity = svc.get(UUID(self.confirm_course_id))
                before_snap = audit_snapshot(entity)
                svc.soft_delete(
                    UUID(self.confirm_course_id), UUID(self.current_user_id)
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
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
        return rx.scroll_to("course-page-top")

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_course_id = ""


# Alias so durgam/durgam.py keeps its existing import unchanged.
CourseConfigState = AdminCoursesState
