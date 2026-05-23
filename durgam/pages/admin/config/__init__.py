"""Config module nav registration (M3 + M4).

Import this module to register config nav entries. Called from durgam.py.

Nav visibility (any_scope=True semantics):
  SYSTEM_ADMIN: all tiles — has all write/configure permissions.
  REGISTRAR family: sees Configuration, Vision & Mission, Class Timings, Working Days,
    Academic Years, Holidays, Student Categories.
  HOD (scoped): sees Configuration + Vision & Mission (has dept_vm:write for their dept).
  STUDENT / BASIC_USER: no Config nav — has no write/configure config permissions.

Each nav entry gate must match the page's _config_guard (or _config_guard_any) check.
Entries with a single role path use single-gate; entries visible to multiple role
paths via different permissions use permission_any (OR-list semantics).
"""

from durgam.nav.registry import NavEntry, register

# "Configuration" landing: show to any user who can edit ANY config resource.
# Using permission_any with all write/configure gates (M3 + M4).
register(NavEntry(
    label="Configuration",
    href="/admin/config",
    icon="settings",
    group="Config",
    permission_any=(
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
        ("configure", "academic_year",              None),
        ("write",     "holiday",                    None),
        ("write",     "student_category_count",     None),
        ("write",     "calendar_entry",              None),
    ),
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
# Vision & Mission: Registrar via university_vision_mission:write AND HoD via
# department_vision_mission:write:department → requires permission_any.
register(NavEntry(
    label="Vision & Mission",
    href="/admin/config/vision-mission",
    icon="target",
    group="Config",
    permission_any=(
        ("write", "university_vision_mission", None),
        ("write", "department_vision_mission",  "department"),
    ),
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
# ── M4 nav entries ──────────────────────────────────────────────────────────────
register(NavEntry(
    label="Academic Years",
    href="/admin/config/academic-years",
    icon="calendar-range",
    group="Config",
    permission_action="configure",
    permission_resource="academic_year",
))
register(NavEntry(
    label="Holidays",
    href="/admin/config/holidays",
    icon="calendar-off",
    group="Config",
    permission_action="write",
    permission_resource="holiday",
))
register(NavEntry(
    label="Student Categories",
    href="/admin/config/student-categories",
    icon="users",
    group="Config",
    permission_action="write",
    permission_resource="student_category_count",
))
register(NavEntry(
    label="Calendar",
    href="/admin/config/calendar",
    icon="calendar-days",
    group="Config",
    permission_action="write",
    permission_resource="calendar_entry",
))
