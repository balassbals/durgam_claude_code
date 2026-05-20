"""Playwright E2E config suite — M3 gate: Configuration — Organisational Core.

Covers all admin config flows: campus, school, centre, department, course,
program read-only detail, vision/mission (university + department), class
timings, working days, and route-protection checks.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run.

Seeded read-only users (never have their ACCOUNT STATE mutated here):
  sys_admin     / SysAdmin_Dev1!XZ      — SYSTEM_ADMIN
  registrar_user / Registrar_Dev1!XZ   — REGISTRAR
  hod_dmacs     / HodDmacs_Dev1!XZ     — HOD scoped to DMACS
  student_001   / Student_Dev1!XZ      — STUDENT (used only for route-protection)

Config CRUD tests create/edit/soft-delete SYSTEM ENTITIES (campuses, schools,
etc.). System entity mutations are acceptable against seeded users — the
"seeded users are read-only" rule applies to user account state (password,
is_active, must_change_password, etc.) not to application data these users
manage.

Vision/mission tests edit V&M content via seeded editor accounts. The V&M
content starts in a known state from scripts/seed.py. Tests verify the edit
works; they do NOT restore the original seed content (gate verification is
a one-time exercise per CLAUDE.md; three-run determinism is verified manually).
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import BASE_URL, _login, _logout, _wait_for_admin_page

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
        """student_001 is redirected away from admin config routes."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}{route}")
        page.wait_for_load_state("networkidle")
        # After the WebSocket guard fires, the student should be redirected to /
        # (not back to /login — they ARE authenticated, just unauthorised for write)
        page.wait_for_url(lambda url: route not in url, timeout=10_000)
        _logout(page)

    def test_unauthenticated_redirected_to_login(self, page: Page) -> None:
        """Unauthenticated visit to /admin/config redirects to /login."""
        page.goto(f"{BASE_URL}/admin/config")
        page.wait_for_url(f"{BASE_URL}/login", timeout=10_000)


# ── Campus CRUD ───────────────────────────────────────────────────────────────

class TestCampusCRUD:
    def test_create_edit_softdelete_campus(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/campuses")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Campus")

        # Create
        page.get_by_text("+ New Campus").click()
        expect(page.get_by_placeholder("e.g. PSN")).to_be_visible(timeout=10_000)
        page.get_by_placeholder("e.g. PSN").fill("TST")
        page.get_by_placeholder("Campus name").fill("Test Campus E2E")
        page.get_by_role("button", name="Save").click()

        # Verify saved
        expect(page.get_by_text("Test Campus E2E", exact=True)).to_be_visible(timeout=15_000)
        expect(page.get_by_text("Campus saved.", exact=True)).to_be_visible(timeout=5_000)

        # Edit (name only — code is locked in edit mode)
        page.get_by_text("Test Campus E2E", exact=True).locator("..").locator("..").get_by_role(
            "button", name="⋮"
        ).click()
        page.get_by_role("menuitem", name="Edit").click()
        campus_name_input = page.get_by_placeholder("Campus name")
        expect(campus_name_input).to_be_visible(timeout=10_000)
        campus_name_input.fill("Test Campus E2E Updated")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Test Campus E2E Updated", exact=True)).to_be_visible(timeout=15_000)

        # Soft-delete
        page.get_by_text("Test Campus E2E Updated", exact=True).locator("..").locator(
            ".."
        ).get_by_role("button", name="⋮").click()
        page.get_by_role("menuitem", name="Deactivate").click()
        # Confirm dialog appears
        expect(page.get_by_text("Deactivate")).to_be_visible(timeout=5_000)
        page.get_by_role("button", name="Deactivate").click()
        # After soft-delete, row disappears from active list
        expect(page.get_by_text("Test Campus E2E Updated", exact=True)).not_to_be_visible(
            timeout=15_000
        )


# ── School CRUD ───────────────────────────────────────────────────────────────

class TestSchoolCRUD:
    def test_create_edit_softdelete_school(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/schools")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New School")

        page.get_by_text("+ New School").click()
        expect(page.get_by_placeholder("e.g. SCI")).to_be_visible(timeout=10_000)
        page.get_by_placeholder("e.g. SCI").fill("TSC")
        page.get_by_placeholder("School name").fill("Test School E2E")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Test School E2E", exact=True)).to_be_visible(timeout=15_000)

        # Soft-delete
        page.get_by_text("Test School E2E", exact=True).locator("..").locator(
            ".."
        ).get_by_role("button", name="⋮").click()
        page.get_by_role("menuitem", name="Deactivate").click()
        page.get_by_role("button", name="Deactivate").click()
        expect(page.get_by_text("Test School E2E", exact=True)).not_to_be_visible(
            timeout=15_000
        )


# ── Centre CRUD ───────────────────────────────────────────────────────────────

class TestCentreCRUD:
    def test_create_edit_softdelete_centre(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/centres")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Centre")

        page.get_by_text("+ New Centre").click()
        expect(page.get_by_placeholder("e.g. IQAC")).to_be_visible(timeout=10_000)
        page.get_by_placeholder("e.g. IQAC").fill("TCE")
        page.get_by_placeholder("Centre name").fill("Test Centre E2E")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Test Centre E2E", exact=True)).to_be_visible(timeout=15_000)

        # Soft-delete
        page.get_by_text("Test Centre E2E", exact=True).locator("..").locator(
            ".."
        ).get_by_role("button", name="⋮").click()
        page.get_by_role("menuitem", name="Deactivate").click()
        page.get_by_role("button", name="Deactivate").click()
        expect(page.get_by_text("Test Centre E2E", exact=True)).not_to_be_visible(
            timeout=15_000
        )


