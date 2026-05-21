"""ProgramService — CRUD for Program and read-access to sub-entities (§8.2, §9.3 M3).  # noqa: E501

Sub-entity write UI (PEO/PO/PSO forms, regulation editors, scheme builder) defers
to M13. This service provides read methods for all sub-entities and creation via
the seed pathway only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.program import (
    Program,
    ProgramExitLevel,
    ProgramOutcome,
    ProgramRegulation,
    ProgramScheme,
    ProgramSpecialisation,
)
from durgam.repositories.program import ProgramRepository
from durgam.services.org_exceptions import HardDeleteBlockedError, OrgServiceError

log = structlog.get_logger(__name__)


class ProgramError(OrgServiceError):
    pass


class ProgramService:
    def __init__(self, program_repo: ProgramRepository) -> None:
        self._programs = program_repo

    def list(self, department_id: UUID | None = None) -> list[Program]:
        if department_id is not None:
            return self._programs.list_by_department(department_id)
        return self._programs.list_active()

    def get(self, program_id: UUID) -> Program:
        program = self._programs.get_by_id(program_id)
        if program is None:
            raise ProgramError("Program not found.")
        return program

    def get_by_code(self, code: str) -> Program:
        program = self._programs.get_by_code(code)
        if program is None:
            raise ProgramError(f"Program '{code}' not found.")
        return program

    def create(
        self,
        code: str,
        name: str,
        department_id: UUID,
        degree_type: str,
        duration_years: int,
        actor_id: UUID,
    ) -> Program:
        code = code.strip().upper()
        name = name.strip()
        degree_type = degree_type.strip()
        if not code:
            raise ProgramError("Program code is required.")
        if not name:
            raise ProgramError("Program name is required.")
        if duration_years < 1:
            raise ProgramError("Duration must be at least 1 year.")
        if self._programs.get_by_code(code) is not None:
            raise ProgramError(f"Program code '{code}' is already in use.")
        now = datetime.now(UTC)
        program = Program(
            code=code,
            name=name,
            department_id=department_id,
            degree_type=degree_type,
            duration_years=duration_years,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        program = self._programs.save(program)
        log.info("program_created", program_id=str(program.id), actor=str(actor_id))
        return program

    def update(self, program_id: UUID, fields: dict, actor_id: UUID) -> Program:
        program = self.get(program_id)
        for key, value in fields.items():
            setattr(program, key, value)
        program.updated_by = actor_id
        return self._programs.save(program)

    def soft_delete(self, program_id: UUID, actor_id: UUID) -> Program:
        program = self.get(program_id)
        return self._programs.soft_delete(program, actor_id)

    def hard_delete(self, program_id: UUID, actor_id: UUID) -> None:
        program = self._programs._session.get(Program, program_id)
        if program is None:
            raise ProgramError("Program not found.")
        if not program.is_deleted:
            raise ProgramError("Program must be deactivated before permanent deletion.")

        from durgam.models.course import Course
        from sqlmodel import func, select

        n_courses: int = self._programs._session.exec(
            select(func.count(Course.id)).where(
                Course.program_id == program_id,
                Course.is_deleted == False,  # noqa: E712
            )
        ).one()
        if n_courses > 0:
            raise HardDeleteBlockedError(
                f"Program has {n_courses} course(s) and cannot be permanently deleted."
            )

        from durgam.models.crosscutting import AuditLog

        n_audit: int = self._programs._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.resource == "program",
                AuditLog.resource_id == str(program_id),
            )
        ).one()
        if n_audit > 0:
            raise HardDeleteBlockedError(
                f"Program has {n_audit} audit record(s) and cannot be permanently deleted."
            )

        self._programs.hard_delete(program)
        log.info("program_hard_deleted", program_id=str(program_id), actor=str(actor_id))

    # ── Sub-entity read-only access ───────────────────────────────────────────

    def get_outcomes(
        self, program_id: UUID, outcome_type: str | None = None
    ) -> list[ProgramOutcome]:
        if outcome_type:
            return self._programs.list_outcomes_by_type(program_id, outcome_type)
        return self._programs.list_outcomes(program_id)

    def get_regulations(self, program_id: UUID) -> list[ProgramRegulation]:
        return self._programs.list_regulations(program_id)

    def get_schemes(
        self, program_id: UUID, regulation_id: UUID | None = None
    ) -> list[ProgramScheme]:
        return self._programs.list_schemes(program_id, regulation_id)

    def get_scheme_course_ids(self, scheme_id: UUID) -> list[UUID]:
        return self._programs.list_scheme_course_ids(scheme_id)

    def get_specialisations(self, program_id: UUID) -> list[ProgramSpecialisation]:
        return self._programs.list_specialisations(program_id)

    def get_exit_levels(self, program_id: UUID) -> list[ProgramExitLevel]:
        return self._programs.list_exit_levels(program_id)
