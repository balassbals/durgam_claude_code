"""Playwright E2E about suite — M3 gate: public-facing About pages.

/about/university — University vision and mission (read-only, all authenticated users).
/about/departments — Department list (read-only, all authenticated users).
/about/departments/[code] — Department V&M detail (read-only, all authenticated).

Requires a running stack with seed data.

Set DURGAM_E2E=1 to run.

RC-7C: About pages MUST NOT use wait_for_load_state("networkidle"). Reflex
pages dispatch all content via WebSocket; networkidle fires before the
WebSocket state update that reveals rx.cond-gated content. Use polled
expect(...).to_be_visible(timeout=15_000) exclusively.
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
_STUDENT_USER = "student_001"
_STUDENT_PASS = "Student_Dev1!XZ"
_REGISTRAR_USER = "registrar_user"
_REGISTRAR_PASS = "Registrar_Dev1!XZ"


# ── Unauthenticated / route-protection ────────────────────────────────────────

class TestAboutRouteProtection:
    def test_unauthenticated_university_redirected(self, page: Page) -> None:
        page.goto(f"{BASE_URL}/about/university")
        page.wait_for_url(f"{BASE_URL}/login", timeout=10_000)

    def test_unauthenticated_departments_redirected(self, page: Page) -> None:
        page.goto(f"{BASE_URL}/about/departments")
        page.wait_for_url(f"{BASE_URL}/login", timeout=10_000)


# ── University about page ─────────────────────────────────────────────────────

class TestAboutUniversity:
    def test_student_can_view_university_about(self, page: Page) -> None:
        """student_001 can reach /about/university and see vision content."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/about/university")
        # RC-7C: no networkidle — rely on polled visibility
        expect(
            page.get_by_role("heading", name="University Vision & Mission")
        ).to_be_visible(timeout=15_000)
        # "Vision" section heading should be present (V&M seeded)
        expect(page.get_by_text("Vision", exact=True)).to_be_visible(timeout=10_000)

    def test_university_about_reachable_from_nav(self, page: Page) -> None:
        """student_001 can reach /about/university via the nav link."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        university_link = page.get_by_role("link", name="University", exact=True)
        expect(university_link).to_be_visible(timeout=10_000)
        university_link.click()
        page.wait_for_url(f"{BASE_URL}/about/university", timeout=10_000)
        expect(
            page.get_by_role("heading", name="University Vision & Mission")
        ).to_be_visible(timeout=15_000)

    def test_admin_can_view_university_about(self, page: Page) -> None:
        """sys_admin also sees the university about page."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/about/university")
        expect(
            page.get_by_role("heading", name="University Vision & Mission")
        ).to_be_visible(timeout=15_000)


# ── Departments about page ────────────────────────────────────────────────────

class TestAboutDepartments:
    def test_student_can_view_departments_list(self, page: Page) -> None:
        """student_001 sees /about/departments department list."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/about/departments")
        expect(
            page.get_by_role("heading", name="Department Vision & Mission")
        ).to_be_visible(timeout=15_000)
        expect(page.get_by_text("DMACS", exact=True)).to_be_visible(timeout=10_000)

    def test_departments_reachable_from_nav(self, page: Page) -> None:
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        departments_link = page.get_by_role("link", name="Departments", exact=True)
        expect(departments_link).to_be_visible(timeout=10_000)
        departments_link.click()
        page.wait_for_url(f"{BASE_URL}/about/departments", timeout=10_000)
        expect(
            page.get_by_role("heading", name="Department Vision & Mission")
        ).to_be_visible(timeout=15_000)

    def test_student_can_view_dmacs_detail(self, page: Page) -> None:
        """student_001 sees DMACS V&M detail."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/about/departments/DMACS")
        expect(page.get_by_text("Mathematics and Computer Science")).to_be_visible(
            timeout=15_000
        )
        expect(page.get_by_text("Vision", exact=True)).to_be_visible(timeout=10_000)

    def test_nonexistent_dept_shows_not_found(self, page: Page) -> None:
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/about/departments/XXXXNOTEXIST")
        expect(page.get_by_text("Department not found.")).to_be_visible(timeout=15_000)

    def test_dept_without_vm_shows_not_configured(self, page: Page) -> None:
        """A department without configured V&M shows the placeholder message."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/about/departments")
        expect(
            page.get_by_role("heading", name="Department Vision & Mission")
        ).to_be_visible(timeout=15_000)

        # Find a "View" link next to a "Not yet configured" status.
        # The seed only configures DMACS; other departments show "Not yet configured".
        not_configured = page.locator(
            "a[href^='/about/departments/']"
        ).filter(has=page.get_by_text("Not yet configured").first)
        count = not_configured.count()
        if count == 0:
            pytest.skip("All departments have V&M configured; cannot test not-configured state")
        not_configured.first.click()
        page.wait_for_url(lambda url: "/about/departments/" in url, timeout=10_000)
        expect(
            page.get_by_text(
                "Vision and mission for this department have not been configured yet."
            )
        ).to_be_visible(timeout=15_000)


# ── Cross-role about page visibility ─────────────────────────────────────────

class TestAboutVisibilityAllRoles:
    def test_registrar_sees_about_university(self, page: Page) -> None:
        _login(page, _REGISTRAR_USER, _REGISTRAR_PASS)
        page.goto(f"{BASE_URL}/about/university")
        expect(
            page.get_by_role("heading", name="University Vision & Mission")
        ).to_be_visible(timeout=15_000)

    def test_about_content_reflects_current_state(self, page: Page) -> None:
        """student_001 can see the university about page with vision/mission content."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/about/university")
        expect(
            page.get_by_role("heading", name="University Vision & Mission")
        ).to_be_visible(timeout=15_000)
        # Vision section should be visible as long as V&M is configured (seeded)
        expect(page.get_by_text("Vision", exact=True)).to_be_visible(timeout=10_000)
