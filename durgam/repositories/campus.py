"""CampusRepository — queries for the Campus model (§8.2)."""

from uuid import UUID

from sqlmodel import Session, func, select

from durgam.models.campus import Campus
from durgam.repositories.base import BaseRepository


class CampusRepository(BaseRepository[Campus]):
    def __init__(self, session: Session) -> None:
        super().__init__(Campus, session)

    def get_by_code(self, code: str) -> Campus | None:
        return self._session.exec(
            select(Campus).where(
                Campus.code == code,
                Campus.is_deleted == False,  # noqa: E712
            )
        ).first()

    def count_departments(self, campus_id: UUID) -> int:
        """Count active departments that reference this campus (main or via join row).

        Used by the service-layer hard-delete guard. Double-counting is acceptable
        because the guard only needs to know if count > 0.
        """
        # Deferred import avoids circular dependency between campus and department repos.
        from durgam.models.department import Department, DepartmentCampus

        n_main = self._session.exec(
            select(func.count(Department.id)).where(
                Department.main_campus_id == campus_id,
                Department.is_deleted == False,  # noqa: E712
            )
        ).one()
        n_link = self._session.exec(
            select(func.count(DepartmentCampus.department_id)).where(
                DepartmentCampus.campus_id == campus_id
            )
        ).one()
        return n_main + n_link

    def hard_delete(self, campus: Campus) -> None:
        """Permanently remove a campus row.

        Caller (CampusService) must verify count_departments == 0 and no audit
        rows reference this record before calling.
        """
        self._session.delete(campus)
        self._session.flush()
