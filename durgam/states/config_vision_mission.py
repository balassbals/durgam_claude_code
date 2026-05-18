"""VisionMissionConfigState — /admin/config/vision-mission (placeholder; edit in Session 7).

Accessible to:
  SYSTEM_ADMIN + REGISTRAR: via university_vision_mission:write:*
  HOD (any department): via department_vision_mission:write:department (any_scope=True)

Session 7 will expand this state with:
  - get/update university vision and missions (Registrar-gated)
  - get/update department vision and missions (HoD-gated, scoped to their dept)
  - ordered mission statement list with add/reorder
"""

from __future__ import annotations

from durgam.states.base import BaseState

_VM_GATES = [
    ("write", "university_vision_mission", None),
    ("write", "department_vision_mission", "department"),
]


class VisionMissionConfigState(BaseState):
    async def load_vision_mission(self) -> None:
        guard = self._config_guard_any(_VM_GATES)
        if guard is not None:
            return guard
        self._load_nav_entries()
