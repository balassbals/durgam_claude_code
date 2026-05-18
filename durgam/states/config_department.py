"""DepartmentConfigState — /admin/config/departments (placeholder; full CRUD in Session 6)."""

from __future__ import annotations

from durgam.states.base import BaseState


class DepartmentConfigState(BaseState):
    async def load_departments(self) -> None:
        guard = self._config_guard("department", "write")
        if guard is not None:
            return guard
        self._load_nav_entries()
