import reflex as rx

from durgam.config import settings
from durgam.logging import configure_logging
from durgam.pages.admin import index as _admin_nav_register  # noqa: F401 — registers nav entries
from durgam.pages.admin.config import __init__ as _config_nav_register  # noqa: F401 — registers config nav entries
from durgam.pages.audit import __init__ as _audit_nav_register  # noqa: F401 — registers audit nav entry
from durgam.pages.admin.import_users import admin_import_users
from durgam.pages.admin.index import admin_index
from durgam.pages.admin.permissions import AdminPermissionsState, admin_permissions
from durgam.pages.admin.roles import admin_role_create, admin_role_detail, admin_roles
from durgam.pages.admin.user_detail import admin_user_create
from durgam.pages.admin.users import admin_users
from durgam.pages.audit.index import AuditLogState, audit_log
from durgam.pages.change_password import change_password
from durgam.pages.forgot_password import forgot_password
from durgam.pages.index import index
from durgam.pages.login import login
from durgam.pages.reset_password import reset_password
from durgam.pages.shared.permission_check_widget import PermissionCheckState
from durgam.states.admin_bulk_import import BulkImportState
from durgam.states.admin_index import AdminIndexState
from durgam.states.admin_roles import AdminRolesState
from durgam.states.admin_users import AdminUsersState
from durgam.states.auth import AuthState
from durgam.theme import apply_theme

configure_logging(debug=settings.debug)

app = rx.App(style=apply_theme())
app.add_page(
    index,
    route="/",
    # Single handler: resolve session + redirect unauthenticated to /login
    # + redirect must_change_password to /change-password. Merged into one
    # method to avoid Reflex 0.9.x multi-event sequencing issues.
    on_load=AuthState.home_on_load,
)
app.add_page(
    login,
    route="/login",
    # Resolve session only — no redirect (login page is accessible unauthenticated)
    on_load=AuthState.resolve_session,
)
app.add_page(forgot_password, route="/forgot-password")
app.add_page(
    reset_password,
    route="/reset-password",
    on_load=[AuthState.resolve_session, AuthState.load_reset_token],
)
app.add_page(
    change_password,
    route="/change-password",
    # Resolve session + redirect unauthenticated to /login (no must_change loop)
    on_load=AuthState.change_password_on_load,
)

# ── M2 Admin routes ────────────────────────────────────────────────────────────
app.add_page(admin_index, route="/admin", on_load=AdminIndexState.load_stats)
app.add_page(admin_users, route="/admin/users", on_load=AdminUsersState.load_users)
app.add_page(admin_user_create, route="/admin/users/new",
             on_load=[AdminUsersState.load_available_roles, PermissionCheckState.clear_widget])
app.add_page(admin_roles, route="/admin/roles", on_load=AdminRolesState.load_roles)
app.add_page(admin_role_create, route="/admin/roles/new",
             on_load=AdminRolesState.load_roles)
app.add_page(admin_role_detail, route="/admin/roles/[role_id]",
             on_load=[AdminRolesState.load_role_detail, PermissionCheckState.clear_widget])
app.add_page(admin_permissions, route="/admin/permissions",
             on_load=AdminPermissionsState.load_permissions)
app.add_page(admin_import_users, route="/admin/import",
             on_load=BulkImportState.load_import)
app.add_page(audit_log, route="/audit", on_load=AuditLogState.load_audit)

# ── M3 Config routes ────────────────────────────────────────────────────────────
from durgam.pages.admin.config.index import admin_config_index
from durgam.pages.admin.config.campuses import admin_config_campuses
from durgam.pages.admin.config.schools import admin_config_schools
from durgam.pages.admin.config.centres import admin_config_centres
from durgam.states.config_landing import ConfigLandingState
from durgam.states.config_campus import CampusConfigState
from durgam.states.config_school import SchoolConfigState
from durgam.states.config_centre import CentreConfigState

app.add_page(admin_config_index, route="/admin/config",
             on_load=ConfigLandingState.load_config_landing)
app.add_page(admin_config_campuses, route="/admin/config/campuses",
             on_load=CampusConfigState.load_campuses)
app.add_page(admin_config_schools, route="/admin/config/schools",
             on_load=SchoolConfigState.load_schools)
app.add_page(admin_config_centres, route="/admin/config/centres",
             on_load=CentreConfigState.load_centres)

