"""VisionMissionConfigState — /admin/config/vision-mission (placeholder; edit in Session 7).

Session 7 will expand this state with:
- get/update university vision and missions (Registrar-gated)
- get/update department vision and missions (HoD-gated, scoped)
- listing missions in display_order
"""

from __future__ import annotations

from durgam.states.base import BaseState


class VisionMissionConfigState(BaseState):
    async def load_vision_mission(self) -> None:
        guard = self._config_guard("university_vision_mission", "write")
        if guard is not None:
            return guard
        self._load_nav_entries()
