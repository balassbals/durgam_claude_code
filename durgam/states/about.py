"""States for read-only About pages (/about/*).

Accessible to all authenticated users. No admin permission required.
"""

from __future__ import annotations

import reflex as rx

from durgam.db import open_session
from durgam.repositories.department import DepartmentRepository
from durgam.repositories.vision_mission import VisionMissionRepository
from durgam.services.vision_mission import VisionMissionService
from durgam.states.base import BaseState


def _vm_svc(session) -> VisionMissionService:
    return VisionMissionService(vm_repo=VisionMissionRepository(session))


def _resolve_or_redirect(state: BaseState):
    """Resolve session. Return redirect if not authenticated, None if ok."""
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


class AboutUniversityState(BaseState):
    university_vision: str = ""
    university_missions: list[dict] = []
    loading: bool = True

    async def load_university_about(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect
        self.loading = True
        self.university_vision = ""
        self.university_missions = []
        with open_session() as session:
            svc = _vm_svc(session)
            uvm = svc.get_or_create_university_vm()
            placeholder = "To be configured by the Registrar's office."
            if uvm.vision != placeholder:
                self.university_vision = uvm.vision
                self.university_missions = [
                    {"statement": m.statement, "display_order": str(m.display_order)}
                    for m in svc.list_university_missions()
                ]
        self._load_nav_entries()
        self.loading = False


class AboutDeptListState(BaseState):
    dept_rows: list[dict] = []  # [{code, name, has_vision}]
    loading: bool = True

    async def load_dept_list(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect
        self.loading = True
        self.dept_rows = []
        with open_session() as session:
            dept_repo = DepartmentRepository(session)
            vm_repo = VisionMissionRepository(session)
            placeholder = "To be configured by the Head of Department."
            rows = []
            for d in dept_repo.list_active():
                dvm = vm_repo.get_department_vm(d.id)
                has_vm = dvm is not None and dvm.vision != placeholder
                rows.append({"code": d.code, "name": d.name, "has_vision": "Yes" if has_vm else "No"})
            self.dept_rows = rows
        self._load_nav_entries()
        self.loading = False


class AboutDeptDetailState(BaseState):
    # named active_dept_code to avoid shadowing the [dept_code] dynamic route arg
    active_dept_code: str = ""
    dept_name: str = ""
    dept_vision: str = ""
    dept_missions: list[dict] = []
    not_found: bool = False
    no_vm: bool = False
    loading: bool = True

    async def load_dept_detail(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        dept_code = self.router.page.params.get("dept_code", "")
        self.loading = True
        self.active_dept_code = dept_code
        self.dept_name = ""
        self.dept_vision = ""
        self.dept_missions = []
        self.not_found = False
        self.no_vm = False

        with open_session() as session:
            dept_repo = DepartmentRepository(session)
            dept = dept_repo.get_by_code(dept_code)
            if dept is None:
                self.not_found = True
                self.loading = False
                return

            self.dept_name = dept.name
            vm_repo = VisionMissionRepository(session)
            dvm = vm_repo.get_department_vm(dept.id)
            placeholder = "To be configured by the Head of Department."
            if dvm is None or dvm.vision == placeholder:
                self.no_vm = True
            else:
                self.dept_vision = dvm.vision
                self.dept_missions = [
                    {"statement": m.statement, "display_order": str(m.display_order)}
                    for m in vm_repo.list_department_missions(dvm.id)
                ]

        self._load_nav_entries()
        self.loading = False