# ── M3 Config placeholder routes (Session 5b) — full implementation in Session 6 and 7
from durgam.pages.admin.config.departments import admin_config_departments
from durgam.pages.admin.config.programs import admin_config_programs
from durgam.pages.admin.config.courses import admin_config_courses
from durgam.pages.admin.config.vision_mission import admin_config_vision_mission
from durgam.pages.admin.config.class_timings import admin_config_class_timings
from durgam.pages.admin.config.working_days import admin_config_working_days
from durgam.states.config_department import DepartmentConfigState
from durgam.states.config_program import ProgramConfigState
from durgam.states.config_course import CourseConfigState
from durgam.states.config_vision_mission import VisionMissionConfigState
from durgam.states.config_timings import ClassTimingsConfigState, WorkingDaysConfigState

app.add_page(admin_config_departments, route="/admin/config/departments",
             on_load=DepartmentConfigState.load_departments)
app.add_page(admin_config_programs, route="/admin/config/programs",
             on_load=ProgramConfigState.load_programs)
app.add_page(admin_config_courses, route="/admin/config/courses",
             on_load=CourseConfigState.load_courses)
app.add_page(admin_config_vision_mission, route="/admin/config/vision-mission",
             on_load=VisionMissionConfigState.load_vision_mission)
app.add_page(admin_config_class_timings, route="/admin/config/class-timings",
             on_load=ClassTimingsConfigState.load_class_timings)
app.add_page(admin_config_working_days, route="/admin/config/working-days",
             on_load=WorkingDaysConfigState.load_working_days)

# ── M3 Session 7 — Dept V&M + About pages ─────────────────────────────────────
from durgam.pages.admin.config.dept_vm import admin_config_dept_vm
from durgam.pages.about import __init__ as _about_nav_register  # noqa: F401 — registers About nav entries
from durgam.pages.about.university import about_university
from durgam.pages.about.departments import about_departments
from durgam.pages.about.dept_detail import about_dept_detail
from durgam.states.config_dept_vm import DeptVMConfigState
from durgam.states.about import AboutUniversityState, AboutDeptListState, AboutDeptDetailState

app.add_page(admin_config_dept_vm,
             route="/admin/config/vision-mission/departments/[dept_code]",
             on_load=DeptVMConfigState.load_dept_vm)
# ── M4 Config routes ────────────────────────────────────────────────────────────
from durgam.pages.admin.config.academic_years import admin_config_academic_years
from durgam.pages.admin.config.holidays import admin_config_holidays
from durgam.pages.admin.config.student_categories import admin_config_student_categories
from durgam.pages.admin.config.calendar_entries import admin_config_calendar
from durgam.states.config_academic_year import AcademicYearConfigState
from durgam.states.config_holiday import HolidayConfigState
from durgam.states.config_student_category import StudentCategoryConfigState
from durgam.states.config_calendar_entry import CalendarEntryConfigState

app.add_page(admin_config_academic_years, route="/admin/config/academic-years",
             on_load=AcademicYearConfigState.load_academic_years)
app.add_page(admin_config_holidays, route="/admin/config/holidays",
             on_load=HolidayConfigState.load_holidays)
app.add_page(admin_config_student_categories, route="/admin/config/student-categories",
             on_load=StudentCategoryConfigState.load_student_categories)
app.add_page(admin_config_calendar, route="/admin/config/calendar",
             on_load=CalendarEntryConfigState.load_entries)

# ── M5a routes ────────────────────────────────────────────────────────────────
from durgam.pages.admin.config.role_emails import admin_config_role_emails
from durgam.states.config_role_email import RoleEmailConfigState

app.add_page(admin_config_role_emails, route="/admin/config/role-emails",
             on_load=RoleEmailConfigState.load_role_emails)

from durgam.pages.admin.config.letterheads import admin_config_letterheads
from durgam.pages.admin.config.templates import admin_config_templates
from durgam.states.config_document_template import LetterheadConfigState, TemplateConfigState

app.add_page(admin_config_letterheads, route="/admin/config/letterheads",
             on_load=LetterheadConfigState.load_letterheads)

app.add_page(admin_config_templates, route="/admin/config/templates",
             on_load=TemplateConfigState.load_templates)

# ── M5b routes ────────────────────────────────────────────────────────────────
from durgam.pages.admin.config.counsellors import admin_config_counsellors
from durgam.pages.admin.config.faculty_mentors import admin_config_faculty_mentors
from durgam.states.config_counsellor import CounsellorConfigState
from durgam.states.config_faculty_mentor import FacultyMentorConfigState

app.add_page(admin_config_counsellors, route="/admin/config/counsellors",
             on_load=CounsellorConfigState.load_counsellors)
