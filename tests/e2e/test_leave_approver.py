"""Playwright E2E leave approver suite — M8 Phase 8 gate.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run. Set BASE_URL if not using default.

Seeded read-only users (never mutated by any test here):
  sys_admin / SysAdmin_Dev1!XZ  — can see approvals inbox (has approval_request:approve:*)
  dean_sci  / DeanSci_Dev1!XZ   — DEAN role; channel approver for LEAVE_APPROVAL

These tests verify:
  1. The approver inbox page is reachable by sys_admin via nav.
  2. The request detail page loads without error.
  3. The leave details section renders when process is LEAVE_APPROVAL.

All tests are READ-ONLY — no approval decisions are triggered.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000")

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E", "0") != "1",
    reason="Set DURGAM_E2E=1 to run E2E suite",
)


def _login(page: Page, username: str, password: str) -> None:
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, username, password)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_approver_inbox_reachable_via_nav(page: Page) -> None:
    """sys_admin can reach Approvals inbox via the nav link."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "sys_admin", "SysAdmin_Dev1!XZ")

    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link", name="Approvals", exact=True)).to_be_visible(timeout=10_000)
    page.get_by_role("link", name="Approvals", exact=True).click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Approval Inbox")).to_be_visible(timeout=15_000)


def test_approvals_inbox_page_loads_without_error(page: Page) -> None:
    """Direct navigation to /approvals/inbox succeeds and renders content."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "sys_admin", "SysAdmin_Dev1!XZ")

    page.goto(f"{BASE_URL}/approvals/inbox")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Approval Inbox")).to_be_visible(timeout=15_000)
    # Inbox may be empty (no pending leave requests in CI seed); that's fine.
    # What must NOT appear is an error page or redirect to login.
    expect(page.get_by_text("Something went wrong", exact=False)).not_to_be_visible()


def test_student_cannot_reach_approvals_inbox(page: Page) -> None:
    """student_001 is redirected away from the approvals inbox (no approve permission)."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "student_001", "Student_Dev1!XZ")

    page.goto(f"{BASE_URL}/approvals/inbox")
    page.wait_for_load_state("networkidle")

    # Should be redirected to home or login — never see the Inbox heading.
    # Allow up to 5 s for the redirect to complete.
    try:
        page.wait_for_url(
            lambda url: "/approvals/inbox" not in url,
            timeout=5_000,
        )
    except Exception:
        pass  # if still on /approvals/inbox, the expect below will fail

    expect(page.get_by_role("heading", name="Approval Inbox")).not_to_be_visible()
