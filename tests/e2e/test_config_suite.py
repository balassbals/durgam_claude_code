"""Playwright E2E config suite — M3+M4+M5a gate: Configuration.

Covers all admin config flows: campus, school, centre, department, course,
program read-only detail, vision/mission (university + department), class
timings, working days, and route-protection checks (M3). Also covers M4:
academic year, holiday, student category, and calendar entry config.
M5a: role email, letterhead, template config.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run.

Seeded read-only users (account state never mutated):
  sys_admin     / SysAdmin_Dev1!XZ      — SYSTEM_ADMIN
  registrar_user / Registrar_Dev1!XZ   — REGISTRAR
  hod_dmacs     / HodDmacs_Dev1!XZ     — HOD scoped to DMACS
  iqac_user     / IqacCoord_Dev1!XZ    — IQAC_COORDINATOR
  student_001   / Student_Dev1!XZ      — STUDENT (used only for route-protection)

CRUD tests:
  - Use static entity codes (TST, TSC, TCE, TDE, TST101) that are NOT seeded.
  - Each test pre-cleans any leftover entity with that code at the start.
  - Each test also cleans up in a finally block so failures don't leak state.
  - Both measures together ensure order-independence and determinism.

V&M/singletons:
  - Edit using seeded editor accounts (registrar_user, hod_dmacs).
  - State is restored to a known value at the end of each test.

File upload tests (M5a):
  - rx.upload renders a hidden <input type="file"> via react-dropzone.
  - Playwright targets it with page.locator('input[type="file"]').set_input_files().
  - The on_drop handler fires automatically when the file is set.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import (
    BASE_URL,
    _delete_university_missions_matching,
    _hard_delete_academic_year_by_code,
    _hard_delete_by_code,
    _hard_delete_calendar_entries_by_title,
    _hard_delete_dept_by_code,
    _hard_delete_letterhead_by_role,
    _hard_delete_template_by_type,
    _login,
    _logout,
    _wait_for_admin_page,
)

_TEST_LH_DOCX = str(Path(__file__).parent / "_test_letterhead.docx")
_TEST_DOCX = str(Path(__file__).parent / "_test_template.docx")

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E") != "1",
    reason="Set DURGAM_E2E=1 and start the app stack to run E2E tests",
)

_ADMIN_USER = "sys_admin"
_ADMIN_PASS = "SysAdmin_Dev1!XZ"
_REGISTRAR_USER = "registrar_user"
_REGISTRAR_PASS = "Registrar_Dev1!XZ"
_HOD_USER = "hod_dmacs"
_HOD_PASS = "HodDmacs_Dev1!XZ"
_IQAC_USER = "iqac_user"
_IQAC_PASS = "IqacCoord_Dev1!XZ"
_STUDENT_USER = "student_001"
_STUDENT_PASS = "Student_Dev1!XZ"

# Stable entity codes used by CRUD tests — pre-cleaned before each test.
_CAMPUS_CODE = "TST"
_SCHOOL_CODE = "TSC"
_CENTRE_CODE = "TCE"
_DEPT_CODE = "TDE"
_COURSE_CODE = "TST101"
_LH_TEST_ROLE = "DEPUTY_REGISTRAR"
_TPL_TEST_TYPE = "bos"


# ── Route Protection ─────────────────────────────────────────────────────────

class TestConfigRouteProtection:
    """student_001 is blocked from every /admin/config/* route."""

    _PROTECTED_ROUTES = [
        "/admin/config",
        "/admin/config/campuses",
        "/admin/config/schools",
        "/admin/config/centres",
        "/admin/config/departments",
        "/admin/config/programs",
        "/admin/config/courses",
        "/admin/config/vision-mission",
        "/admin/config/class-timings",
        "/admin/config/working-days",
        "/admin/config/academic-years",
        "/admin/config/holidays",
        "/admin/config/student-categories",
        "/admin/config/calendar",
        "/admin/config/role-emails",
        "/admin/config/letterheads",
        "/admin/config/templates",
    ]

    @pytest.mark.parametrize("route", _PROTECTED_ROUTES)
    def test_student_blocked_from_config_route(self, page: Page, route: str) -> None:
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}{route}")
        page.wait_for_url(lambda url: route not in url, timeout=10_000)
        _logout(page)

    def test_unauthenticated_redirected_to_login(self, page: Page) -> None:
        page.goto(f"{BASE_URL}/admin/config")
        page.wait_for_url(f"{BASE_URL}/login", timeout=10_000)


# ── Campus CRUD ───────────────────────────────────────────────────────────────

class TestCampusCRUD:
    def test_create_edit_softdelete_campus(self, page: Page) -> None:
        # Pre-clean any leftover entity from a previous failed run.
        _hard_delete_by_code("campuses", _CAMPUS_CODE)
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/config/campuses")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New Campus")

            # Create
            page.get_by_text("+ New Campus").click()
            expect(page.get_by_placeholder("e.g. PSN")).to_be_visible(timeout=10_000)
            page.get_by_placeholder("e.g. PSN").fill(_CAMPUS_CODE)
            page.get_by_placeholder("Campus name").fill("Test Campus E2E")
            page.get_by_role("button", name="Save").click()
            # Entity name visible = save succeeded; flash cleared by _config_guard in load_campuses
            expect(page.get_by_text("Test Campus E2E", exact=True)).to_be_visible(timeout=15_000)

            # Edit — navigate into the same row's kebab.
            # data_table renders in table mode (is_mobile=False); each row is <tr>,
            # cells are <td>. From the text <p>, ".." → <td>, ".." → <tr>.
            row = page.get_by_text("Test Campus E2E", exact=True).locator("..").locator("..")
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Edit").click()
            campus_name_input = page.get_by_placeholder("Campus name")
            expect(campus_name_input).to_be_visible(timeout=10_000)
            campus_name_input.fill("Test Campus E2E Updated")
            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Test Campus E2E Updated", exact=True)).to_be_visible(
                timeout=15_000
            )

            # Soft-delete via kebab
            row_u = page.get_by_text("Test Campus E2E Updated", exact=True).locator(
                ".."
            ).locator("..")
            row_u.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            # Confirm dialog
            expect(page.get_by_text("Deactivate 'Test Campus E2E Updated'?")).to_be_visible(
                timeout=5_000
            )
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Test Campus E2E Updated", exact=True)
            ).not_to_be_visible(timeout=15_000)
        finally:
            _hard_delete_by_code("campuses", _CAMPUS_CODE)


# ── School CRUD ───────────────────────────────────────────────────────────────

class TestSchoolCRUD:
    def test_create_edit_softdelete_school(self, page: Page) -> None:
        _hard_delete_by_code("schools", _SCHOOL_CODE)
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/config/schools")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New School")

            page.get_by_text("+ New School").click()
            expect(page.get_by_placeholder("e.g. SCI")).to_be_visible(timeout=10_000)
            page.get_by_placeholder("e.g. SCI").fill(_SCHOOL_CODE)
            # RC-1: actual placeholder is "Full school name", not "School name"
            page.get_by_placeholder("Full school name").fill("Test School E2E")
            # Failure B: dean_role_code is required by SchoolService.create()
            page.get_by_placeholder("e.g. DEAN_SCI").fill("DEAN_TSC")
            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Test School E2E", exact=True)).to_be_visible(timeout=15_000)

            # Soft-delete
            row = page.get_by_text("Test School E2E", exact=True).locator("..").locator("..")
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Test School E2E", exact=True)
            ).not_to_be_visible(timeout=15_000)
        finally:
            _hard_delete_by_code("schools", _SCHOOL_CODE)


# ── Centre CRUD ───────────────────────────────────────────────────────────────

class TestCentreCRUD:
    def test_create_edit_softdelete_centre(self, page: Page) -> None:
        _hard_delete_by_code("centres_of_excellence", _CENTRE_CODE)
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/config/centres")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New Centre")

            page.get_by_text("+ New Centre").click()
            expect(page.get_by_placeholder("e.g. CMB")).to_be_visible(timeout=10_000)
            page.get_by_placeholder("e.g. CMB").fill(_CENTRE_CODE)
            page.get_by_placeholder("Centre name").fill("Test Centre E2E")
            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Test Centre E2E", exact=True)).to_be_visible(timeout=15_000)

            # Soft-delete
            row = page.get_by_text("Test Centre E2E", exact=True).locator("..").locator("..")
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Test Centre E2E", exact=True)
            ).not_to_be_visible(timeout=15_000)
        finally:
            _hard_delete_by_code("centres_of_excellence", _CENTRE_CODE)


# ── Department CRUD ───────────────────────────────────────────────────────────

class TestDepartmentCRUD:
    def test_create_edit_softdelete_department(self, page: Page) -> None:
        # Use the department-aware helper: deletes department_campuses FK rows first,
        # then departments. Plain _hard_delete_by_code("departments", ...) would raise
        # ForeignKeyViolation because DepartmentCampus rows reference the dept.
        _hard_delete_dept_by_code(_DEPT_CODE)
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/config/departments")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New Department")

            page.get_by_text("+ New Department").click()
            # RC-1: actual placeholder is "Full department name"
            expect(page.get_by_placeholder("e.g. DMACS")).to_be_visible(timeout=10_000)
            page.get_by_placeholder("e.g. DMACS").fill(_DEPT_CODE)
            page.get_by_placeholder("Full department name").fill("Test Dept E2E")

            # RC-3: departments use rx.select.root (Radix, no native <select>).
            # Interact via trigger text → option click.
            page.get_by_text("Select school").click()
            expect(page.get_by_role("option").first).to_be_visible(timeout=10_000)
            page.get_by_role("option").first.click()

            # Failure C: main_campus is also required by save_department validation.
            page.get_by_text("Select main campus").click()
            expect(page.get_by_role("option").first).to_be_visible(timeout=10_000)
            page.get_by_role("option").first.click()

            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Test Dept E2E", exact=True)).to_be_visible(timeout=15_000)

            # Soft-delete
            row = page.get_by_text("Test Dept E2E", exact=True).locator("..").locator("..")
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Test Dept E2E", exact=True)
            ).not_to_be_visible(timeout=15_000)
        finally:
            _hard_delete_dept_by_code(_DEPT_CODE)


# ── Course CRUD ───────────────────────────────────────────────────────────────

class TestCourseCRUD:
    def test_create_edit_softdelete_course(self, page: Page) -> None:
        _hard_delete_by_code("courses", _COURSE_CODE)
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/config/courses")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New Course")

            page.get_by_text("+ New Course").click()
            # RC-1: actual placeholder is "e.g. MAT101" (not "e.g. MA101")
            expect(page.get_by_placeholder("e.g. MAT101")).to_be_visible(timeout=10_000)
            page.get_by_placeholder("e.g. MAT101").fill(_COURSE_CODE)
            page.get_by_placeholder("Course name").fill("Test Course E2E")

            # RC-3: rx.select.root for program and department — click trigger then option.
            page.get_by_text("Select program").click()
            expect(page.get_by_role("option").first).to_be_visible(timeout=10_000)
            page.get_by_role("option").first.click()

            page.get_by_text("Select department").click()
            expect(page.get_by_role("option").first).to_be_visible(timeout=10_000)
            page.get_by_role("option").first.click()

            # RC-2: credits are computed (not an input). Fill lecture hours instead.
            page.locator("input[name='form_lecture']").fill("3")

            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Test Course E2E", exact=True)).to_be_visible(timeout=15_000)

            # Soft-delete
            row = page.get_by_text("Test Course E2E", exact=True).locator("..").locator("..")
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Test Course E2E", exact=True)
            ).not_to_be_visible(timeout=15_000)
        finally:
            _hard_delete_by_code("courses", _COURSE_CODE)


# ── Program read-only detail ──────────────────────────────────────────────────

class TestProgramDetail:
    def test_seeded_program_detail_renders_all_tabs(self, page: Page) -> None:
        """Seeded BSCMATH program detail shows all 6 tab buttons."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/programs")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "BSCMATH")

        # RC-4: open detail via kebab → "View Details" (not by clicking row text).
        row = page.get_by_text("BSCMATH", exact=True).locator("..").locator("..")
        row.get_by_role("button", name="⋮").click()
        page.get_by_role("menuitem", name="View Details").click()

        # RC-4: tabs are plain rx.button(), not rx.tabs.trigger (no ARIA role="tab").
        for tab_name in ("Overview", "Outcomes", "Regulations", "Scheme",
                         "Specialisations", "Exit Levels"):
            expect(page.get_by_role("button", name=tab_name)).to_be_visible(timeout=10_000)


# ── Vision/Mission Admin ──────────────────────────────────────────────────────

class TestVisionMissionAdmin:
    def test_registrar_can_edit_university_vision(self, page: Page) -> None:
        """Registrar can edit and save the university vision."""
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "University Vision")

        page.get_by_text("Edit Vision").click()
        vision_textarea = page.get_by_placeholder("Enter the university vision statement…")
        expect(vision_textarea).to_be_visible(timeout=10_000)
        vision_textarea.fill("To foster knowledge, devotion, and service — updated by E2E.")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("University vision saved.", exact=True)).to_be_visible(
            timeout=15_000
        )
        expect(
            page.get_by_text("To foster knowledge, devotion, and service — updated by E2E.")
        ).to_be_visible(timeout=10_000)

    def test_registrar_can_add_and_remove_university_mission(self, page: Page) -> None:
        """Registrar can add a mission, assert it saved, then remove it.

        Uses a unique-per-run identifier to prevent strict-mode violations from
        accumulated rows across runs. Pre-cleans any leftover "E2E test mission"
        rows before the test body, and cleans up in a finally block.
        """
        test_id = uuid.uuid4().hex[:8]
        mission_text = f"E2E test mission {test_id} — safe to remove."
        # Pre-clean ALL accumulated test mission rows from previous failed runs.
        _delete_university_missions_matching("E2E test mission%")
        try:
            _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
            page.goto(f"{BASE_URL}/admin/config/vision-mission")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "Mission Statements")

            page.get_by_text("+ Add Mission").click()
            mission_textarea = page.get_by_placeholder("Enter mission statement…")
            expect(mission_textarea).to_be_visible(timeout=10_000)
            mission_textarea.fill(mission_text)
            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Mission statement saved.", exact=True)).to_be_visible(
                timeout=15_000
            )
            mission_row = page.get_by_text(mission_text, exact=True)
            expect(mission_row).to_be_visible(timeout=10_000)

            # ONE ".." from <p> reaches the outer hstack; Remove is a descendant.
            # TWO ".." would reach the mission list → strict-mode violation (multiple rows).
            mission_row.locator("..").get_by_role("button", name="Remove").click()
            expect(page.get_by_text("Mission statement removed.", exact=True)).to_be_visible(
                timeout=15_000
            )
            expect(page.get_by_text(mission_text, exact=True)).not_to_be_visible(timeout=5_000)
        finally:
            # Ensure cleanup even if the UI Remove step failed mid-way.
            _delete_university_missions_matching("E2E test mission%")

    def test_sysadmin_sees_department_picker(self, page: Page) -> None:
        """SYSTEM_ADMIN sees the department V&M picker on the vision-mission page.

        RC-5: After Bug 2 fix, only SYSTEM_ADMIN (can_manage_depts=True) sees
        the 'Department Vision & Mission' section. Registrar does NOT see it.
        """
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Department Vision & Mission")
        expect(page.get_by_role("link", name="Edit V&M").first).to_be_visible(timeout=10_000)

    def test_hod_can_edit_department_vision(self, page: Page) -> None:
        """HoD scoped to DMACS can edit DMACS department vision."""
        _login(page, _HOD_USER, _HOD_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission/departments/DMACS")
        page.wait_for_load_state("networkidle")
        # RC-6: wait for "Edit Vision" button (unique, unambiguous anchor).
        expect(page.get_by_text("Edit Vision")).to_be_visible(timeout=15_000)

        page.get_by_text("Edit Vision").click()
        vision_textarea = page.get_by_placeholder("Enter the department vision statement…")
        expect(vision_textarea).to_be_visible(timeout=10_000)
        vision_textarea.fill("DMACS vision — updated by E2E HoD test.")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Department vision saved.", exact=True)).to_be_visible(
            timeout=15_000
        )
        expect(
            page.get_by_text("DMACS vision — updated by E2E HoD test.", exact=True)
        ).to_be_visible(timeout=10_000)

    def test_student_cannot_reach_vm_admin_page(self, page: Page) -> None:
        """student_001 is redirected away from /admin/config/vision-mission."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission")
        page.wait_for_load_state("networkidle")
        page.wait_for_url(lambda url: "/admin/config/vision-mission" not in url, timeout=10_000)


# ── Class Timings ─────────────────────────────────────────────────────────────

class TestClassTimings:
    def test_registrar_can_edit_class_timings(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/class-timings")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Periods per day")

        ppd_input = page.locator("input[name='periods_per_day']")
        expect(ppd_input).to_be_visible(timeout=10_000)
        ppd_input.fill("9")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Class timings saved.", exact=True)).to_be_visible(
            timeout=15_000
        )

        # Verify persisted after reload
        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Periods per day")
        expect(page.locator("input[name='periods_per_day']")).to_have_value("9", timeout=10_000)

        # Reset to seed value (8) so subsequent runs start from known state
        page.locator("input[name='periods_per_day']").fill("8")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Class timings saved.", exact=True)).to_be_visible(
            timeout=5_000
        )


# ── Working Days ──────────────────────────────────────────────────────────────

class TestWorkingDays:
    def test_registrar_can_edit_working_days(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/working-days")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Days per week")

        # Failure E: filter(has_text="6") returns 0 elements because Radix radio group
        # renders text inside nested spans or sibling labels, not as direct button text.
        # Use positional index: nth(0)="5", nth(1)="6".
        page.get_by_role("radio").nth(1).click()
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Working days saved.", exact=True)).to_be_visible(
            timeout=15_000
        )

        # Verify persisted: reload and check the hint text (more reliable than to_be_checked)
        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Days per week")
        # RC-7E: Radix radio 'checked' attribute unreliable; assert on conditional hint text.
        expect(
            page.get_by_text(
                "Working days: Monday · Tuesday · Wednesday · Thursday · Friday · Saturday"
            )
        ).to_be_visible(timeout=10_000)

        # Reset to 5-day week to avoid dirty state for next run
        page.get_by_role("radio").nth(0).click()
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Working days saved.", exact=True)).to_be_visible(
            timeout=5_000
        )

    def test_hod_blocked_from_working_days(self, page: Page) -> None:
        """HoD lacks configure permission and is redirected."""
        _login(page, _HOD_USER, _HOD_PASS)
        page.goto(f"{BASE_URL}/admin/config/working-days")
        page.wait_for_load_state("networkidle")
        page.wait_for_url(lambda url: "/admin/config/working-days" not in url, timeout=10_000)


# ── Academic Year Config (M4) ─────────────────────────────────────────────────

_AY_TEST_CODE = "9999-00"


class TestAcademicYearConfig:
    def test_registrar_sees_seeded_academic_years(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/academic-years")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Academic Year", timeout=15_000)
        expect(page.get_by_text("2025-26", exact=True)).to_be_visible(timeout=10_000)
        _logout(page)

    def test_create_edit_softdelete_academic_year(self, page: Page) -> None:
        _hard_delete_academic_year_by_code(_AY_TEST_CODE)
        try:
            _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
            page.goto(f"{BASE_URL}/admin/config/academic-years")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New Academic Year", timeout=15_000)

            # Create
            page.get_by_role("button", name="+ New Academic Year").click()
            expect(page.get_by_role("heading", name="New Academic Year")).to_be_visible(
                timeout=5_000
            )
            page.get_by_placeholder("e.g. 2025-26").fill(_AY_TEST_CODE)
            page.locator("input[name='form_starts_on']").fill("2099-07-01")
            page.locator("input[name='form_ends_on']").fill("2100-05-31")
            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Academic year saved.", exact=True)).to_be_visible(
                timeout=10_000
            )
            expect(page.get_by_text(_AY_TEST_CODE, exact=True)).to_be_visible(
                timeout=5_000
            )

            # Soft delete via kebab
            row = page.locator("tr", has_text=_AY_TEST_CODE)
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(page.get_by_text("Academic year deactivated.", exact=True)).to_be_visible(
                timeout=10_000
            )
            _logout(page)
        finally:
            _hard_delete_academic_year_by_code(_AY_TEST_CODE)


# ── Holiday Config (M4) ──────────────────────────────────────────────────────

class TestHolidayConfig:
    def test_registrar_sees_seeded_holidays(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/holidays")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Holiday", timeout=15_000)
        # Seeded AY 2025-26 should be pre-selected with seeded holidays
        expect(page.get_by_text("Gandhi Jayanti", exact=True)).to_be_visible(
            timeout=10_000
        )
        _logout(page)


# ── Student Category Config (M4) ─────────────────────────────────────────────

class TestStudentCategoryConfig:
    def test_registrar_sees_student_category_form(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/student-categories")
        page.wait_for_load_state("networkidle")
        expect(
            page.get_by_role("heading", name="Student Category Counts")
        ).to_be_visible(timeout=15_000)
        # Verify form loads with AY selector
        expect(page.get_by_text("Academic Year:", exact=True)).to_be_visible(
            timeout=10_000
        )
        _logout(page)


# ── Calendar Entry Config (M4) ───────────────────────────────────────────────

_CAL_TEST_TITLE = "E2E test entry"


class TestCalendarEntryConfig:
    def test_registrar_sees_seeded_calendar_entries(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/calendar")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Academic Calendar", timeout=15_000)
        # Seeded entries for 2025-26
        expect(page.get_by_text("Semester 1 Begins", exact=True)).to_be_visible(
            timeout=10_000
        )
        expect(page.get_by_text("CIE-1", exact=True)).to_be_visible(timeout=5_000)
        _logout(page)

    def test_create_and_delete_calendar_entry(self, page: Page) -> None:
        test_id = uuid.uuid4().hex[:8]
        title = f"{_CAL_TEST_TITLE} {test_id}"
        _hard_delete_calendar_entries_by_title(f"{_CAL_TEST_TITLE}%")
        try:
            _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
            page.goto(f"{BASE_URL}/admin/config/calendar")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "Academic Calendar", timeout=15_000)

            # Create a Phase 1 entry (Registrar framework type)
            page.get_by_role("button", name="+ New Entry").click()
            expect(page.get_by_role("heading", name="New Calendar Entry")).to_be_visible(
                timeout=5_000
            )
            page.get_by_placeholder("Entry title").fill(title)
            # Select entry type
            type_trigger = page.locator(
                "form .rt-SelectTrigger",
                has_text="Select entry type"
            )
            type_trigger.click()
            page.get_by_role("option", name="Semester Begin").click()
            # Fill dates
            page.locator("input[name='form_starts_at']").fill("2025-08-01T09:00")
            page.locator("input[name='form_ends_at']").fill("2025-08-01T17:00")
            page.get_by_role("button", name="Save").click()
            expect(page.get_by_text("Calendar entry saved.", exact=True)).to_be_visible(
                timeout=10_000
            )
            expect(page.get_by_text(title, exact=True)).to_be_visible(timeout=5_000)

            # Delete via kebab
            row = page.locator("tr", has_text=title)
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Delete").click()
            page.get_by_role("button", name="Delete").click()
            expect(page.get_by_text("Calendar entry deleted.", exact=True)).to_be_visible(
                timeout=10_000
            )
            _logout(page)
        finally:
            _hard_delete_calendar_entries_by_title(f"{_CAL_TEST_TITLE}%")

    def test_export_csv_triggers_download(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/calendar")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Academic Calendar", timeout=15_000)
        # Click CSV export — should trigger download
        with page.expect_download(timeout=15_000) as download_info:
            page.get_by_role("button", name="CSV").click()
        download = download_info.value
        assert "calendar_" in download.suggested_filename
        assert download.suggested_filename.endswith(".csv")
        _logout(page)


# ── Locked AY Enforcement (M4) ──────────────────────────────────────────────

class TestLockedAYEnforcement:
    def test_locked_ay_shows_locked_badge(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/academic-years")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Academic Year", timeout=15_000)
        # 2024-25 is seeded as locked
        row = page.locator("tr", has_text="2024-25")
        expect(row.get_by_text("Yes", exact=True)).to_be_visible(timeout=5_000)
        _logout(page)

    def test_locked_ay_kebab_shows_no_actions(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/academic-years")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Academic Year", timeout=15_000)
        row = page.locator("tr", has_text="2024-25")
        row.get_by_role("button", name="⋮").click()
        expect(page.get_by_text("Locked — no actions")).to_be_visible(timeout=5_000)
        page.keyboard.press("Escape")
        _logout(page)

    def test_holidays_show_locked_badge_on_locked_ay(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/holidays")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Holiday", timeout=15_000)
        # AY selector is Radix rx.select.root — click trigger then option
        ay_trigger = page.locator(".rt-SelectTrigger")
        expect(ay_trigger).to_be_visible(timeout=10_000)
        ay_trigger.click()
        page.get_by_role("option", name="2024-25").click()
        # Should show the AY Locked badge
        expect(page.get_by_text("AY Locked")).to_be_visible(timeout=10_000)
        _logout(page)


# ── RoleEmail Config (M5a) ──────────────────────────────────────────────────

class TestRoleEmailConfig:
    def test_registrar_sees_seeded_role_emails(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/role-emails")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Role Email", timeout=15_000)
        expect(page.get_by_text("REGISTRAR", exact=True).first).to_be_visible(
            timeout=10_000
        )
        _logout(page)

    def test_student_blocked_from_role_emails(self, page: Page) -> None:
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/admin/config/role-emails")
        page.wait_for_url(
            lambda url: "/admin/config/role-emails" not in url, timeout=10_000
        )


# ── Letterhead Config (M5a) ──────────────────────────────────────────────────

class TestLetterheadConfig:
    def test_registrar_upload_and_deactivate_letterhead(self, page: Page) -> None:
        """Registrar uploads a letterhead via file_upload_zone, sees it in the list,
        then deactivates it. Proves the rx.upload + Playwright selector works."""
        _hard_delete_letterhead_by_role(_LH_TEST_ROLE)
        try:
            _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
            page.goto(f"{BASE_URL}/admin/config/letterheads")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ Upload Letterhead", timeout=15_000)

            # Open upload form
            page.get_by_text("+ Upload Letterhead").click()
            expect(
                page.get_by_role("heading", name="Upload Letterhead")
            ).to_be_visible(timeout=5_000)

            # Select role from dropdown (live-sourced from roles table)
            role_trigger = page.locator(".rt-SelectTrigger").first
            expect(role_trigger).to_be_visible(timeout=10_000)
            role_trigger.click()
            page.get_by_role("option", name=_LH_TEST_ROLE).click()
            page.wait_for_timeout(500)

            # Stage file via hidden <input type="file"> rendered by react-dropzone.
            file_input = page.locator("input[type='file']")
            file_input.set_input_files(_TEST_LH_DOCX)

            # Click Upload to commit the staged file
            page.get_by_role("button", name="Upload", exact=True).click()

            # Wait for upload success toast
            expect(
                page.get_by_text("Letterhead uploaded.", exact=True)
            ).to_be_visible(timeout=15_000)

            # Verify row appears in list
            expect(
                page.get_by_text(_LH_TEST_ROLE, exact=True)
            ).to_be_visible(timeout=10_000)

            # Deactivate via kebab
            row = page.locator("tr", has_text=_LH_TEST_ROLE)
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Letterhead deactivated.", exact=True)
            ).to_be_visible(timeout=15_000)
            expect(
                page.get_by_text(_LH_TEST_ROLE, exact=True)
            ).not_to_be_visible(timeout=10_000)
        finally:
            _hard_delete_letterhead_by_role(_LH_TEST_ROLE)

    def test_student_blocked_from_letterheads(self, page: Page) -> None:
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/admin/config/letterheads")
        page.wait_for_url(
            lambda url: "/admin/config/letterheads" not in url, timeout=10_000
        )


# ── Template Config (M5a) ──────────────────────────────────────────────────

class TestTemplateConfig:
    def test_iqac_upload_and_deactivate_template(self, page: Page) -> None:
        """IQAC user uploads a BoS template, sees it in the list, deactivates it."""
        _hard_delete_template_by_type(_TPL_TEST_TYPE)
        try:
            _login(page, _IQAC_USER, _IQAC_PASS)
            page.goto(f"{BASE_URL}/admin/config/templates")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ Upload Template", timeout=15_000)

            # Open upload form
            page.get_by_text("+ Upload Template").click()
            expect(
                page.get_by_role("heading", name="Upload Template")
            ).to_be_visible(timeout=5_000)

            # Select template type — triggers render of upload zone
            page.locator(".rt-SelectTrigger", has_text="Select type").click()
            page.get_by_role("option", name="BOS").click()
            page.wait_for_timeout(500)

            # Stage DOCX file
            file_input = page.locator("input[type='file']")
            file_input.set_input_files(_TEST_DOCX)

            # Click Upload to commit the staged file
            page.get_by_role("button", name="Upload", exact=True).click()

            # Wait for upload success toast
            expect(
                page.get_by_text("Template uploaded.", exact=True)
            ).to_be_visible(timeout=15_000)

            # Verify row appears in list
            expect(
                page.get_by_text("BOS", exact=True)
            ).to_be_visible(timeout=10_000)

            # Deactivate via kebab
            row = page.locator("tr", has_text="BOS")
            row.get_by_role("button", name="⋮").click()
            page.get_by_role("menuitem", name="Deactivate").click()
            page.get_by_role("button", name="Deactivate").click()
            expect(
                page.get_by_text("Template deactivated.", exact=True)
            ).to_be_visible(timeout=15_000)
        finally:
            _hard_delete_template_by_type(_TPL_TEST_TYPE)

    def test_student_blocked_from_templates(self, page: Page) -> None:
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/admin/config/templates")
        page.wait_for_url(
            lambda url: "/admin/config/templates" not in url, timeout=10_000
        )

    def test_registrar_blocked_from_templates(self, page: Page) -> None:
        """Registrar lacks template_asset:write and is redirected."""
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/templates")
        page.wait_for_url(
            lambda url: "/admin/config/templates" not in url, timeout=10_000
        )
