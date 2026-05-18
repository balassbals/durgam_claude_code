"""ConfigLandingState — /admin/config landing page with permission-filtered tiles."""

from __future__ import annotations

from uuid import UUID

from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.states.base import BaseState

# Gates for the landing page: user needs at least one of these to reach the page.
_LANDING_GATES: list[tuple[str, str, str | None]] = [
    ("write",     "campus",                    None),
    ("write",     "school",                    None),
    ("write",     "department",                None),
    ("write",     "centre",                    None),
    ("write",     "program",                   None),
    ("write",     "course",                    None),
    ("write",     "university_vision_mission", None),
    ("write",     "department_vision_mission", "department"),
    ("configure", "class_timings_config",      None),
    ("configure", "working_days_config",        None),
]

# Tile definitions: (label, href, description, permission_gates).
# permission_gates is an OR-list — tile shows if user passes any gate.
_ALL_TILES: list[tuple[str, str, str, list[tuple[str, str, str | None]]]] = [
    (
        "Campuses", "/admin/config/campuses",
        "Manage the four SSSIHL campuses",
        [("write", "campus", None)],
    ),
    (
        "Schools", "/admin/config/schools",
        "Four academic schools headed by Deans",
        [("write", "school", None)],
    ),
    (
        "Departments", "/admin/config/departments",
        "Ten departments with school and campus mappings",
        [("write", "department", None)],
    ),
    (
        "Centres", "/admin/config/centres",
        "Centres of Excellence",
        [("write", "centre", None)],
    ),
    (
        "Programs", "/admin/config/programs",
        "Academic programs with outcomes and regulations",
        [("write", "program", None)],
    ),
    (
        "Courses", "/admin/config/courses",
        "Course catalogue (basic fields)",
        [("write", "course", None)],
    ),
    (
        "Vision & Mission", "/admin/config/vision-mission",
        "University and department vision/mission statements",
        [
            ("write", "university_vision_mission", None),
            ("write", "department_vision_mission", "department"),
        ],
    ),
    (
        "Class Timings", "/admin/config/class-timings",
        "Institute-wide period timings",
        [("configure", "class_timings_config", None)],
    ),
    (
        "Working Days", "/admin/config/working-days",
        "5-day or 6-day work week",
        [("configure", "working_days_config", None)],
    ),
]


class ConfigLandingState(BaseState):
    # Tiles the current user can actually reach — filtered at load time.
    config_tiles: list[dict[str, str]] = []

    async def load_config_landing(self) -> None:
        # Use _config_guard_any: page accessible if user can edit ANY config resource.
        # HoD (department_vision_mission:write:department) passes this check.
        guard = self._config_guard_any(_LANDING_GATES)
        if guard is not None:
            return guard

        self.config_tiles = []
        user_id = UUID(self.current_user_id)

        with open_session() as session:
            for label, href, description, gates in _ALL_TILES:
                # Tile visible if user passes any permission gate (any_scope=True).
                if any(
                    can(user_id, action, resource, scope_type, None, session, any_scope=True)
                    for (action, resource, scope_type) in gates
                ):
                    self.config_tiles.append({
                        "label": label,
                        "href": href,
                        "description": description,
                    })

        self._load_nav_entries()
