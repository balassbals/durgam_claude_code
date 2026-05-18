"""SchoolRepository — queries for the School model (§8.2)."""

from uuid import UUID

from sqlmodel import Session, func, select

from durgam.models.school import School
from durgam.repositories.base import BaseRepository


class SchoolRepository(BaseRepository[School]):
    def __init__(self, session: Session) -> None:
        super().__init__(School, session)

    def get_by_code(self, code: str) -> School | None:
        return self._session.exec(
            select(School).where(
                School.code == code,
                School.is_deleted == False,  # noqa: E712
            )
        ).first()

    def count_departments(self, school_id: UUID) -> int:
        """Count active departments belonging to this school."""
        from durgam.models.department import Department

        return self._session.exec(
            select(func.count(Department.id)).where(
                Department.school_id == school_id,
                Department.is_deleted == False,  # noqa: E712
            )
        ).one()

    def hard_delete(self, school: School) -> None:
        self._session.delete(school)
        self._session.flush()
