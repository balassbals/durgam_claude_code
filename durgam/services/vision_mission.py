"""VisionMissionService — update-only management for vision and missions (E-001).

Both university and department vision/mission are update-only; no delete is
permitted. NotDeletableError is raised on any delete attempt.

University: singleton row; managed by Registrar family.
Department: one row per department; managed by HoD family scoped to their dept.
"""

from uuid import UUID

import structlog

from durgam.models.vision_mission import (
    DepartmentMission,
    DepartmentVisionMission,
    UniversityMission,
    UniversityVisionMission,
)
from durgam.repositories.vision_mission import VisionMissionRepository
from durgam.services.org_exceptions import NotDeletableError, OrgServiceError

log = structlog.get_logger(__name__)


class VisionMissionError(OrgServiceError):
    pass


class VisionMissionService:
    def __init__(self, vm_repo: VisionMissionRepository) -> None:
        self._vm = vm_repo

    # ── University vision/mission ─────────────────────────────────────────────

    def get_or_create_university_vm(self) -> UniversityVisionMission:
        uvm = self._vm.get_university_vm()
        if uvm is None:
            uvm = self._vm.create_university_vm(
                "To be configured by the Registrar's office."
            )
        return uvm

    def update_university_vision(
        self, vision: str, actor_id: UUID
    ) -> UniversityVisionMission:
        vision = vision.strip()
        if not vision:
            raise VisionMissionError("Vision text is required.")
        uvm = self.get_or_create_university_vm()
        uvm.vision = vision
        uvm.updated_by = actor_id
        uvm = self._vm.save_university_vm(uvm)
        log.info("university_vision_updated", actor=str(actor_id))
        return uvm

    def list_university_missions(self) -> list[UniversityMission]:
        uvm = self.get_or_create_university_vm()
        return self._vm.list_university_missions(uvm.id)

    def add_university_mission(
        self, statement: str, actor_id: UUID
    ) -> UniversityMission:
        statement = statement.strip()
        if not statement:
            raise VisionMissionError("Mission statement is required.")
        uvm = self.get_or_create_university_vm()
        existing = self._vm.list_university_missions(uvm.id)
        next_order = max((m.display_order for m in existing), default=0) + 1
        mission = self._vm.create_university_mission(
            uvm.id, statement, next_order, actor_id
        )
        log.info("university_mission_added", actor=str(actor_id))
        return mission

    def update_university_mission(
        self, mission_id: UUID, statement: str, actor_id: UUID
    ) -> UniversityMission:
        statement = statement.strip()
        if not statement:
            raise VisionMissionError("Mission statement is required.")
        mission = self._vm._session.get(UniversityMission, mission_id)
        if mission is None or mission.is_deleted:
            raise VisionMissionError("Mission not found.")
        mission.statement = statement
        mission.updated_by = actor_id
        return self._vm.save_university_mission(mission)

    # ── Department vision/mission ─────────────────────────────────────────────

    def get_or_create_department_vm(
        self, department_id: UUID
    ) -> DepartmentVisionMission:
        dvm = self._vm.get_department_vm(department_id)
        if dvm is None:
            dvm = self._vm.create_department_vm(
                department_id, "To be configured by the Head of Department."
            )
        return dvm

    def update_department_vision(
        self, department_id: UUID, vision: str, actor_id: UUID
    ) -> DepartmentVisionMission:
        vision = vision.strip()
        if not vision:
            raise VisionMissionError("Vision text is required.")
        dvm = self.get_or_create_department_vm(department_id)
        dvm.vision = vision
        dvm.updated_by = actor_id
        dvm = self._vm.save_department_vm(dvm)
        log.info("department_vision_updated", dept_id=str(department_id), actor=str(actor_id))
        return dvm

    def list_department_missions(self, department_id: UUID) -> list[DepartmentMission]:
        dvm = self.get_or_create_department_vm(department_id)
        return self._vm.list_department_missions(dvm.id)

    def add_department_mission(
        self, department_id: UUID, statement: str, actor_id: UUID
    ) -> DepartmentMission:
        statement = statement.strip()
        if not statement:
            raise VisionMissionError("Mission statement is required.")
        dvm = self.get_or_create_department_vm(department_id)
        existing = self._vm.list_department_missions(dvm.id)
        next_order = max((m.display_order for m in existing), default=0) + 1
        return self._vm.create_department_mission(
            dvm.id, statement, next_order, actor_id
        )

    def update_department_mission(
        self, mission_id: UUID, statement: str, actor_id: UUID
    ) -> DepartmentMission:
        statement = statement.strip()
        if not statement:
            raise VisionMissionError("Mission statement is required.")
        mission = self._vm._session.get(DepartmentMission, mission_id)
        if mission is None or mission.is_deleted:
            raise VisionMissionError("Mission not found.")
        mission.statement = statement
        mission.updated_by = actor_id
        return self._vm.save_department_mission(mission)

    # ── Delete stubs — always raise NotDeletableError (E-001) ─────────────────

    def delete_university_vm(self, *_args, **_kwargs) -> None:
        raise NotDeletableError(
            "University vision/mission cannot be deleted; only updated."
        )

    def delete_department_vm(self, *_args, **_kwargs) -> None:
        raise NotDeletableError(
            "Department vision/mission cannot be deleted; only updated."
        )
