"""AdminDepartmentsState — department list, create, edit, soft-delete,
campus-link management, and sub-department listing (/admin/config/departments)."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.campus import CampusRepository
from durgam.repositories.department import DepartmentRepository, SubDepartmentRepository
from durgam.repositories.school import SchoolRepository
from durgam.services.campus import CampusService
from durgam.services.department import DepartmentError, DepartmentService
from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.services.school import SchoolService
from durgam.states.base import BaseState


def _dept_svc(session) -> DepartmentService:
    return DepartmentService(
        dept_repo=DepartmentRepository(session),
        subdept_repo=SubDepartmentRepository(session),
    )


class AdminDepartmentsState(BaseState):
    # List
    departments: list[dict] = []
    loading: bool = True

    # Form (create/edit)
    show_form: bool = False
    editing_id: str = ""   # empty = create mode
    form_code: str = ""
    form_name: str = ""
    form_school_id: str = ""
    form_main_campus_id: str = ""

    # Dropdowns loaded for form
    schools_dropdown: list[dict] = []    # {"id": str, "code": str, "name": str}
    campuses_dropdown: list[dict] = []   # {"id": str, "code": str, "name": str}

    # Confirmation dialog (soft delete)
    confirm_open: bool = False
    confirm_dept_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    # Detail view (campus links + sub-departments)
    detail_dept_id: str = ""
    detail_dept_name: str = ""
    detail_campus_links: list[dict] = []   # {"campus_id": str, "campus_code": str}
    detail_sub_depts: list[dict] = []      # {"id": str, "code": str, "name": str}
    show_detail: bool = False

    # Add-campus-to-dept form
    add_campus_id: str = ""
    available_campuses: list[dict] = []   # campuses not yet linked

    # Confirm remove campus link
    confirm_remove_campus_open: bool = False
    confirm_remove_campus_id: str = ""

    # ── Load ──────────────────────────────────────────────────────────────────

    def _refresh_departments_list(self) -> None:
        """Reload the department list rows without touching form/detail/loading state.

        Called from load_departments (after guard) and from campus-link handlers
        (Bug 2: list count must update live without closing the detail panel).
        """
        with open_session() as session:
            new_rows = []
            for d in _dept_svc(session).list():
                campus_links = DepartmentRepository(session).list_campus_links(d.id)
                school = SchoolRepository(session).get_by_id(d.school_id)
                school_code = school.code if school else ""
                new_rows.append({
                    "id": str(d.id),
                    "code": d.code,
                    "name": d.name,
                    "school_id": str(d.school_id),
                    "school_code": school_code,
                    "main_campus_id": str(d.main_campus_id),
                    "campus_count": str(len(campus_links)),
                })
            self.departments = new_rows

    async def load_departments(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        guard = self._config_guard("department", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.departments = []   # reset before query (page-on-load data refresh rule)
        self.show_form = False
        self.show_detail = False
        self._refresh_departments_list()
        self._load_nav_entries()
        self.loading = False

    # ── Dropdowns ─────────────────────────────────────────────────────────────

    def _load_dropdowns(self) -> None:
        with open_session() as session:
            self.schools_dropdown = [
                {"id": str(s.id), "label": f"{s.code} — {s.name}"}
                for s in SchoolService(SchoolRepository(session)).list()
            ]
            self.campuses_dropdown = [
                {"id": str(c.id), "label": f"{c.code} — {c.name}"}
                for c in CampusService(CampusRepository(session)).list()
            ]

    # ── Setters (Reflex 0.9.x does not auto-generate set_* for sub-states) ────

    def set_form_code(self, value: str) -> None:
        self.form_code = value

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_school_id(self, value: str) -> None:
        self.form_school_id = value

    def set_form_main_campus_id(self, value: str) -> None:
        self.form_main_campus_id = value

    def set_add_campus_id(self, value: str) -> None:
        self.add_campus_id = value

    # ── Form open/close ───────────────────────────────────────────────────────

    def open_create(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_school_id = ""
        self.form_main_campus_id = ""
        self._load_dropdowns()
        self.show_form = True

    def open_edit(
        self,
        dept_id: str,
        code: str,
        name: str,
        school_id: str,
        main_campus_id: str,
    ) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = dept_id
        self.form_code = code
        self.form_name = name
        self.form_school_id = school_id
        self.form_main_campus_id = main_campus_id
        self._load_dropdowns()
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_school_id = ""
        self.form_main_campus_id = ""
        self.flash = ""
        self.flash_type = "info"

    # ── Save ──────────────────────────────────────────────────────────────────

    @require_role(action="write", resource="department")
    @audit_action(action="write", resource="department")
    async def save_department(self, form_data: dict) -> None:
        """Receives form_data from rx.form on_submit — authoritative values."""
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        # Dropdowns use rx.select.root (no name= attr) — read from state vars.
        school_id_str = self.form_school_id.strip()
        main_campus_id_str = self.form_main_campus_id.strip()
        editing_id = form_data.get("editing_id", "").strip()

        missing = []
        if not code:
            missing.append("code")
        if not name:
            missing.append("name")
        if not school_id_str:
            missing.append("school")
        if not main_campus_id_str:
            missing.append("main campus")
        if missing:
            self.flash = f"Required: {', '.join(missing)}"
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                actor_id = UUID(self.current_user_id)
                svc = _dept_svc(session)
                if not editing_id:
                    new_dept = svc.create(
                        code, name,
                        UUID(school_id_str), UUID(main_campus_id_str),
                        actor_id,
                    )
                    # Auto-create the main-campus join row.  The list query
                    # counts DepartmentCampus rows; without this the campus
                    # count shows 0 immediately after create (Bug 1).
                    svc.add_campus(new_dept.id, UUID(main_campus_id_str), actor_id)
                else:
                    svc.update(
                        UUID(editing_id),
                        {
                            "name": name,
                            "school_id": UUID(school_id_str),
                            "main_campus_id": UUID(main_campus_id_str),
                        },
                        actor_id,
                    )
                session.commit()  # open_session() does NOT auto-commit
            success_msg = "Department saved."
        except DepartmentError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        self.show_form = False
        self.editing_id = ""
        # load_departments calls _config_guard which clears flash.
        # Set flash AFTER load so the success message is visible (Bug 3).
        await self.load_departments()
        self.flash = success_msg
        self.flash_type = "success"

    # ── Soft delete ───────────────────────────────────────────────────────────

    def open_soft_delete_confirm(self, dept_id: str, name: str) -> None:
        self.confirm_dept_id = dept_id
        self.confirm_title = f"Deactivate '{name}'?"
        self.confirm_body = (
            "This will deactivate the department. Existing data referencing it is preserved."
        )
        self.confirm_open = True

    @require_role(action="delete", resource="department")
    @audit_action(action="delete", resource="department")
    async def soft_delete_department(self) -> None:
        try:
            with open_session() as session:
                _dept_svc(session).soft_delete(
                    UUID(self.confirm_dept_id), UUID(self.current_user_id)
                )
                session.commit()  # open_session() does NOT auto-commit
        except (DepartmentError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            return
        self.confirm_open = False
        self.confirm_dept_id = ""
        await self.load_departments()
        self.flash = "Department deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_dept_id = ""

    # ── Detail view ───────────────────────────────────────────────────────────

    async def open_detail(self, dept_id: str, dept_name: str) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.detail_dept_id = dept_id
        self.detail_dept_name = dept_name
        self.detail_campus_links = []
        self.detail_sub_depts = []
        self.show_detail = True
        self.add_campus_id = ""
        self.available_campuses = []
        with open_session() as session:
            svc = _dept_svc(session)
            dept_uuid = UUID(dept_id)
            links = DepartmentRepository(session).list_campus_links(dept_uuid)
            linked_campus_ids = {str(link.campus_id) for link in links}
            all_campuses = CampusService(CampusRepository(session)).list()
            campus_by_id = {str(c.id): c for c in all_campuses}
            self.detail_campus_links = [
                {
                    "campus_id": str(link.campus_id),
                    "campus_code": campus_by_id[str(link.campus_id)].code
                    if str(link.campus_id) in campus_by_id
                    else str(link.campus_id),
                }
                for link in links
            ]
            self.available_campuses = [
                {"id": str(c.id), "label": c.code}
                for c in all_campuses
                if str(c.id) not in linked_campus_ids
            ]
            subdepts = svc.list_sub_departments(dept_uuid)
            self.detail_sub_depts = [
                {"id": str(sd.id), "code": sd.code, "name": sd.name}
                for sd in subdepts
            ]

    def close_detail(self) -> None:
        self.show_detail = False
        self.detail_dept_id = ""
        self.detail_dept_name = ""
        self.detail_campus_links = []
        self.detail_sub_depts = []

    # ── Campus link management ────────────────────────────────────────────────

    @require_role(action="write", resource="department")
    @audit_action(action="write", resource="department")
    async def add_campus_link(self) -> None:
        if not self.add_campus_id:
            return
        self.flash = ""  # clear stale flash before this action (Bug 3)
        try:
            with open_session() as session:
                _dept_svc(session).add_campus(
                    UUID(self.detail_dept_id),
                    UUID(self.add_campus_id),
                    UUID(self.current_user_id),
                )
                session.commit()  # open_session() does NOT auto-commit
        except DepartmentError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        # Refresh list (campus_count) and detail (campus chips) in one round-trip.
        self._refresh_departments_list()
        await self.open_detail(self.detail_dept_id, self.detail_dept_name)
        self.flash = "Campus linked."
        self.flash_type = "success"

    def open_remove_campus_confirm(self, campus_id: str) -> None:
        self.confirm_remove_campus_id = campus_id
        self.confirm_remove_campus_open = True

    @require_role(action="write", resource="department")
    @audit_action(action="write", resource="department")
    async def remove_campus_link(self) -> None:
        self.flash = ""  # clear stale flash before this action (Bug 3)
        try:
            with open_session() as session:
                _dept_svc(session).remove_campus(
                    UUID(self.detail_dept_id),
                    UUID(self.confirm_remove_campus_id),
                    UUID(self.current_user_id),
                )
                session.commit()  # open_session() does NOT auto-commit
        except DepartmentError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_remove_campus_open = False
            return
        self.confirm_remove_campus_open = False
        self._refresh_departments_list()
        await self.open_detail(self.detail_dept_id, self.detail_dept_name)
        self.flash = "Campus removed."
        self.flash_type = "success"

    def cancel_remove_campus(self) -> None:
        self.confirm_remove_campus_open = False
        self.confirm_remove_campus_id = ""


# Alias so durgam.py keeps its existing import unchanged.
DepartmentConfigState = AdminDepartmentsState
