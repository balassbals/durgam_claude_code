"""ConfigLandingState — /admin/config landing page with permission-filtered tiles."""

from __future__ import annotations

from uuid import UUID

from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.states.base import BaseState

# (resource, action, label, href, description)
_ALL_TILES = [
    ("campus",                    "write",     "Campuses",         "/admin/config/campuses",        "Manage the four SSSIHL campuses"),
    ("school",                    "write",     "Schools",          "/admin/config/schools",         "Four academic schools headed by Deans"),
    ("department",                "write",     "Departments",      "/admin/config/departments",     "Ten departments with school and campus mappings"),
    ("centre",                    "write",     "Centres",          "/admin/config/centres",         "Centres of Excellence"),
    ("program",                   "write",     "Programs",         "/admin/config/programs",        "Academic programs with outcomes and regulations"),
    ("course",                    "write",     "Courses",          "/admin/config/courses",         "Course catalogue (basic fields)"),
    ("university_vision_mission", "write",     "Vision & Mission", "/admin/config/vision-mission",  "University and department vision/mission statements"),
    ("class_timings_config",      "configure", "Class Timings",    "/admin/config/class-timings",   "Institute-wide period timings"),
    ("working_days_config",       "configure", "Working Days",     "/admin/config/working-days",    "5-day or 6-day work week"),
]


class ConfigLandingState(BaseState):
    # Tiles the current user can actually reach — populated at load time
    # by checking each page's write/configure permission.
    config_tiles: list[dict[str, str]] = []

    async def load_config_landing(self) -> None:
        # Gate on university_vision_mission:write:* so REGISTRAR (and sys_admin)
        # can reach the landing while STUDENT/BASIC_USER cannot.
        guard = self._config_guard("university_vision_mission", "write")
        if guard is not None:
            return guard

        self.config_tiles = []
        user_id = UUID(self.current_user_id)

        with open_session() as session:
            for resource, action, label, href, description in _ALL_TILES:
                if can(user_id, action, resource, None, None, session):
                    self.config_tiles.append({
                        "label": label,
                        "href": href,
                        "description": description,
                    })

        self._load_nav_entries()
