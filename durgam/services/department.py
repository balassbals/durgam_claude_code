"""DepartmentService — CRUD for Department and SubDepartment (§8.2, §9.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.department import Department, SubDepartment
from durgam.repositories.department import DepartmentRepository, SubDepartmentRepository
from durgam.services.org_exceptions import HardDeleteBlockedError, OrgServiceError

log = structlog.get_logger(__name__)


class DepartmentError(OrgServiceError):
    pass


class DepartmentService:
    def __init__(
        self,
        dept_repo: DepartmentRepository,
        subdept_repo: SubDepartmentRepository,
    ) -> None:
        self._depts = dept_repo
        self._subdepts = subdept_repo

    def list(self, school_id: UUID | None = None) -> list[Department]:
        if school_id is not None:
            return self._depts.list_by_school(school_id)
        return self._depts.list_active()

    def get(self, dept_id: UUID) -> Department:
        dept = self._depts.get_by_id(dept_id)
        if dept is None:
            raise DepartmentError("Department not found.")
        return dept

    def get_by_code(self, code: str) -> Department:
        dept = self._depts.get_by_code(code)
        if dept is None:
            raise DepartmentError(f"Department '{code}' not found.")
        return dept

    def create(
        self,
        code: str,
        name: str,
        school_id: UUID,
        main_campus_id: UUID,
        actor_id: UUID,
    ) -> Department:
        code = code.strip().upper()
        name = name.strip()
        if not code:
            raise DepartmentError("Department code is required.")
        if not name:
            raise DepartmentError("Department name is required.")
        if self._depts.get_by_code(code) is not None:
            raise DepartmentError(f"Department code '{code}' is already in use.")
        now = datetime.now(UTC)
        dept = Department(
            code=code,
            name=name,
            school_id=school_id,
            main_campus_id=main_campus_id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        dept = self._depts.save(dept)
        log.info("department_created", dept_id=str(dept.id), actor=str(actor_id))
        return dept

    def update(self, dept_id: UUID, fields: dict, actor_id: UUID) -> Department:
        dept = self.get(dept_id)
        for key, value in fields.items():
            setattr(dept, key, value)
        dept.updated_by = actor_id
        dept = self._depts.save(dept)
        log.info("department_updated", dept_id=str(dept_id), actor=str(actor_id))
        return dept

    def soft_delete(self, dept_id: UUID, actor_id: UUID) -> Department:
        dept = self.get(dept_id)
        return self._depts.soft_delete(dept, actor_id)

    def hard_delete(self, dept_id: UUID, actor_id: UUID) -> None:
        dept = self._depts._session.get(Department, dept_id)
        if dept is None:
            raise DepartmentError("Department not found.")
        if not dept.is_deleted:
            raise DepartmentError("Department must be deactivated before permanent deletion.")

        n_programs = self._depts.count_programs(dept_id)
        n_courses = self._depts.count_courses(dept_id)
        n_deps = n_programs + n_courses
        if n_deps > 0:
            raise HardDeleteBlockedError(
                f"Department has {n_programs} program(s) and {n_courses} course(s) "
                "and cannot be permanently deleted."
            )

        from durgam.models.crosscutting import AuditLog
        from sqlmodel import func, select

        n_audit: int = self._depts._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.resource == "department",
                AuditLog.resource_id == str(dept_id),
            )
        ).one()
        if n_audit > 0:
            raise HardDeleteBlockedError(
                f"Department has {n_audit} audit record(s) and cannot be permanently deleted."
            )

        self._depts.hard_delete(dept)
        log.info("department_hard_deleted", dept_id=str(dept_id), actor=str(actor_id))

    # ── Campus link management ────────────────────────────────────────────────

    def add_campus(
        self, dept_id: UUID, campus_id: UUID, actor_id: UUID, *, has_ahod: bool = False
    ) -> None:
        self.get(dept_id)  # verify dept exists and is active
        self._depts.upsert_campus_link(dept_id, campus_id, has_ahod=has_ahod)

    def remove_campus(self, dept_id: UUID, campus_id: UUID, actor_id: UUID) -> None:
        self._depts.remove_campus_link(dept_id, campus_id)

    # ── SubDepartment management ──────────────────────────────────────────────

    def list_sub_departments(self, dept_id: UUID) -> list[SubDepartment]:
        return self._subdepts.list_by_department(dept_id)

    def create_sub_department(
        self,
        code: str,
        name: str,
        parent_dept_id: UUID,
        actor_id: UUID,
    ) -> SubDepartment:
        code = code.strip().upper()
        name = name.strip()
        if not code:
            raise DepartmentError("Sub-department code is required.")
        if not name:
            raise DepartmentError("Sub-department name is required.")
        if self._subdepts.get_by_code(code) is not None:
            raise DepartmentError(f"Sub-department code '{code}' is already in use.")
        self.get(parent_dept_id)  # verify parent exists
        now = datetime.now(UTC)
        subdept = SubDepartment(
            code=code,
            name=name,
            parent_department_id=parent_dept_id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self._subdepts.save(subdept)

    def soft_delete_sub_department(
        self, subdept_id: UUID, actor_id: UUID
    ) -> SubDepartment:
        subdept = self._subdepts.get_by_id(subdept_id)
        if subdept is None:
            raise DepartmentError("Sub-department not found.")
        return self._subdepts.soft_delete(subdept, actor_id)
