"""AdminProgramsState — program list + 6-tab read-only detail (/admin/config/programs)."""

from __future__ import annotations

from uuid import UUID

from durgam.db import open_session
from durgam.repositories.program import ProgramRepository
from durgam.services.program import ProgramService
from durgam.states.base import BaseState


def _prog_svc(session) -> ProgramService:
    return ProgramService(program_repo=ProgramRepository(session))


class AdminProgramsState(BaseState):
    # List
    programs: list[dict] = []
    loading: bool = True

    # Detail view
    detail_program_id: str = ""
    detail_code: str = ""
    detail_name: str = ""
    detail_degree_type: str = ""
    detail_duration_years: str = ""
    detail_active_tab: str = "overview"
    show_detail: bool = False

    # Sub-entity data (loaded when detail opens)
    detail_peos: list[dict] = []
    detail_pos: list[dict] = []
    detail_psos: list[dict] = []
    detail_regulations: list[dict] = []
    detail_schemes: list[dict] = []
    detail_specialisations: list[dict] = []
    detail_exit_levels: list[dict] = []

    async def load_programs(self) -> None:
        guard = self._config_guard("program", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.programs = []  # reset before query (page-on-load data refresh rule)
        self.show_detail = False
        with open_session() as session:
            for p in _prog_svc(session).list():
                self.programs.append({
                    "id": str(p.id),
                    "code": p.code,
                    "name": p.name,
                    "degree_type": p.degree_type,
                    "duration_years": str(p.duration_years),
                })
        self.loading = False
        self._load_nav_entries()

    async def open_detail(self, program_id: str) -> None:
        self.detail_program_id = program_id
        self.detail_active_tab = "overview"
        self.show_detail = True

        # Reset sub-entity lists before loading
        self.detail_peos = []
        self.detail_pos = []
        self.detail_psos = []
        self.detail_regulations = []
        self.detail_schemes = []
        self.detail_specialisations = []
        self.detail_exit_levels = []

        with open_session() as session:
            svc = _prog_svc(session)
            prog = svc.get(UUID(program_id))
            # Read all needed attributes inside the session block
            self.detail_code = prog.code
            self.detail_name = prog.name
            self.detail_degree_type = prog.degree_type
            self.detail_duration_years = str(prog.duration_years)

            # PEOs, POs, PSOs
            outcomes = svc.get_outcomes(UUID(program_id))
            for o in outcomes:
                row = {"code": o.code, "description": o.description}
                if o.outcome_type == "PEO":
                    self.detail_peos.append(row)
                elif o.outcome_type == "PO":
                    self.detail_pos.append(row)
                elif o.outcome_type == "PSO":
                    self.detail_psos.append(row)

            # Regulations
            regs = svc.get_regulations(UUID(program_id))
            for r in regs:
                self.detail_regulations.append({
                    "code": r.code,
                    "effective_from_year": str(r.effective_from_year),
                    "description": r.description or "",
                })

            # Schemes — collect course codes per scheme
            from durgam.models.course import Course

            prog_repo = ProgramRepository(session)
            schemes = svc.get_schemes(UUID(program_id))
            for s in schemes:
                course_ids = prog_repo.list_scheme_course_ids(s.id)
                course_codes: list[str] = []
                for cid in course_ids:
                    c = session.get(Course, cid)
                    if c:
                        course_codes.append(c.code)
                self.detail_schemes.append({
                    "semester": str(s.semester),
                    "total_credits": str(s.total_credits),
                    "course_codes": ", ".join(course_codes) if course_codes else "—",
                })

            # Specialisations
            specs = svc.get_specialisations(UUID(program_id))
            for sp in specs:
                self.detail_specialisations.append({"code": sp.code, "name": sp.name})

            # Exit levels
            exits = svc.get_exit_levels(UUID(program_id))
            for e in exits:
                self.detail_exit_levels.append({
                    "level_name": e.level_name,
                    "required_credits": str(e.required_credits),
                })

    def close_detail(self) -> None:
        self.show_detail = False
        self.detail_program_id = ""

    def set_detail_active_tab(self, tab: str) -> None:
        self.detail_active_tab = tab


# durgam.py imports ProgramConfigState — alias to keep import unchanged
ProgramConfigState = AdminProgramsState
