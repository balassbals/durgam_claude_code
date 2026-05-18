"""SchoolRepository — queries for the School model (§8.2)."""

from uuid import UUID

from sqlmodel import Session, func, select

from durgam.models.school import School
from durgam.repositories.base import BaseRepository


class SchoolRepository(BaseRepository[School]):
    def __init__(self, session: Session) -> None:
        super().__init__(School, session)

    def list_active(self) -> list[School]:
        """Return all active schools ordered by code (stable alphabetical order)."""
        return list(
            self._session.exec(
                select(School)
                .where(School.is_deleted == False)  # noqa: E712
                .order_by(School.code)  # type: ignore[attr-defined]
            ).all()
        )

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
