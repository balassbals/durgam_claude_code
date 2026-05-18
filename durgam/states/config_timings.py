"""ClassTimingsConfigState and WorkingDaysConfigState — placeholder states (Session 7).

Session 7 will expand these with get/save singleton logic and rx.form edit forms.
"""

from __future__ import annotations

from durgam.states.base import BaseState


class ClassTimingsConfigState(BaseState):
    async def load_class_timings(self) -> None:
        guard = self._config_guard("class_timings_config", "configure")
        if guard is not None:
            return guard
        self._load_nav_entries()


class WorkingDaysConfigState(BaseState):
    async def load_working_days(self) -> None:
        guard = self._config_guard("working_days_config", "configure")
        if guard is not None:
            return guard
        self._load_nav_entries()
