"""NonOwnedCourseConfigState — AY-scoped non-owned course CRUD."""

from __future__ import annotations

from uuid import UUID

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.non_owned_course import NonOwnedCourseRepository
from durgam.services.non_owned_course import NonOwnedCourseError, NonOwnedCourseService
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.states.base import BaseState


def _svc(session) -> NonOwnedCourseService:
    return NonOwnedCourseService(
        repo=NonOwnedCourseRepository(session),
    )


class NonOwnedCourseConfigState(BaseState):
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    courses: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_course_code: str = ""
    form_course_name: str = ""
    form_credits: str = "0"
    form_semester: str = "odd"
    form_faculty: str = ""
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_courses(self) -> None:
        guard = self._config_guard("non_owned_course", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.courses = []
        self.show_form = False
        self.ay_options = []

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

            self._load_data(session)

        self._load_nav_entries()
        self.loading = False

    def _load_data(self, session) -> None:
        self.courses = []
        if not self.selected_ay_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        svc = _svc(session)
        for c in svc.list_by_ay(UUID(self.selected_ay_id)):
            self.courses.append({
                "id": str(c.id),
                "course_code": c.course_code,
                "course_name": c.course_name,
                "credits": str(c.credits),
                "semester": c.semester,
                "faculty": c.faculty_id_placeholder,
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

    def set_form_course_code(self, v: str) -> None:
        self.form_course_code = v

    def set_form_course_name(self, v: str) -> None:
        self.form_course_name = v

    def set_form_credits(self, v: str) -> None:
        self.form_credits = v

    def set_form_semester(self, v: str) -> None:
        self.form_semester = v

    def set_form_faculty(self, v: str) -> None:
        self.form_faculty = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_course_code = ""
        self.form_course_name = ""
        self.form_credits = "0"
        self.form_semester = "odd"
        self.form_faculty = ""
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self, cid: str, code: str, name: str, credits: str,
        semester: str, faculty: str, notes: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = cid
        self.form_course_code = code
        self.form_course_name = name
        self.form_credits = credits
        self.form_semester = semester
        self.form_faculty = faculty
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="non_owned_course")
    @audit_action(action="write", resource="non_owned_course")
    async def save_course(self, form_data: dict) -> None:
        course_code = form_data.get("form_course_code", "").strip()
        course_name = form_data.get("form_course_name", "").strip()
        credits_str = form_data.get("form_credits", "0").strip()
        semester = form_data.get("form_semester", "").strip()
        faculty = form_data.get("form_faculty", "").strip()
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        try:
            credits_val = int(credits_str)
        except ValueError:
            self.flash = "Credits must be a number."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        academic_year_id=UUID(self.selected_ay_id),
                        course_code=course_code,
                        course_name=course_name,
                        credits=credits_val,
                        semester=semester,
                        faculty_id_placeholder=faculty,
                        actor_id=actor_id,
                        notes=notes,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {
                            "course_code": course_code,
                            "course_name": course_name,
                            "credits": credits_val,
                            "semester": semester,
                            "faculty_id_placeholder": faculty,
                            "notes": notes,
                        },
                        actor_id,
                    )
                session.commit()
        except (NonOwnedCourseError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_courses()
        self.flash = "Non-owned course saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, code: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate course '{code}'?"
        self.confirm_body = "This will remove the non-owned course record."
        self.confirm_open = True

    @require_role(action="delete", resource="non_owned_course")
    @audit_action(action="delete", resource="non_owned_course")
    async def soft_delete_course(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
        except (NonOwnedCourseError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_courses()
        self.flash = "Non-owned course deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
