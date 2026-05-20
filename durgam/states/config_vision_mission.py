"""VisionMissionConfigState — /admin/config/vision-mission.

University V&M editor (Registrar family + SYSTEM_ADMIN) + department list for
navigation to per-department V&M pages. Uses _config_guard_any so both
registrar and HoD-family users can land here; the page shows only the
sections relevant to their permission.
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

_VM_GATES = [
    ("write", "university_vision_mission", None),
    ("write", "department_vision_mission", "department"),
]


def _svc(session) -> VisionMissionService:
    return VisionMissionService(vm_repo=VisionMissionRepository(session))


class VisionMissionConfigState(BaseState):
    # University VM display
    university_vision: str = ""
    university_missions: list[dict] = []  # [{id, statement, display_order}]
    can_edit_university: bool = False

    # Vision edit form
    show_vision_form: bool = False
    form_vision: str = ""

    # Mission add/edit modal
    show_mission_modal: bool = False
    editing_mission_id: str = ""   # empty = add mode
    form_mission: str = ""

    # Department list for navigation to dept V&M pages
    dept_rows: list[dict] = []   # [{code, name, has_vision}]

    loading: bool = True

    async def load_vision_mission(self) -> None:
        guard = self._config_guard_any(_VM_GATES)
        if guard is not None:
            return guard
        self.loading = True
        self.university_vision = ""
        self.university_missions = []
        self.dept_rows = []
        self.can_edit_university = False
        self.show_vision_form = False
        self.show_mission_modal = False

        user_id = UUID(self.current_user_id)

        with open_session() as session:
            self.can_edit_university = can(
                user_id, "write", "university_vision_mission", None, None, session
            )
            if self.can_edit_university:
                svc = _svc(session)
                uvm = svc.get_or_create_university_vm()
                self.university_vision = uvm.vision
                self.university_missions = [
                    {
                        "id": str(m.id),
                        "statement": m.statement,
                        "display_order": str(m.display_order),
                    }
                    for m in svc.list_university_missions()
                ]

            dept_repo = DepartmentRepository(session)
            vm_repo = VisionMissionRepository(session)
            rows = []
            for d in dept_repo.list_active():
                dvm = vm_repo.get_department_vm(d.id)
                placeholder = "To be configured by the Head of Department."
                has_vm = dvm is not None and dvm.vision != placeholder
                rows.append({"code": d.code, "name": d.name, "has_vision": "Yes" if has_vm else "No"})
            self.dept_rows = rows

        self._load_nav_entries()
        self.loading = False

    # ── Explicit setters ───────────────────────────────────────────────────────

    def set_form_vision(self, value: str) -> None:
        self.form_vision = value

    def set_form_mission(self, value: str) -> None:
        self.form_mission = value

    # ── University vision form ─────────────────────────────────────────────────

    def open_edit_vision(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.form_vision = self.university_vision
        self.show_vision_form = True

    def cancel_vision_form(self) -> None:
        self.show_vision_form = False
        self.form_vision = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="university_vision_mission")
    @audit_action(action="write", resource="university_vision_mission")
    async def save_university_vision(self, form_data: dict) -> None:
        vision = form_data.get("form_vision", "").strip()
        try:
            with open_session() as session:
                _svc(session).update_university_vision(vision, UUID(self.current_user_id))
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        self.show_vision_form = False
        await self.load_vision_mission()
        self.flash = "University vision saved."
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

    @require_role(action="write", resource="university_vision_mission")
    @audit_action(action="write", resource="university_vision_mission")
    async def save_mission(self, form_data: dict) -> None:
        statement = form_data.get("form_mission", "").strip()
        editing_id = form_data.get("editing_mission_id", "").strip()
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.add_university_mission(statement, actor_id)
                else:
                    svc.update_university_mission(UUID(editing_id), statement, actor_id)
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_mission_modal = False
            return
        self.show_mission_modal = False
        await self.load_vision_mission()
        self.flash = "Mission statement saved."
        self.flash_type = "success"

    # ── Mission reorder / remove ───────────────────────────────────────────────

    @require_role(action="write", resource="university_vision_mission")
    @audit_action(action="write", resource="university_vision_mission")
    async def move_mission_up(self, mission_id: str) -> None:
        try:
            with open_session() as session:
                _svc(session).move_university_mission(
                    UUID(mission_id), "up", UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_vision_mission()

    @require_role(action="write", resource="university_vision_mission")
    @audit_action(action="write", resource="university_vision_mission")
    async def move_mission_down(self, mission_id: str) -> None:
        try:
            with open_session() as session:
                _svc(session).move_university_mission(
                    UUID(mission_id), "down", UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_vision_mission()

    @require_role(action="write", resource="university_vision_mission")
    @audit_action(action="write", resource="university_vision_mission")
    async def remove_mission(self, mission_id: str) -> None:
        try:
            with open_session() as session:
                _svc(session).remove_university_mission(
                    UUID(mission_id), UUID(self.current_user_id)
                )
                session.commit()
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_vision_mission()
        self.flash = "Mission statement removed."
        self.flash_type = "success"
