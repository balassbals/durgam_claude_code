"""ConfigLandingState — /admin/config landing page."""

from __future__ import annotations

from durgam.states.base import BaseState


class ConfigLandingState(BaseState):
    async def load_config_landing(self) -> None:
        # Gate on a write permission so STUDENT and BASIC_USER cannot reach this page.
        # REGISTRAR has university_vision_mission:write:* which covers them.
        # SYSTEM_ADMIN has all write permissions.
        guard = self._config_guard("university_vision_mission", "write")
        if guard is not None:
            return guard
        self._load_nav_entries()
