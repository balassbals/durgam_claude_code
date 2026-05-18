"""Config module nav registration (M3).

Import this module to register config nav entries. Called from durgam.py.

The "Configuration" group is visible to users who can edit ANY config resource:
- SYSTEM_ADMIN: all write/configure permissions → sees all 9 tiles
- REGISTRAR family: university_vision_mission:write:*, class_timings:configure,
  working_days:configure → sees 3 tiles (Vision & Mission, Class Timings, Working Days)
- HOD: has department_vision_mission:write:department (scoped) — scoped permissions
  are NOT matchable by the nav registry (scope_id=None check; M2 scope discrimination).
  HOD accesses dept vision/mission via the department detail page (Session 6+).
- STUDENT / BASIC_USER: no write/configure permissions → no Config nav.

Each nav entry is gated by the SAME write/configure permission that the target
page's _config_guard checks. Nav gate must match page guard (M3 pattern rule).
"""

from durgam.nav.registry import NavEntry, register

# The "Configuration" landing entry uses university_vision_mission:write:* so
# REGISTRAR (who has this) sees the landing page; campus:write:* alone would hide it.
register(NavEntry(
    label="Configuration",
    href="/admin/config",
    icon="settings",
    group="Config",
    permission_action="write",
    permission_resource="university_vision_mission",
))
register(NavEntry(
    label="Campuses",
    href="/admin/config/campuses",
    icon="map-pin",
    group="Config",
    permission_action="write",
    permission_resource="campus",
))
register(NavEntry(
    label="Schools",
    href="/admin/config/schools",
    icon="graduation-cap",
    group="Config",
    permission_action="write",
    permission_resource="school",
))
register(NavEntry(
    label="Departments",
    href="/admin/config/departments",
    icon="building",
    group="Config",
    permission_action="write",
    permission_resource="department",
))
register(NavEntry(
    label="Centres",
    href="/admin/config/centres",
    icon="star",
    group="Config",
    permission_action="write",
    permission_resource="centre",
))
register(NavEntry(
    label="Programs",
    href="/admin/config/programs",
    icon="book",
    group="Config",
    permission_action="write",
    permission_resource="program",
))
register(NavEntry(
    label="Courses",
    href="/admin/config/courses",
    icon="book-open",
    group="Config",
    permission_action="write",
    permission_resource="course",
))
register(NavEntry(
    label="Vision & Mission",
    href="/admin/config/vision-mission",
    icon="target",
    group="Config",
    permission_action="write",
    permission_resource="university_vision_mission",
))
register(NavEntry(
    label="Class Timings",
    href="/admin/config/class-timings",
    icon="clock",
    group="Config",
    permission_action="configure",
    permission_resource="class_timings_config",
))
register(NavEntry(
    label="Working Days",
    href="/admin/config/working-days",
    icon="calendar",
    group="Config",
    permission_action="configure",
    permission_resource="working_days_config",
))
