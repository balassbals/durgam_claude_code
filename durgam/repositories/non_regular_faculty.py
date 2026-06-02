"""NonRegularFacultyRepository — department-scoped, no AY-lock (§9.10, E-003)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import NonRegularFaculty
from durgam.repositories.base import BaseRepository


class NonRegularFacultyRepository(BaseRepository[NonRegularFaculty]):
    def __init__(self, session: Session) -> None:
        super().__init__(NonRegularFaculty, session)

    def list_by_department(self, department_id: UUID) -> list[NonRegularFaculty]:
        return list(
            self._session.exec(
                select(NonRegularFaculty)
                .where(
                    NonRegularFaculty.department_id == department_id,
                    NonRegularFaculty.is_deleted == False,  # noqa: E712
                )
                .order_by(NonRegularFaculty.name)
            ).all()
        )