app.add_page(admin_config_faculty_mentors, route="/admin/config/faculty-mentors",
             on_load=FacultyMentorConfigState.load_mentors)

from durgam.pages.admin.config.class_teachers import admin_config_class_teachers
from durgam.pages.admin.config.class_coordinators import admin_config_class_coordinators
from durgam.pages.admin.config.non_regular_faculty import admin_config_non_regular_faculty
from durgam.states.config_class_teacher import ClassTeacherConfigState
from durgam.states.config_class_coordinator import ClassCoordinatorConfigState
from durgam.states.config_non_regular_faculty import NonRegularFacultyConfigState

app.add_page(admin_config_class_teachers, route="/admin/config/class-teachers",
             on_load=ClassTeacherConfigState.load_teachers)
app.add_page(admin_config_class_coordinators, route="/admin/config/class-coordinators",
             on_load=ClassCoordinatorConfigState.load_coordinators)
app.add_page(admin_config_non_regular_faculty, route="/admin/config/non-regular-faculty",
             on_load=NonRegularFacultyConfigState.load_visitors)

from durgam.pages.admin.config.non_owned_courses import admin_config_non_owned_courses
from durgam.pages.admin.config.ug_timetable import admin_config_ug_timetable
from durgam.states.config_non_owned_course import NonOwnedCourseConfigState
from durgam.states.config_ug_timetable import UGTimetableConfigState

app.add_page(admin_config_non_owned_courses, route="/admin/config/non-owned-courses",
             on_load=NonOwnedCourseConfigState.load_courses)
app.add_page(admin_config_ug_timetable, route="/admin/config/ug-timetable",
             on_load=UGTimetableConfigState.load_slots)

# ── M5b Session 7: Purchase Policy & Approval Config ────────────────────────
from durgam.pages.admin.config.designations import admin_config_designations
from durgam.pages.admin.config.purchase_rules import admin_config_purchase_rules
from durgam.pages.admin.config.purchase_committees import admin_config_purchase_committees
from durgam.pages.admin.config.approval_processes import admin_config_approval_processes
from durgam.states.config_designation import DesignationConfigState
from durgam.states.config_purchase_rule import PurchaseRuleConfigState
from durgam.states.config_purchase_committee import PurchaseCommitteeConfigState
from durgam.states.config_approval_process import ApprovalProcessConfigState

app.add_page(admin_config_designations, route="/admin/config/designations",
             on_load=DesignationConfigState.load_designations)
app.add_page(admin_config_purchase_rules, route="/admin/config/purchase-rules",
             on_load=PurchaseRuleConfigState.load_rules)
app.add_page(admin_config_purchase_committees, route="/admin/config/purchase-committees",
             on_load=PurchaseCommitteeConfigState.load_templates)
app.add_page(admin_config_approval_processes, route="/admin/config/approval-processes",
             on_load=ApprovalProcessConfigState.load_processes)

# ── M5a authenticated file download API ──────────────────────────────────────
from durgam.api.download import download_file

app._api.add_route("/api/files/{file_id}", download_file, methods=["GET"])

app.add_page(about_university, route="/about/university",
             on_load=AboutUniversityState.load_university_about)
app.add_page(about_departments, route="/about/departments",
             on_load=AboutDeptListState.load_dept_list)
app.add_page(about_dept_detail, route="/about/departments/[dept_code]",
             on_load=AboutDeptDetailState.load_dept_detail)

# ── M7 Approval Requests (Phases 2–3) ─────────────────────────────────────────
from durgam.pages.approvals import __init__ as _approvals_nav_register  # noqa: F401
from durgam.pages.approvals.my_requests import my_requests_page
from durgam.pages.approvals.submit import submit_page
from durgam.pages.approvals.request_detail import request_detail_page
from durgam.pages.approvals.inbox import inbox_page
from durgam.states.approval_requests import (
    ApproverInboxState,
    MyRequestsState,
    RequestDetailState,
    SubmitRequestState,
)

app.add_page(my_requests_page, route="/approvals/my-requests",
             on_load=MyRequestsState.load_my_requests)
app.add_page(submit_page, route="/approvals/submit",
             on_load=SubmitRequestState.load_submit)
app.add_page(request_detail_page, route="/approvals/request/[approval_request_id]",
             on_load=RequestDetailState.load_detail)
app.add_page(inbox_page, route="/approvals/inbox",
             on_load=ApproverInboxState.load_inbox)
