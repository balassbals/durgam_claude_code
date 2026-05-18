"""ProgramConfigState — /admin/config/programs (placeholder; read-only detail in Session 6)."""

from __future__ import annotations

from durgam.states.base import BaseState


class ProgramConfigState(BaseState):
    async def load_programs(self) -> None:
        guard = self._config_guard("program", "write")
        if guard is not None:
            return guard
        self._load_nav_entries()
