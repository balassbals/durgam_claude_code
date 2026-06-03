"""VisionMissionConfigState — /admin/config/vision-mission.

University V&M editor (Registrar family + SYSTEM_ADMIN).
HoDs are redirected immediately to their own department's V&M page.
SYSTEM_ADMIN additionally sees a department picker to reach any dept's editor.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.models.vision_mission import UniversityMission
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

    # Department picker — only shown to SYSTEM_ADMIN (has unscoped dept VM write)
    can_manage_depts: bool = False
    dept_rows: list[dict] = []   # [{code, name, has_vision, edit_href}]

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
        self.can_manage_depts = False
        self.show_vision_form = False
        self.show_mission_modal = False

        user_id = UUID(self.current_user_id)

        with open_session() as session:
            self.can_edit_university = can(
                user_id, "write", "university_vision_mission", None, None, session
            )

            if not self.can_edit_university:
                # HoD path: find the department this user is authorised to edit
                # and redirect there immediately. Iterate active depts, checking
                # exact scope_id match — first match wins.
                dept_repo = DepartmentRepository(session)
                for dept in dept_repo.list_active():
                    if can(
                        user_id,
                        "write",
                        "department_vision_mission",
                        "department",
                        dept.id,
                        session,
                    ):
                        return rx.redirect(  # type: ignore[return-value]
                            f"/admin/config/vision-mission/departments/{dept.code}"
                        )
                # Guard passed but neither permission matched — shouldn't happen
                return rx.redirect("/")  # type: ignore[return-value]

            # University editor path (Registrar family + SYSTEM_ADMIN)
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

            # Department picker: visible only to users who can write dept VM
            # with scope_id=None (i.e. unscoped — SYSTEM_ADMIN only).
            # Registrar has no department_vision_mission:write permission at all.
            self.can_manage_depts = can(
                user_id, "write", "department_vision_mission", "department", None, session
            )
            if self.can_manage_depts:
                dept_repo = DepartmentRepository(session)
                vm_repo = VisionMissionRepository(session)
                placeholder = "To be configured by the Head of Department."
                rows = []
                for d in dept_repo.list_active():
                    dvm = vm_repo.get_department_vm(d.id)
                    has_vm = dvm is not None and dvm.vision != placeholder
                    rows.append({
                        "code": d.code,
                        "name": d.name,
                        "has_vision": "Yes" if has_vm else "No",
                        "edit_href": f"/admin/config/vision-mission/departments/{d.code}",
                    })
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
                svc = _svc(session)
                uvm = svc.get_or_create_university_vm()
                before_snap = {"vision_statement": uvm.vision}
                uvm_id = str(uvm.id)
                svc.update_university_vision(vision, UUID(self.current_user_id))
                session.commit()
            self._set_audit(
                resource_id=uvm_id,
                before=before_snap,
                after={"vision_statement": vision},
            )
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
                    mission = svc.add_university_mission(statement, actor_id)
                    mission_id = str(mission.id)
                    after_snap = {"statement": statement, "order_index": mission.display_order}
                    session.commit()
                    self._set_audit(resource_id=mission_id, after=after_snap)
                else:
                    old = session.get(UniversityMission, UUID(editing_id))
                    before_snap = {"statement": old.statement} if old else {}
                    svc.update_university_mission(UUID(editing_id), statement, actor_id)
                    session.commit()
                    self._set_audit(
                        resource_id=editing_id,
                        before=before_snap,
                        after={"statement": statement},
                    )
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
                mission = session.get(UniversityMission, UUID(mission_id))
                old_order = mission.display_order if mission else None
                _svc(session).move_university_mission(
                    UUID(mission_id), "up", UUID(self.current_user_id)
                )
                new_order = mission.display_order if mission else None
                session.commit()
            self._set_audit(
                resource_id=mission_id,
                before={"order_index": old_order},
                after={"order_index": new_order},
            )
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
                mission = session.get(UniversityMission, UUID(mission_id))
                old_order = mission.display_order if mission else None
                _svc(session).move_university_mission(
                    UUID(mission_id), "down", UUID(self.current_user_id)
                )
                new_order = mission.display_order if mission else None
                session.commit()
            self._set_audit(
                resource_id=mission_id,
                before={"order_index": old_order},
                after={"order_index": new_order},
            )
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
                mission = session.get(UniversityMission, UUID(mission_id))
                before_snap = (
                    {"statement": mission.statement, "order_index": mission.display_order}
                    if mission
                    else {}
                )
                _svc(session).remove_university_mission(
                    UUID(mission_id), UUID(self.current_user_id)
                )
                session.commit()
            self._set_audit(resource_id=mission_id, before=before_snap)
        except VisionMissionError as e:
            self.flash = e.message
            self.flash_type = "error"
            return
        await self.load_vision_mission()
        self.flash = "Mission statement removed."
        self.flash_type = "success"
