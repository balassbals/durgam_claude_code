"""VisionMissionRepository — singleton and per-department vision/mission (E-001).

No delete methods are exposed. VisionMissionService raises NotDeletableError on
any delete attempt; this repository simply never provides a delete pathway.
"""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.vision_mission import (
    DepartmentMission,
    DepartmentVisionMission,
    UniversityMission,
    UniversityVisionMission,
)


class VisionMissionRepository:
    """Not a BaseRepository subclass — manages two distinct model hierarchies."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── University vision/mission ─────────────────────────────────────────────

    def get_university_vm(self) -> UniversityVisionMission | None:
        """Return the singleton university vision/mission row, or None if not yet created."""
        return self._session.exec(
            select(UniversityVisionMission).where(
                UniversityVisionMission.is_deleted == False  # noqa: E712
            )
        ).first()

    def create_university_vm(self, vision: str, actor_id: UUID | None = None) -> UniversityVisionMission:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        uvm = UniversityVisionMission(
            vision=vision,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(uvm)
        self._session.flush()
        self._session.refresh(uvm)
        return uvm

    def save_university_vm(self, uvm: UniversityVisionMission) -> UniversityVisionMission:
        from datetime import UTC, datetime

        uvm.updated_at = datetime.now(UTC)
        self._session.add(uvm)
        self._session.flush()
        self._session.refresh(uvm)
        return uvm

    def list_university_missions(self, university_vision_id: UUID) -> list[UniversityMission]:
        """Return missions for the university, ordered by display_order."""
        return list(
            self._session.exec(
                select(UniversityMission).where(
                    UniversityMission.university_vision_id == university_vision_id,
                    UniversityMission.is_deleted == False,  # noqa: E712
                ).order_by(UniversityMission.display_order)  # type: ignore[attr-defined]
            ).all()
        )

    def create_university_mission(
        self,
        university_vision_id: UUID,
        statement: str,
        display_order: int,
        actor_id: UUID | None = None,
    ) -> UniversityMission:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        mission = UniversityMission(
            university_vision_id=university_vision_id,
            statement=statement,
            display_order=display_order,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(mission)
        self._session.flush()
        self._session.refresh(mission)
        return mission

    def save_university_mission(self, mission: UniversityMission) -> UniversityMission:
        from datetime import UTC, datetime

        mission.updated_at = datetime.now(UTC)
        self._session.add(mission)
        self._session.flush()
        self._session.refresh(mission)
        return mission

    # ── Department vision/mission ─────────────────────────────────────────────

    def get_department_vm(self, department_id: UUID) -> DepartmentVisionMission | None:
        return self._session.exec(
            select(DepartmentVisionMission).where(
                DepartmentVisionMission.department_id == department_id,
                DepartmentVisionMission.is_deleted == False,  # noqa: E712
            )
        ).first()

    def create_department_vm(
        self, department_id: UUID, vision: str, actor_id: UUID | None = None
    ) -> DepartmentVisionMission:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        dvm = DepartmentVisionMission(
            department_id=department_id,
            vision=vision,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(dvm)
        self._session.flush()
        self._session.refresh(dvm)
        return dvm

    def save_department_vm(self, dvm: DepartmentVisionMission) -> DepartmentVisionMission:
        from datetime import UTC, datetime

        dvm.updated_at = datetime.now(UTC)
        self._session.add(dvm)
        self._session.flush()
        self._session.refresh(dvm)
        return dvm

    def list_department_missions(self, department_vision_id: UUID) -> list[DepartmentMission]:
        """Return missions for a department, ordered by display_order."""
        return list(
            self._session.exec(
                select(DepartmentMission).where(
                    DepartmentMission.department_vision_id == department_vision_id,
                    DepartmentMission.is_deleted == False,  # noqa: E712
                ).order_by(DepartmentMission.display_order)  # type: ignore[attr-defined]
            ).all()
        )

    def create_department_mission(
        self,
        department_vision_id: UUID,
        statement: str,
        display_order: int,
        actor_id: UUID | None = None,
    ) -> DepartmentMission:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        mission = DepartmentMission(
            department_vision_id=department_vision_id,
            statement=statement,
            display_order=display_order,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(mission)
        self._session.flush()
        self._session.refresh(mission)
        return mission

    def save_department_mission(self, mission: DepartmentMission) -> DepartmentMission:
        from datetime import UTC, datetime

        mission.updated_at = datetime.now(UTC)
        self._session.add(mission)
        self._session.flush()
        self._session.refresh(mission)
        return mission
