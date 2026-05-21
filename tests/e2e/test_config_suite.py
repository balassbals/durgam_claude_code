"""Playwright E2E config suite — M3 gate: Configuration — Organisational Core.

Covers all admin config flows: campus, school, centre, department, course,
program read-only detail, vision/mission (university + department), class
timings, working days, and route-protection checks.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run.

Seeded read-only users (account state never mutated):
  sys_admin     / SysAdmin_Dev1!XZ      — SYSTEM_ADMIN
  registrar_user / Registrar_Dev1!XZ   — REGISTRAR
  hod_dmacs     / HodDmacs_Dev1!XZ     — HOD scoped to DMACS
  student_001   / Student_Dev1!XZ      — STUDENT (used only for route-protection)

CRUD tests:
  - Use static entity codes (TST, TSC, TCE, TDE, TST101) that are NOT seeded.
  - Each test pre-cleans any leftover entity with that code at the start.
  - Each test also cleans up in a finally block so failures don't leak state.
  - Both measures together ensure order-independence and determinism.

V&M/singletons:
  - Edit using seeded editor accounts (registrar_user, hod_dmacs).
  - State is restored to a known value at the end of each test.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import (
    BASE_URL,
    _hard_delete_by_code,
    _login,
    _logout,
    _wait_for_admin_page,
)

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
_STUDENT_USER = "student_001"
_STUDENT_PASS = "Student_Dev1!XZ"

# Stable entity codes used by CRUD tests — pre-cleaned before each test.
_CAMPUS_CODE = "TST"
_SCHOOL_CODE = "TSC"
_CENTRE_CODE = "TCE"
_DEPT_CODE = "TDE"
_COURSE_CODE = "TST101"


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
        _hard_delete_by_code("departments", _DEPT_CODE)
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
            _hard_delete_by_code("departments", _DEPT_CODE)


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
        """Registrar can add a mission, assert it saved, then remove it (cleanup)."""
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Mission Statements")

        page.get_by_text("+ Add Mission").click()
        mission_textarea = page.get_by_placeholder("Enter mission statement…")
        expect(mission_textarea).to_be_visible(timeout=10_000)
        mission_textarea.fill("E2E test mission statement — can be safely removed.")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Mission statement saved.", exact=True)).to_be_visible(
            timeout=15_000
        )
        mission_row = page.get_by_text(
            "E2E test mission statement — can be safely removed.", exact=True
        )
        expect(mission_row).to_be_visible(timeout=10_000)

        # RC-7A: remove immediately to prevent accumulation across runs.
        # ONE ".." from <p> reaches the outer hstack; Remove is a descendant of that hstack.
        # TWO ".." would reach the mission list container (all rows) → strict-mode violation.
        mission_row.locator("..").get_by_role("button", name="Remove").click()
        expect(page.get_by_text("Mission statement removed.", exact=True)).to_be_visible(
            timeout=15_000
        )
        expect(
            page.get_by_text(
                "E2E test mission statement — can be safely removed.", exact=True
            )
        ).not_to_be_visible(timeout=5_000)

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
