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

    async def load_departments(self) -> None:
        guard = self._config_guard("department", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.departments = []   # reset before query (page-on-load data refresh rule)
        self.show_form = False
        self.show_detail = False
        with open_session() as session:
            for d in _dept_svc(session).list():
                campus_links = DepartmentRepository(session).list_campus_links(d.id)
                school = SchoolRepository(session).get_by_id(d.school_id)
                school_code = school.code if school else ""
                self.departments.append({
                    "id": str(d.id),
                    "code": d.code,
                    "name": d.name,
                    "school_id": str(d.school_id),
                    "school_code": school_code,
                    "main_campus_id": str(d.main_campus_id),
                    "campus_count": str(len(campus_links)),
                })
        self._load_nav_entries()
        self.loading = False

    # ── Dropdowns ─────────────────────────────────────────────────────────────

    def _load_dropdowns(self) -> None:
        with open_session() as session:
            self.schools_dropdown = [
                {"id": str(s.id), "code": s.code, "name": s.name}
                for s in SchoolService(SchoolRepository(session)).list()
            ]
            self.campuses_dropdown = [
                {"id": str(c.id), "code": c.code, "name": c.name}
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

    # ── Save ──────────────────────────────────────────────────────────────────

    @require_role(action="write", resource="department")
    @audit_action(action="write", resource="department")
    async def save_department(self, form_data: dict) -> None:
        """Receives form_data from rx.form on_submit — authoritative values."""
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        school_id_str = form_data.get("form_school_id", "").strip()
        main_campus_id_str = form_data.get("form_main_campus_id", "").strip()
        editing_id = form_data.get("editing_id", "").strip()

        if not school_id_str or not main_campus_id_str:
            self.flash = "School and campus are required."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                actor_id = UUID(self.current_user_id)
                svc = _dept_svc(session)
                if not editing_id:
                    svc.create(
                        code, name,
                        UUID(school_id_str), UUID(main_campus_id_str),
                        actor_id,
                    )
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
            self.flash = "Department saved."
            self.flash_type = "success"
        except DepartmentError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.show_form = False
        self.editing_id = ""
        await self.load_departments()

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
            self.flash = "Department deactivated."
            self.flash_type = "success"
        except (DepartmentError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_dept_id = ""
        await self.load_departments()

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_dept_id = ""

    # ── Detail view ───────────────────────────────────────────────────────────

    async def open_detail(self, dept_id: str, dept_name: str) -> None:
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
                {"id": str(c.id), "code": c.code}
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
        try:
            with open_session() as session:
                _dept_svc(session).add_campus(
                    UUID(self.detail_dept_id),
                    UUID(self.add_campus_id),
                    UUID(self.current_user_id),
                )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "Campus linked."
            self.flash_type = "success"
        except DepartmentError as e:
            self.flash = e.message
            self.flash_type = "error"
        await self.open_detail(self.detail_dept_id, self.detail_dept_name)

    def open_remove_campus_confirm(self, campus_id: str) -> None:
        self.confirm_remove_campus_id = campus_id
        self.confirm_remove_campus_open = True

    @require_role(action="write", resource="department")
    @audit_action(action="write", resource="department")
    async def remove_campus_link(self) -> None:
        try:
            with open_session() as session:
                _dept_svc(session).remove_campus(
                    UUID(self.detail_dept_id),
                    UUID(self.confirm_remove_campus_id),
                    UUID(self.current_user_id),
                )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "Campus removed."
            self.flash_type = "success"
        except DepartmentError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_remove_campus_open = False
        await self.open_detail(self.detail_dept_id, self.detail_dept_name)

    def cancel_remove_campus(self) -> None:
        self.confirm_remove_campus_open = False
        self.confirm_remove_campus_id = ""


# Alias so durgam.py keeps its existing import unchanged.
DepartmentConfigState = AdminDepartmentsState
