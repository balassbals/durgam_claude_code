"""DeptVMConfigState — /admin/config/vision-mission/departments/[dept_code].

Department Vision & Mission editor. Guards that the acting user has
department_vision_mission:write:department permission for the specific
department named in the URL. HoD scoped to DMACS cannot edit PHYS.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.repositories.department import DepartmentRepository
from durgam.repositories.vision_mission import VisionMissionRepository
from durgam.services.vision_mission import VisionMissionError, VisionMissionService
from durgam.states.base import BaseState


def _svc(session) -> VisionMissionService:
    return VisionMissionService(vm_repo=VisionMissionRepository(session))


class DeptVMConfigState(BaseState):
    # Current department
    dept_code: str = ""
    dept_name: str = ""
    dept_id: str = ""

    # Department VM display
    dept_vision: str = ""
    dept_missions: list[dict] = []  # [{id, statement, display_order}]

    # Vision edit form
    show_vision_form: bool = False
    form_vision: str = ""

    # Mission modal
    show_mission_modal: bool = False
    editing_mission_id: str = ""
    form_mission: str = ""

    loading: bool = True

    async def load_dept_vm(self) -> None:
        # Resolve session and check base authentication first
        self.admin_authorized = False
        self.flash = ""
        self.flash_type = "info"
        self._resolve_session()
        if not self.current_user_id:
            return rx.redirect("/login")  # type: ignore[return-value]
        try:
            user_id = UUID(self.current_user_id)
        except ValueError:
            self.current_user_id = ""
            return rx.redirect("/login")  # type: ignore[return-value]

        dept_code = self.router.page.params.get("dept_code", "")
        if not dept_code:
            return rx.redirect("/admin/config/vision-mission")  # type: ignore[return-value]

        self.loading = True
        self.dept_code = dept_code
        self.dept_vision = ""
        self.dept_missions = []
        self.show_vision_form = False
        self.show_mission_modal = False

        with open_session() as session:
            dept_repo = DepartmentRepository(session)
            dept = dept_repo.get_by_code(dept_code)
            if dept is None:
                self.flash = f"Department '{dept_code}' not found."
                self.flash_type = "error"
                return rx.redirect("/admin/config/vision-mission")  # type: ignore[return-value]

            self.dept_name = dept.name
            self.dept_id = str(dept.id)

            # Scope-specific permission check: user must have write permission for THIS dept
            dept_uuid = dept.id
            if not can(
                user_id,
                "write",
                "department_vision_mission",
                "department",
                dept_uuid,
                session,
            ):
                self.flash = "You do not have permission to edit this department's vision and mission."
                self.flash_type = "warning"
                return rx.redirect("/")  # type: ignore[return-value]

            self.admin_authorized = True

            svc = _svc(session)
            dvm = svc.get_or_create_department_vm(dept_uuid)
            self.dept_vision = dvm.vision
            self.dept_missions = [
                {
                    "id": str(m.id),
                    "statement": m.statement,
                    "display_order": str(m.display_order),
                }
                for m in svc.list_department_missions(dept_uuid)
            ]

        self._load_nav_entries()
        self.loading = False

    # ── Setters ────────────────────────────────────────────────────────────────

    def set_form_vision(self, value: str) -> None:
        self.form_vision = value

    def set_form_mission(self, value: str) -> None:
        self.form_mission = value

    # ── Vision form ────────────────────────────────────────────────────────────

    def open_edit_vision(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.form_vision = self.dept_vision
        self.show_vision_form = True

    def cancel_vision_form(self) -> None:
        self.show_vision_form = False
        self.form_vision = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="department_vision_mission", scope="department")
    @audit_action(action="write", resource="department_vision_mission")
    async def save_dept_vision(self, form_data: dict) -> None:
        vision = form_data.get("form_vision", "").strip()
        dept_id = form_data.get("dept_id", "").strip()
        try:
            with open_session() as session:
                _svc(session).update_department_vision(
                    UUID(dept_id), vision, UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        self.show_vision_form = False
        await self.load_dept_vm()
        self.flash = "Department vision saved."
        self.flash_type = "success"

    # ── Mission modal ──────────────────────────────────────────────────────────

    def open_add_mission(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_mission_id = ""
        self.form_mission = ""
        self.show_mission_modal = True

    def open_edit_mission(self, mission_id: str, statement: str) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_mission_id = mission_id
        self.form_mission = statement
        self.show_mission_modal = True

    def cancel_mission_modal(self) -> None:
        self.show_mission_modal = False
        self.editing_mission_id = ""
        self.form_mission = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="department_vision_mission", scope="department")
    @audit_action(action="write", resource="department_vision_mission")
    async def save_mission(self, form_data: dict) -> None:
        statement = form_data.get("form_mission", "").strip()
        editing_id = form_data.get("editing_mission_id", "").strip()
        dept_id = self.dept_id
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.add_department_mission(UUID(dept_id), statement, actor_id)
                else:
                    svc.update_department_mission(UUID(editing_id), statement, actor_id)
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_mission_modal = False
            return
        self.show_mission_modal = False
        await self.load_dept_vm()
        self.flash = "Mission statement saved."
        self.flash_type = "success"

    # ── Reorder / remove ──────────────────────────────────────────────────────

    @require_role(action="write", resource="department_vision_mission", scope="department")
    @audit_action(action="write", resource="department_vision_mission")
    async def move_mission_up(self, mission_id: str) -> None:
        try:
            with open_session() as session:
                _svc(session).move_department_mission(
                    UUID(mission_id), "up", UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_dept_vm()

    @require_role(action="write", resource="department_vision_mission", scope="department")
    @audit_action(action="write", resource="department_vision_mission")
    async def move_mission_down(self, mission_id: str) -> None:
        try:
            with open_session() as session:
                _svc(session).move_department_mission(
                    UUID(mission_id), "down", UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_dept_vm()

    @require_role(action="write", resource="department_vision_mission", scope="department")
    @audit_action(action="write", resource="department_vision_mission")
    async def remove_mission(self, mission_id: str) -> None:
        try:
            with open_session() as session:
                _svc(session).remove_department_mission(
                    UUID(mission_id), UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_dept_vm()
        self.flash = "Mission statement removed."
        self.flash_type = "success"
