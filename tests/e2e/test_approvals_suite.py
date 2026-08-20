"""Playwright E2E approval-requests suite — M7 gate.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run. Set BASE_URL if not using default.

Seeded read-only users (never mutated by any test here):
  sys_admin   / SysAdmin_Dev1!XZ   — SYSTEM_ADMIN, active
  student_001 / Student_Dev1!XZ    — STUDENT, active

All tests are read-only — no data is created or mutated.

Playwright + Reflex patterns (from CLAUDE.md):
  - wait_for_load_state("networkidle") for initial HTTP page loads only.
  - After page navigation, wait for a stable DOM element before asserting.
  - Use wait_for_url() for redirect assertions (WebSocket-based).
  - Use polled expect(...).to_be_visible() for element assertions.
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

_ADMIN_USER = "sys_admin"
_ADMIN_PASS = "SysAdmin_Dev1!XZ"
_STUDENT_USER = "student_001"
_STUDENT_PASS = "Student_Dev1!XZ"


def _wait_for_page_heading(page: Page, heading_text: str, timeout: int = 15_000) -> None:
    """Wait for a page heading to be visible after on_load guard fires."""
    expect(
        page.get_by_role("heading", name=heading_text, exact=True)
    ).to_be_visible(timeout=timeout)


# ---------------------------------------------------------------------------
# TestApprovalsAccess — nav visibility and route protection
# ---------------------------------------------------------------------------

class TestApprovalsAccess:
    def test_student_does_not_see_approvals_nav(self, page: Page) -> None:
        """Student sees 'My Requests' (permission_action=None) but NOT
        'Approvals' (gated on approval_request:approve:*). Manual nav
        to /approvals/inbox should redirect."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_load_state("networkidle")

        # "My Requests" should be visible to all authenticated users
        expect(
            page.get_by_role("link", name="My Requests", exact=True)
        ).to_be_visible(timeout=10_000)

        # "Approvals" link (the inbox link) should NOT be visible
        expect(
            page.get_by_role("link", name="Approvals", exact=True)
        ).not_to_be_visible(timeout=5_000)

        # Direct navigation to /approvals/inbox should redirect away
        page.goto(f"{BASE_URL}/approvals/inbox")
        page.wait_for_load_state("networkidle")
        # The page should either redirect to login or show empty content
        # (AuthState guard renders rx.fragment() for unauthorized users)
        # Verify the inbox heading does NOT appear
        expect(
            page.get_by_role("heading", name="Approval Inbox", exact=True)
        ).not_to_be_visible(timeout=5_000)

    def test_sys_admin_sees_both_nav_links(self, page: Page) -> None:
        """SYSTEM_ADMIN sees both 'My Requests' and 'Approvals' nav links."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_load_state("networkidle")

        expect(
            page.get_by_role("link", name="My Requests", exact=True)
        ).to_be_visible(timeout=10_000)

        expect(
            page.get_by_role("link", name="Approvals", exact=True)
        ).to_be_visible(timeout=10_000)


# ---------------------------------------------------------------------------
# TestRequestorFlow — my-requests page and submit form rendering
# ---------------------------------------------------------------------------

class TestRequestorFlow:
    def test_my_requests_page_renders_for_authenticated_user(self, page: Page) -> None:
        """Student navigates to /approvals/my-requests; heading and empty
        state both render."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/approvals/my-requests")
        page.wait_for_load_state("networkidle")

        _wait_for_page_heading(page, "My Approval Requests")

        # Empty state message should be visible (student has no requests)
        expect(
            page.get_by_text(
                "You have not submitted any approval requests yet.",
                exact=True,
            )
        ).to_be_visible(timeout=10_000)

    def test_submit_form_page_renders(self, page: Page) -> None:
        """Submit form page shows heading, process select, title input,
        and submit button."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/approvals/submit")
        page.wait_for_load_state("networkidle")

        _wait_for_page_heading(page, "New Approval Request")

        # Process picker
        expect(
            page.get_by_text("Approval Process", exact=True)
        ).to_be_visible(timeout=10_000)

        # Title input
        expect(
            page.get_by_placeholder("Brief title for your request")
        ).to_be_visible(timeout=10_000)

        # Submit button
        expect(
            page.get_by_text("Submit Request", exact=True)
        ).to_be_visible(timeout=10_000)


# ---------------------------------------------------------------------------
# TestApproverFlow — inbox rendering and detail page
# ---------------------------------------------------------------------------

class TestApproverFlow:
    def test_sys_admin_inbox_renders(self, page: Page) -> None:
        """SYSTEM_ADMIN (who inherits approval_request:approve via wildcard)
        can reach /approvals/inbox; empty state visible when no pending."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/approvals/inbox")
        page.wait_for_load_state("networkidle")

        _wait_for_page_heading(page, "Approval Inbox")

        # Empty state message
        expect(
            page.get_by_text("No items found.", exact=True)
        ).to_be_visible(timeout=10_000)

    # TODO: test_request_detail_page_renders_for_authorized_viewer
    # Requires a fixture-seeded approval request. Deferred to gate ritual
    # because creating a request through the service API from Playwright
    # requires either (a) an API endpoint or (b) a DB-side helper that the
    # E2E runner calls. Neither exists yet. Bala will refine during gate.


# ---------------------------------------------------------------------------
# TestNrfAdminIntegration — NRF admin page interaction with approvals
# ---------------------------------------------------------------------------

class TestNrfAdminIntegration:
    def test_nrf_admin_pending_section_renders(self, page: Page) -> None:
        """sys_admin opens /admin/config/non-regular-faculty; when no pending
        NRF approval requests exist, the pending section is hidden (it uses
        rx.cond on length > 0). The main heading is visible."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/non-regular-faculty")
        page.wait_for_load_state("networkidle")

        # Wait for the admin page guard to fire and content to render
        _wait_for_page_heading(page, "Non-Regular Faculty")

        # The "+ Submit for Approval" button should be visible
        expect(
            page.get_by_text("Submit for Approval", exact=False)
        ).to_be_visible(timeout=10_000)

        # "Pending Approvals" heading should NOT be visible when count is 0
        # (the section is conditionally rendered via rx.cond on length > 0)
        # # TODO: verify — if seed creates pending NRF requests this will flip
        expect(
            page.get_by_role("heading", name="Pending Approvals", exact=True)
        ).not_to_be_visible(timeout=5_000)

    def test_nrf_admin_add_button_redirects_to_submit_form(self, page: Page) -> None:
        """Clicking '+ Submit for Approval' on the NRF admin page navigates
        to /approvals/submit."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/config/non-regular-faculty")
        page.wait_for_load_state("networkidle")

        _wait_for_page_heading(page, "Non-Regular Faculty")

        # Click the submit-for-approval button
        page.get_by_text("Submit for Approval", exact=False).click()

        # Should navigate to the submit form page
        page.wait_for_url(
            lambda url: "/approvals/submit" in url,
            timeout=10_000,
        )

        # Verify the submit form heading appears
        _wait_for_page_heading(page, "New Approval Request")
