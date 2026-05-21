"""DepartmentRepository and SubDepartmentRepository (§8.2).

Both classes live here because sub-departments are always managed within the
context of a parent department (DepartmentService orchestrates both).
"""

from uuid import UUID

from sqlmodel import Session, func, select

from durgam.models.department import (
    Department,
    DepartmentCampus,
    SubDepartment,
    SubDepartmentCampus,
)
from durgam.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    def __init__(self, session: Session) -> None:
        super().__init__(Department, session)

    def list_active(self) -> list[Department]:
        """Return all active departments ordered by code."""
        return list(
            self._session.exec(
                select(Department)
                .where(Department.is_deleted == False)  # noqa: E712
                .order_by(Department.code)  # type: ignore[attr-defined]
            ).all()
        )

    def get_by_code(self, code: str) -> Department | None:
        return self._session.exec(
            select(Department).where(
                Department.code == code,
                Department.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_by_school(self, school_id: UUID) -> list[Department]:
        return list(
            self._session.exec(
                select(Department).where(
                    Department.school_id == school_id,
                    Department.is_deleted == False,  # noqa: E712
                ).order_by(Department.code)  # type: ignore[attr-defined]
            ).all()
        )

    def list_by_campus(self, campus_id: UUID) -> list[Department]:
        """Return departments that operate in the given campus (via join table)."""
        return list(
            self._session.exec(
                select(Department)
                .join(
                    DepartmentCampus,
                    DepartmentCampus.department_id == Department.id,  # type: ignore[arg-type]
                )
                .where(
                    DepartmentCampus.campus_id == campus_id,
                    Department.is_deleted == False,  # noqa: E712
                )
                .order_by(Department.code)  # type: ignore[attr-defined]
            ).all()
        )

    def list_campus_links(self, department_id: UUID) -> list[DepartmentCampus]:
        return list(
            self._session.exec(
                select(DepartmentCampus).where(
                    DepartmentCampus.department_id == department_id
                )
            ).all()
        )

    def upsert_campus_link(
        self, department_id: UUID, campus_id: UUID, *, has_ahod: bool = False
    ) -> None:
        existing = self._session.exec(
            select(DepartmentCampus).where(
                DepartmentCampus.department_id == department_id,
                DepartmentCampus.campus_id == campus_id,
            )
        ).first()
        if existing is None:
            link = DepartmentCampus(
                department_id=department_id,
                campus_id=campus_id,
                has_ahod=has_ahod,
            )
            self._session.add(link)
        elif existing.has_ahod != has_ahod:
            existing.has_ahod = has_ahod
            self._session.add(existing)
        self._session.flush()

    def remove_campus_link(self, department_id: UUID, campus_id: UUID) -> None:
        link = self._session.exec(
            select(DepartmentCampus).where(
                DepartmentCampus.department_id == department_id,
                DepartmentCampus.campus_id == campus_id,
            )
        ).first()
        if link is not None:
            self._session.delete(link)
            self._session.flush()

    def count_programs(self, department_id: UUID) -> int:
        """Count active programs primarily owned by this department."""
        from durgam.models.program import Program

        return self._session.exec(
            select(func.count(Program.id)).where(
                Program.department_id == department_id,
                Program.is_deleted == False,  # noqa: E712
            )
        ).one()

    def count_courses(self, department_id: UUID) -> int:
        """Count active courses belonging to this department."""
        from durgam.models.course import Course

        return self._session.exec(
            select(func.count(Course.id)).where(
                Course.department_id == department_id,
                Course.is_deleted == False,  # noqa: E712
            )
        ).one()

    def hard_delete(self, department: Department) -> None:
        self._session.delete(department)
        self._session.flush()


class SubDepartmentRepository(BaseRepository[SubDepartment]):
    def __init__(self, session: Session) -> None:
        super().__init__(SubDepartment, session)

    def get_by_code(self, code: str) -> SubDepartment | None:
        return self._session.exec(
            select(SubDepartment).where(
                SubDepartment.code == code,
                SubDepartment.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_by_department(self, parent_department_id: UUID) -> list[SubDepartment]:
        return list(
            self._session.exec(
                select(SubDepartment).where(
                    SubDepartment.parent_department_id == parent_department_id,
                    SubDepartment.is_deleted == False,  # noqa: E712
                ).order_by(SubDepartment.code)  # type: ignore[attr-defined]
            ).all()
        )

    def list_campus_links(
        self, sub_department_id: UUID
    ) -> list[SubDepartmentCampus]:
        return list(
            self._session.exec(
                select(SubDepartmentCampus).where(
                    SubDepartmentCampus.sub_department_id == sub_department_id
                )
            ).all()
        )

    def upsert_campus_link(
        self, sub_department_id: UUID, campus_id: UUID
    ) -> None:
        existing = self._session.exec(
            select(SubDepartmentCampus).where(
                SubDepartmentCampus.sub_department_id == sub_department_id,
                SubDepartmentCampus.campus_id == campus_id,
            )
        ).first()
        if existing is None:
            link = SubDepartmentCampus(
                sub_department_id=sub_department_id, campus_id=campus_id
            )
            self._session.add(link)
            self._session.flush()

    def remove_campus_link(
        self, sub_department_id: UUID, campus_id: UUID
    ) -> None:
        link = self._session.exec(
            select(SubDepartmentCampus).where(
                SubDepartmentCampus.sub_department_id == sub_department_id,
                SubDepartmentCampus.campus_id == campus_id,
            )
        ).first()
        if link is not None:
            self._session.delete(link)
            self._session.flush()
