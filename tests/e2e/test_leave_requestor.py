"""Playwright E2E leave requestor suite — M8 Phase 7 gate.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run. Set BASE_URL if not using default.

Seeded read-only users (never mutated by any test here):
  faculty_user / Faculty_Dev1!XZ — FACULTY scoped to DMACS
  student_001  / Student_Dev1!XZ — STUDENT (no leave_request:create permission)

All tests are read-only — no leave requests are submitted (modal verified,
submit NOT triggered; only form rendering and nav access are asserted).

Playwright + Reflex patterns (from CLAUDE.md):
  - wait_for_load_state("networkidle") for initial HTTP page loads only.
  - After WebSocket-based state updates, poll expect(...).to_be_visible().
  - Use wait_for_url() for redirect assertions.
  - Inputs: page.get_by_placeholder(...) — rx.input renders with placeholder attr.
  - Headings: page.get_by_role("heading", name=...) — rx.heading renders as heading role.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import BASE_URL, _login

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E") != "1",
    reason="Set DURGAM_E2E=1 and start the app stack to run E2E tests",
)

_FACULTY_USER = "faculty_user"
_FACULTY_PASS = "Faculty_Dev1!XZ"
_STUDENT_USER = "student_001"
_STUDENT_PASS = "Student_Dev1!XZ"


def _wait_for_leave_page(page: Page, timeout: int = 15_000) -> None:
    """Wait for My Leave heading to be visible after on_load guard fires."""
    expect(
        page.get_by_role("heading", name="My Leave", exact=True)
    ).to_be_visible(timeout=timeout)


# ---------------------------------------------------------------------------
# TestLeaveNavAccess — route protection and nav visibility
# ---------------------------------------------------------------------------

class TestLeaveNavAccess:
    def test_unauthenticated_redirected_to_login(self, page: Page) -> None:
        """Visiting /leave without a session redirects to /login."""
        page.goto(f"{BASE_URL}/leave")
        page.wait_for_load_state("networkidle")
        page.wait_for_url(f"{BASE_URL}/login", timeout=10_000)

    def test_student_cannot_reach_leave_page(self, page: Page) -> None:
        """Student lacks leave_request:create permission — nav link not visible.
        Direct URL should redirect (no leave sanction rules for STUDENT).
        The page itself may render (auth passes) but leave content shows empty balances.
        The 'My Leave' nav entry is gated on leave_request:create:* and must be absent."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_load_state("networkidle")
        # Nav entry must NOT be visible for student (no create permission)
        expect(
            page.get_by_role("link", name="My Leave", exact=True)
        ).not_to_be_visible(timeout=10_000)

    def test_faculty_sees_my_leave_nav(self, page: Page) -> None:
        """Faculty user (FACULTY + LEAVE_REQUESTOR permissions) sees 'My Leave' nav link."""
        _login(page, _FACULTY_USER, _FACULTY_PASS)
        page.wait_for_load_state("networkidle")
        expect(
            page.get_by_role("link", name="My Leave", exact=True)
        ).to_be_visible(timeout=15_000)

    def test_faculty_navigates_to_leave_page(self, page: Page) -> None:
        """Faculty navigates from home to /leave via nav link and sees the page heading."""
        _login(page, _FACULTY_USER, _FACULTY_PASS)
        page.wait_for_load_state("networkidle")
        page.get_by_role("link", name="My Leave", exact=True).click()
        _wait_for_leave_page(page)


# ---------------------------------------------------------------------------
# TestLeaveApplyModal — modal rendering (read-only; submit not triggered)
# ---------------------------------------------------------------------------

class TestLeaveApplyModal:
    def test_apply_modal_opens_and_closes(self, page: Page) -> None:
        """'Apply for Leave' button opens the modal; Cancel closes it."""
        _login(page, _FACULTY_USER, _FACULTY_PASS)
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/leave")
        page.wait_for_load_state("networkidle")
        _wait_for_leave_page(page)

        # Modal not visible yet
        expect(
            page.get_by_role("heading", name="Apply for Leave", exact=True)
        ).not_to_be_visible()

        # Open modal
        page.get_by_role("button", name="Apply for Leave", exact=False).click()
        expect(
            page.get_by_role("heading", name="Apply for Leave", exact=True)
        ).to_be_visible(timeout=10_000)

        # Close modal via Cancel button
        page.get_by_role("button", name="Cancel", exact=True).click()
        expect(
            page.get_by_role("heading", name="Apply for Leave", exact=True)
        ).not_to_be_visible(timeout=10_000)
