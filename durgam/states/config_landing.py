"""ConfigLandingState — /admin/config landing page."""

from __future__ import annotations

from durgam.states.base import BaseState


class ConfigLandingState(BaseState):
    async def load_config_landing(self) -> None:
        guard = self._config_guard("campus")
        if guard is not None:
            return guard
        self._load_nav_entries()