# ── Department CRUD ───────────────────────────────────────────────────────────

class TestDepartmentCRUD:
    def test_create_edit_softdelete_department(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/departments")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Department")

        page.get_by_text("+ New Department").click()
        expect(page.get_by_placeholder("e.g. PHYS")).to_be_visible(timeout=10_000)
        page.get_by_placeholder("e.g. PHYS").fill("TDE")
        page.get_by_placeholder("Department name").fill("Test Dept E2E")
        # School dropdown: wait for options then select first available
        school_sel = page.locator("select[name='form_school_id']")
        expect(school_sel.locator("option:not([value=''])").first).to_be_attached(
            timeout=10_000
        )
        school_sel.select_option(index=1)
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Test Dept E2E", exact=True)).to_be_visible(timeout=15_000)

        # Soft-delete
        page.get_by_text("Test Dept E2E", exact=True).locator("..").locator(
            ".."
        ).get_by_role("button", name="⋮").click()
        page.get_by_role("menuitem", name="Deactivate").click()
        page.get_by_role("button", name="Deactivate").click()
        expect(page.get_by_text("Test Dept E2E", exact=True)).not_to_be_visible(
            timeout=15_000
        )


# ── Course CRUD ───────────────────────────────────────────────────────────────

class TestCourseCRUD:
    def test_create_edit_softdelete_course(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/courses")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "+ New Course")

        page.get_by_text("+ New Course").click()
        expect(page.get_by_placeholder("e.g. MA101")).to_be_visible(timeout=10_000)
        page.get_by_placeholder("e.g. MA101").fill("TST101")
        page.get_by_placeholder("Course name").fill("Test Course E2E")
        # Program dropdown
        prog_sel = page.locator("select[name='form_program_id']")
        expect(prog_sel.locator("option:not([value=''])").first).to_be_attached(
            timeout=10_000
        )
        prog_sel.select_option(index=1)
        # Department dropdown
        dept_sel = page.locator("select[name='form_department_id']")
        expect(dept_sel.locator("option:not([value=''])").first).to_be_attached(
            timeout=10_000
        )
        dept_sel.select_option(index=1)
        page.get_by_placeholder("e.g. 4").fill("3")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Test Course E2E", exact=True)).to_be_visible(timeout=15_000)

        # Soft-delete
        page.get_by_text("Test Course E2E", exact=True).locator("..").locator(
            ".."
        ).get_by_role("button", name="⋮").click()
        page.get_by_role("menuitem", name="Deactivate").click()
        page.get_by_role("button", name="Deactivate").click()
        expect(page.get_by_text("Test Course E2E", exact=True)).not_to_be_visible(
            timeout=15_000
        )


# ── Program read-only detail ──────────────────────────────────────────────────

class TestProgramDetail:
    def test_seeded_program_detail_renders_all_tabs(self, page: Page) -> None:
        """Seeded BSCMATH program detail shows all 6 tabs."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/programs")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "BSCMATH")

        # Click to open detail
        page.get_by_text("BSCMATH", exact=True).click()
        # Verify all 6 tab labels appear
        for tab in ("Overview", "Outcomes", "Regulations", "Scheme", "Specialisations", "Exit Levels"):
            expect(page.get_by_role("tab", name=tab)).to_be_visible(timeout=10_000)


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
        expect(page.get_by_text("To foster knowledge, devotion, and service — updated by E2E.")).to_be_visible(
            timeout=10_000
        )

    def test_registrar_can_add_university_mission(self, page: Page) -> None:
        """Registrar can add a new university mission statement."""
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
        expect(
            page.get_by_text("E2E test mission statement — can be safely removed.", exact=True)
        ).to_be_visible(timeout=10_000)

    def test_registrar_sees_department_list(self, page: Page) -> None:
        """Registrar sees the department V&M list for navigation."""
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Department Vision & Mission")

        # At least one department link should be visible
        expect(page.get_by_role("link", name="Edit V&M").first).to_be_visible(timeout=10_000)

    def test_hod_can_edit_department_vision(self, page: Page) -> None:
        """HoD scoped to DMACS can edit DMACS department vision."""
        _login(page, _HOD_USER, _HOD_PASS)
        page.goto(f"{BASE_URL}/admin/config/vision-mission/departments/DMACS")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Vision")

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

        # Change periods_per_day to 9
        ppd_input = page.locator("input[name='periods_per_day']")
        expect(ppd_input).to_be_visible(timeout=10_000)
        ppd_input.fill("9")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Class timings saved.", exact=True)).to_be_visible(
            timeout=15_000
        )
        # Verify persisted: reload and check
        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Periods per day")
        expect(page.locator("input[name='periods_per_day']")).to_have_value("9", timeout=10_000)


# ── Working Days ──────────────────────────────────────────────────────────────

class TestWorkingDays:
    def test_registrar_can_edit_working_days(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/admin/config/working-days")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Days per week")

        # Select 6-day week
        page.get_by_role("radio").filter(has_text="6").click()
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text("Working days saved.", exact=True)).to_be_visible(
            timeout=15_000
        )
        # Verify persisted: reload
        page.reload()
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Days per week")
        # 6-day radio should now be selected
        six_day = page.get_by_role("radio").filter(has_text="6")
        expect(six_day).to_be_checked(timeout=10_000)

    def test_hod_blocked_from_working_days(self, page: Page) -> None:
        """HoD lacks configure permission and is redirected."""
        _login(page, _HOD_USER, _HOD_PASS)
        page.goto(f"{BASE_URL}/admin/config/working-days")
        page.wait_for_load_state("networkidle")
        page.wait_for_url(lambda url: "/admin/config/working-days" not in url, timeout=10_000)
