"""UGTimetableConfigState — AY+semester-scoped UG timetable CRUD."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.ug_timetable import UGTimetableRepository
from durgam.services.assignment import (
    AssignmentError,
    faculty_display,
    resolve_faculty_id_by_employee_id,
)
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.services.ug_timetable import UGTimetableError, UGTimetableService
from durgam.states.base import BaseState

_DAY_LABELS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


def _svc(session) -> UGTimetableService:
    return UGTimetableService(
        repo=UGTimetableRepository(session),
    )


class UGTimetableConfigState(BaseState):
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    selected_semester: str = "odd"

    slots: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_year_of_study: str = "1"
    form_day_of_week: str = "1"
    form_period_number: str = "1"
    form_course_code: str = ""
    form_course_name: str = ""
    form_faculty: str = ""
    form_room: str = ""
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_slots(self) -> None:
        guard = self._config_guard("ug_timetable", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.slots = []
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
        self.slots = []
        if not self.selected_ay_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        svc = _svc(session)
        for s in svc.list_by_ay_semester(UUID(self.selected_ay_id), self.selected_semester):
            self.slots.append({
                "id": str(s.id),
                "year_of_study": str(s.year_of_study),
                "day_of_week": str(s.day_of_week),
                "day_label": _DAY_LABELS.get(s.day_of_week, str(s.day_of_week)),
                "period_number": str(s.period_number),
                "course_code": s.course_code,
                "course_name": s.course_name,
                "faculty": faculty_display(session, s.faculty_id),
                "room": s.room or "",
                "notes": s.notes or "",
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

    async def on_semester_change(self, value: str) -> None:
        self.selected_semester = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)

    def set_form_year_of_study(self, v: str) -> None:
        self.form_year_of_study = v

    def set_form_day_of_week(self, v: str) -> None:
        self.form_day_of_week = v

    def set_form_period_number(self, v: str) -> None:
        self.form_period_number = v

    def set_form_course_code(self, v: str) -> None:
        self.form_course_code = v

    def set_form_course_name(self, v: str) -> None:
        self.form_course_name = v

    def set_form_faculty(self, v: str) -> None:
        self.form_faculty = v

    def set_form_room(self, v: str) -> None:
        self.form_room = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_year_of_study = "1"
        self.form_day_of_week = "1"
        self.form_period_number = "1"
        self.form_course_code = ""
        self.form_course_name = ""
        self.form_faculty = ""
        self.form_room = ""
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self, sid: str, year: str, day: str, period: str,
        code: str, name: str, faculty: str, room: str, notes: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = sid
        self.form_year_of_study = year
        self.form_day_of_week = day
        self.form_period_number = period
        self.form_course_code = code
        self.form_course_name = name
        self.form_faculty = faculty
        self.form_room = room
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="ug_timetable")
    @audit_action(action="write", resource="ug_timetable")
    async def save_slot(self, form_data: dict) -> None:
        year_str = form_data.get("form_year_of_study", "1").strip()
        day_str = form_data.get("form_day_of_week", "1").strip()
        period_str = form_data.get("form_period_number", "1").strip()
        course_code = form_data.get("form_course_code", "").strip()
        course_name = form_data.get("form_course_name", "").strip()
        faculty = form_data.get("form_faculty", "").strip()
        room = form_data.get("form_room", "").strip() or None
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        try:
            year_of_study = int(year_str)
            day_of_week = int(day_str)
            period_number = int(period_str)
        except ValueError:
            self.flash = "Year, day, and period must be numbers."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                faculty_id = resolve_faculty_id_by_employee_id(session, faculty)
                if not editing_id:
                    entity = svc.create(
                        academic_year_id=UUID(self.selected_ay_id),
                        semester=self.selected_semester,
                        year_of_study=year_of_study,
                        day_of_week=day_of_week,
                        period_number=period_number,
                        course_code=course_code,
                        course_name=course_name,
                        faculty_id=faculty_id,
                        actor_id=actor_id,
                        room=room,
                        notes=notes,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    before_snap = audit_snapshot(
                        UGTimetableRepository(session).get_by_id(UUID(editing_id))
                    )
                    entity = svc.update(
                        UUID(editing_id),
                        {
                            "year_of_study": year_of_study,
                            "day_of_week": day_of_week,
                            "period_number": period_number,
                            "course_code": course_code,
                            "course_name": course_name,
                            "faculty_id": faculty_id,
                            "room": room,
                            "notes": notes,
                        },
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
        except IntegrityError:
            self.flash = "A slot already exists for this day/period/year."
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        except (UGTimetableError, AssignmentError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_slots()
        self.flash = "Timetable slot saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, code: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate slot for '{code}'?"
        self.confirm_body = "This will remove the timetable slot."
        self.confirm_open = True

    @require_role(action="delete", resource="ug_timetable")
    @audit_action(action="delete", resource="ug_timetable")
    async def soft_delete_slot(self) -> None:
        try:
            with open_session() as session:
                entity = UGTimetableRepository(session).get_by_id(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
        except (UGTimetableError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_slots()
        self.flash = "Timetable slot deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
