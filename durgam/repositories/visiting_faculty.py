"""VisitingFacultyRepository — department-scoped, no AY-lock (§9.10)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import VisitingFaculty
from durgam.repositories.base import BaseRepository


class VisitingFacultyRepository(BaseRepository[VisitingFaculty]):
    def __init__(self, session: Session) -> None:
        super().__init__(VisitingFaculty, session)

    def list_by_department(self, department_id: UUID) -> list[VisitingFaculty]:
        return list(
            self._session.exec(
                select(VisitingFaculty)
                .where(
                    VisitingFaculty.department_id == department_id,
                    VisitingFaculty.is_deleted == False,  # noqa: E712
                )
                .order_by(VisitingFaculty.name)
            ).all()
        )
