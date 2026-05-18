"""ProgramRepository — queries for Program and all 6 sub-entity models (§8.2).

Sub-entity write UI defers to M13; the repo exposes read methods for all
sub-entities plus creation methods used by the seed pathway.
"""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.program import (
    Program,
    ProgramExitLevel,
    ProgramOutcome,
    ProgramRegulation,
    ProgramScheme,
    ProgramSchemeCourse,
    ProgramSpecialisation,
)
from durgam.repositories.base import BaseRepository


class ProgramRepository(BaseRepository[Program]):
    def __init__(self, session: Session) -> None:
        super().__init__(Program, session)

    def list_active(self) -> list[Program]:
        """Return all active programs ordered by code."""
        return list(
            self._session.exec(
                select(Program)
                .where(Program.is_deleted == False)  # noqa: E712
                .order_by(Program.code)  # type: ignore[attr-defined]
            ).all()
        )

    def get_by_code(self, code: str) -> Program | None:
        return self._session.exec(
            select(Program).where(
                Program.code == code,
                Program.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_by_department(self, department_id: UUID) -> list[Program]:
        return list(
            self._session.exec(
                select(Program).where(
                    Program.department_id == department_id,
                    Program.is_deleted == False,  # noqa: E712
                ).order_by(Program.code)  # type: ignore[attr-defined]
            ).all()
        )

    # ── Sub-entity reads ──────────────────────────────────────────────────────

    def list_outcomes(self, program_id: UUID) -> list[ProgramOutcome]:
        """Return all outcomes ordered by type then display_order."""
        return list(
            self._session.exec(
                select(ProgramOutcome).where(
                    ProgramOutcome.program_id == program_id,
                    ProgramOutcome.is_deleted == False,  # noqa: E712
                ).order_by(
                    ProgramOutcome.outcome_type,  # type: ignore[attr-defined]
                    ProgramOutcome.display_order,  # type: ignore[attr-defined]
                )
            ).all()
        )

    def list_outcomes_by_type(
        self, program_id: UUID, outcome_type: str
    ) -> list[ProgramOutcome]:
        """Return PEOs, POs, or PSOs for a program, ordered by display_order."""
        return list(
            self._session.exec(
                select(ProgramOutcome).where(
                    ProgramOutcome.program_id == program_id,
                    ProgramOutcome.outcome_type == outcome_type,
                    ProgramOutcome.is_deleted == False,  # noqa: E712
                ).order_by(ProgramOutcome.display_order)  # type: ignore[attr-defined]
            ).all()
        )

    def list_regulations(self, program_id: UUID) -> list[ProgramRegulation]:
        return list(
            self._session.exec(
                select(ProgramRegulation).where(
                    ProgramRegulation.program_id == program_id,
                    ProgramRegulation.is_deleted == False,  # noqa: E712
                ).order_by(ProgramRegulation.effective_from_year)  # type: ignore[attr-defined]
            ).all()
        )

    def get_regulation(
        self, program_id: UUID, code: str
    ) -> ProgramRegulation | None:
        return self._session.exec(
            select(ProgramRegulation).where(
                ProgramRegulation.program_id == program_id,
                ProgramRegulation.code == code,
                ProgramRegulation.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_schemes(
        self, program_id: UUID, regulation_id: UUID | None = None
    ) -> list[ProgramScheme]:
        stmt = (
            select(ProgramScheme)
            .where(
                ProgramScheme.program_id == program_id,
                ProgramScheme.is_deleted == False,  # noqa: E712
            )
            .order_by(ProgramScheme.semester)  # type: ignore[attr-defined]
        )
        if regulation_id is not None:
            stmt = stmt.where(ProgramScheme.regulation_id == regulation_id)
        return list(self._session.exec(stmt).all())

    def list_scheme_course_ids(self, scheme_id: UUID) -> list[UUID]:
        """Return course UUIDs linked to a scheme of instruction."""
        rows = self._session.exec(
            select(ProgramSchemeCourse).where(
                ProgramSchemeCourse.scheme_id == scheme_id
            )
        ).all()
        return [r.course_id for r in rows]

    def list_specialisations(self, program_id: UUID) -> list[ProgramSpecialisation]:
        return list(
            self._session.exec(
                select(ProgramSpecialisation).where(
                    ProgramSpecialisation.program_id == program_id,
                    ProgramSpecialisation.is_deleted == False,  # noqa: E712
                ).order_by(ProgramSpecialisation.code)  # type: ignore[attr-defined]
            ).all()
        )

    def list_exit_levels(self, program_id: UUID) -> list[ProgramExitLevel]:
        return list(
            self._session.exec(
                select(ProgramExitLevel).where(
                    ProgramExitLevel.program_id == program_id,
                    ProgramExitLevel.is_deleted == False,  # noqa: E712
                ).order_by(ProgramExitLevel.required_credits)  # type: ignore[attr-defined]
            ).all()
        )

    # ── Sub-entity creation (seed pathway; rich UI defers to M13) ─────────────

    def create_outcome(
        self,
        program_id: UUID,
        outcome_type: str,
        code: str,
        description: str,
        display_order: int,
        actor_id: UUID | None = None,
    ) -> ProgramOutcome:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        outcome = ProgramOutcome(
            program_id=program_id,
            outcome_type=outcome_type,
            code=code,
            description=description,
            display_order=display_order,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(outcome)
        self._session.flush()
        self._session.refresh(outcome)
        return outcome

    def add_scheme_course(self, scheme_id: UUID, course_id: UUID) -> None:
        existing = self._session.exec(
            select(ProgramSchemeCourse).where(
                ProgramSchemeCourse.scheme_id == scheme_id,
                ProgramSchemeCourse.course_id == course_id,
            )
        ).first()
        if existing is None:
            link = ProgramSchemeCourse(scheme_id=scheme_id, course_id=course_id)
            self._session.add(link)
            self._session.flush()

    def remove_scheme_course(self, scheme_id: UUID, course_id: UUID) -> None:
        link = self._session.exec(
            select(ProgramSchemeCourse).where(
                ProgramSchemeCourse.scheme_id == scheme_id,
                ProgramSchemeCourse.course_id == course_id,
            )
        ).first()
        if link is not None:
            self._session.delete(link)
            self._session.flush()
