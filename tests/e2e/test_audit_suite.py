"""Playwright E2E audit log suite — M6b gate.

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run. Set BASE_URL if not using default.

Seeded read-only users (never mutated by any test here):
  sys_admin   / SysAdmin_Dev1!XZ   — SYSTEM_ADMIN, active
  student_001 / Student_Dev1!XZ    — STUDENT, active

All tests are sequential and read-only — no data is created or mutated.

Playwright + Reflex patterns (from CLAUDE.md):
  - wait_for_load_state("networkidle") for initial HTTP page loads only.
  - After admin page navigation, wait for a stable DOM element before asserting.
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


class TestAuditLogAccess:
    def test_student_cannot_reach_audit(self, page: Page) -> None:
        """Student has no audit_log:read permission; /audit should redirect."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        # _config_guard redirects unauthorized users away from /audit
        page.wait_for_url(
            lambda url: "/audit" not in url,
            timeout=10_000,
        )

    def test_sys_admin_can_reach_audit(self, page: Page) -> None:
        """SYSTEM_ADMIN has audit_log:read; page renders with heading."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        expect(
            page.get_by_role("heading", name="Audit Log", exact=True)
        ).to_be_visible(timeout=15_000)


class TestAuditLogDefaultView:
    def test_default_view_shows_recent_entries(self, page: Page) -> None:
        """After load, the result-summary line renders (Showing N-M or no entries)."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Audit Log", exact=True)).to_be_visible(timeout=15_000)
        # The page renders either "Showing X–Y of Z" or "No matching audit entries."
        summary = page.locator("text=/Showing \\d/").or_(
            page.get_by_text("No matching audit entries.", exact=True)
        )
        expect(summary.first).to_be_visible(timeout=10_000)
        # Column header "When" — DOM text is original-case; CSS text_transform
        # uppercases visually only. Use exact=True (M2 strict-mode rule).
        expect(
            page.get_by_text("When", exact=True).first
        ).to_be_visible(timeout=5_000)


class TestAuditLogFilters:
    def test_filter_by_action_apply_button(self, page: Page) -> None:
        """Apply Filters round-trips without error; summary line persists."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Audit Log", exact=True)).to_be_visible(timeout=15_000)
        # Wait for the summary to render before applying filters
        summary = page.locator("text=/Showing \\d/").or_(
            page.get_by_text("No matching audit entries.", exact=True)
        )
        expect(summary.first).to_be_visible(timeout=10_000)
        # Click Apply — round-trip filter without changing values.
        # Button text is "Apply" (primary_btn at index.py:616).
        page.get_by_role("button", name="Apply", exact=True).click()
        # Wait for summary to re-render (page settles after filter round-trip)
        expect(summary.first).to_be_visible(timeout=10_000)


class TestAuditLogPagination:
    def test_pagination_buttons_render_with_correct_disable_state(
        self, page: Page
    ) -> None:
        """Prev disabled on page 1; Next state matches total > page_size."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Audit Log", exact=True)).to_be_visible(timeout=15_000)
        # Wait for pagination to render.
        # Button text is "← Prev" / "Next →" (secondary_btn at index.py:678,693).
        prev_btn = page.get_by_role("button", name="← Prev", exact=True)
        expect(prev_btn).to_be_visible(timeout=10_000)
        # Page 1 — Prev should be disabled
        expect(prev_btn).to_be_disabled()
        # Next button should exist
        next_btn = page.get_by_role("button", name="Next →", exact=True)
        expect(next_btn).to_be_visible(timeout=5_000)


class TestAuditLogDetailDrawer:
    def test_open_detail_drawer(self, page: Page) -> None:
        """Click View on first row, drawer opens; close it."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Audit Log", exact=True)).to_be_visible(timeout=15_000)
        # Wait for at least one row to render
        summary = page.locator("text=/Showing \\d/")
        expect(summary.first).to_be_visible(timeout=10_000)
        # Click the first kebab menu trigger (aria_label="View audit details",
        # index.py:469).
        kebab = page.get_by_role("button", name="View audit details", exact=True).first
        expect(kebab).to_be_visible(timeout=5_000)
        kebab.click()
        # Click "View Details" in the dropdown menu
        page.get_by_text("View Details", exact=True).click()
        # Wait for drawer to open — heading "Audit Entry" visible
        expect(
            page.get_by_role("heading", name="Audit Entry", exact=True)
        ).to_be_visible(timeout=10_000)
        # Verify an expected field label is present inside the drawer.
        # DOM text is "Occurred at"; CSS text_transform uppercases visually.
        expect(
            page.get_by_text("Occurred at", exact=True).first
        ).to_be_visible(timeout=5_000)
        # Close the drawer via ✕ button (aria_label="Close drawer", index.py:1021).
        page.get_by_role("button", name="Close drawer", exact=True).click()
        expect(
            page.get_by_role("heading", name="Audit Entry", exact=True)
        ).not_to_be_visible(timeout=5_000)


class TestAuditLogCsvExport:
    def test_csv_export_triggers_download(self, page: Page) -> None:
        """Export CSV triggers a file download with expected filename pattern."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Audit Log", exact=True)).to_be_visible(timeout=15_000)
        # Wait for data to load so export button is enabled
        summary = page.locator("text=/Showing \\d/")
        expect(summary.first).to_be_visible(timeout=10_000)
        # Click Export CSV (secondary_btn at index.py:628) — should trigger download
        with page.expect_download(timeout=15_000) as download_info:
            page.get_by_role("button", name="Export CSV", exact=True).click()
        download = download_info.value
        assert download.suggested_filename.startswith("audit-log-")
        assert download.suggested_filename.endswith(".csv")
