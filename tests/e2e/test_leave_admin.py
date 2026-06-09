"""Playwright E2E leave admin suite — M8 Phase 8 gate.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run. Set BASE_URL if not using default.

Seeded read-only users:
  sys_admin / SysAdmin_Dev1!XZ — has leave_sanction_rule:configure + late_attendance:write

Tests:
  1. Leave Sanction Matrix page loads for sys_admin.
  2. Leave Matrix is reachable via Config nav group.
  3. Late Attendance admin page loads for sys_admin.
  4. Student cannot reach Leave Matrix admin page.

All tests are READ-ONLY — no matrix rows are created or deleted.
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


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_leave_matrix_page_loads_for_sys_admin(page: Page) -> None:
    """Direct navigation to /admin/config/leave-sanction-matrix succeeds."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "sys_admin", "SysAdmin_Dev1!XZ")

    page.goto(f"{BASE_URL}/admin/config/leave-sanction-matrix")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Leave Sanction Matrix")).to_be_visible(timeout=15_000)
    # Seeded rules must appear; "Create Rule" button must be present.
    expect(page.get_by_text("Create Rule", exact=False)).to_be_visible(timeout=10_000)


def test_leave_matrix_reachable_via_config_nav(page: Page) -> None:
    """sys_admin can navigate to Leave Matrix via the Config nav group."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "sys_admin", "SysAdmin_Dev1!XZ")

    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link", name="Leave Matrix", exact=True)).to_be_visible(timeout=10_000)
    page.get_by_role("link", name="Leave Matrix", exact=True).click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Leave Sanction Matrix")).to_be_visible(timeout=15_000)


def test_late_attendance_page_loads_for_sys_admin(page: Page) -> None:
    """Direct navigation to /admin/leave/late-attendance succeeds."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "sys_admin", "SysAdmin_Dev1!XZ")

    page.goto(f"{BASE_URL}/admin/leave/late-attendance")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Late Attendance Markers")).to_be_visible(timeout=15_000)
    expect(page.get_by_role("heading", name="Record Late Attendance")).to_be_visible(timeout=10_000)


def test_student_cannot_reach_leave_matrix(page: Page) -> None:
    """student_001 is redirected away from the Leave Matrix admin page."""
    from tests.e2e._helpers import _login as _base_login
    _base_login(page, "student_001", "Student_Dev1!XZ")

    page.goto(f"{BASE_URL}/admin/config/leave-sanction-matrix")
    page.wait_for_load_state("networkidle")

    try:
        page.wait_for_url(
            lambda url: "/admin/config/leave-sanction-matrix" not in url,
            timeout=5_000,
        )
    except Exception:
        pass

    expect(page.get_by_role("heading", name="Leave Sanction Matrix")).not_to_be_visible()
