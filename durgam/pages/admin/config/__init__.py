"""Config module nav registration (M3 + M4 + M5a + M5b).

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
        ("write",     "role_email",                  None),
        ("write",     "letterhead_asset",             None),
        ("write",     "template_asset",                None),
        ("write",     "mental_health_counsellor",       None),
        ("write",     "faculty_mentor_assignment",      None),
        ("write",     "class_teacher_assignment",       None),
        ("write",     "class_coordinator_assignment",   None),
        ("write",     "non_regular_faculty",             None),
        ("write",     "non_owned_course",                None),
        ("write",     "ug_timetable",                    None),
        ("write",     "purchase_procedure_rule",         None),
        ("write",     "purchase_committee_template",     None),
        ("write",     "approval_process",                None),
        ("write",     "designation",                     None),
        ("configure", "leave_sanction_rule",             None),
        ("configure", "announcement_composer_config",     None),
        ("configure", "announcement_category",            None),
        ("configure", "audience_group",                   None),
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
# ── M5a nav entries ─────────────────────────────────────────────────────────────
register(NavEntry(
    label="Role Emails",
    href="/admin/config/role-emails",
    icon="mail",
    group="Config",
    permission_action="write",
    permission_resource="role_email",
))
register(NavEntry(
    label="Letterheads",
    href="/admin/config/letterheads",
    icon="image",
    group="Config",
    permission_action="write",
    permission_resource="letterhead_asset",
))
register(NavEntry(
    label="Templates",
    href="/admin/config/templates",
    icon="file-text",
    group="Config",
    permission_action="write",
    permission_resource="template_asset",
))
# ── M5b nav entries ─────────────────────────────────────────────────────────────
register(NavEntry(
    label="Counsellors",
    href="/admin/config/counsellors",
    icon="heart-pulse",
    group="Config",
    permission_action="write",
    permission_resource="mental_health_counsellor",
))
register(NavEntry(
    label="Faculty Mentors",
    href="/admin/config/faculty-mentors",
    icon="users",
    group="Config",
    permission_action="write",
    permission_resource="faculty_mentor_assignment",
))
register(NavEntry(
    label="Class Teachers",
    href="/admin/config/class-teachers",
    icon="user-check",
    group="Config",
    permission_action="write",
    permission_resource="class_teacher_assignment",
))
register(NavEntry(
    label="Class Coordinators",
    href="/admin/config/class-coordinators",
    icon="user-cog",
    group="Config",
    permission_action="read",
    permission_resource="class_coordinator_assignment",
))
register(NavEntry(
    label="Non-Regular Faculty",
    href="/admin/config/non-regular-faculty",
    icon="briefcase",
    group="Config",
    permission_action="write",
    permission_resource="non_regular_faculty",
))
# Non-Owned Courses: Director family + DAA family (two distinct permission paths)
register(NavEntry(
    label="Non-Owned Courses",
    href="/admin/config/non-owned-courses",
    icon="book-copy",
    group="Config",
    permission_action="write",
    permission_resource="non_owned_course",
))
register(NavEntry(
    label="UG Timetable",
    href="/admin/config/ug-timetable",
    icon="table",
    group="Config",
    permission_action="write",
    permission_resource="ug_timetable",
))
# ── M5b Session 7: Purchase Policy & Approval Config ──────────────────────────
register(NavEntry(
    label="Designations",
    href="/admin/config/designations",
    icon="badge-check",
    group="Config",
    permission_action="write",
    permission_resource="designation",
))
register(NavEntry(
    label="Purchase Rules",
    href="/admin/config/purchase-rules",
    icon="receipt",
    group="Config",
    permission_action="write",
    permission_resource="purchase_procedure_rule",
))
register(NavEntry(
    label="Purchase Committees",
    href="/admin/config/purchase-committees",
    icon="users-round",
    group="Config",
    permission_action="write",
    permission_resource="purchase_committee_template",
))
register(NavEntry(
    label="Approval Processes",
    href="/admin/config/approval-processes",
    icon="workflow",
    group="Config",
    permission_action="write",
    permission_resource="approval_process",
))
# ── M8 nav entries ─────────────────────────────────────────────────────────────
register(NavEntry(
    label="Leave Matrix",
    href="/admin/config/leave-sanction-matrix",
    icon="table-2",
    group="Config",
    permission_action="configure",
    permission_resource="leave_sanction_rule",
))
# ── M9 Announcement config nav entries ─────────────────────────────────────────
register(NavEntry(
    label="Composer Roles",
    href="/admin/config/announcement-composer",
    icon="mic",
    group="Config",
    permission_action="configure",
    permission_resource="announcement_composer_config",
))
register(NavEntry(
    label="Announcement Categories",
    href="/admin/config/announcement-categories",
    icon="tag",
    group="Config",
    permission_action="configure",
    permission_resource="announcement_category",
))
register(NavEntry(
    label="Audience Groups",
    href="/admin/config/audience-groups",
    icon="users",
    group="Config",
    permission_action="configure",
    permission_resource="audience_group",
))
