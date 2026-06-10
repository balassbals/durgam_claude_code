"""Playwright E2E suite — Leave Balance Import (M8.1 E-016).

Requires a running stack (DURGAM_E2E=1):
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Three tests:
  1. test_csv_upload_valid_rows_commit_success
     Upload a valid CSV → preview shows valid rows + resolved AY name → commit →
     success flash visible.

  2. test_csv_upload_invalid_rows_commit_disabled
     Upload a CSV with invalid rows (negative balance, unknown leave type) →
     invalid rows badge visible → commit button is disabled.

  3. test_per_employee_form_save
     Click "+ Add / Update Balance" → per-employee modal opens → select employee
     and leave type → enter fields → save → success flash contains "Balance saved".

Patterns from CLAUDE.md M2+:
  - wait_for_load_state("networkidle") only for HTTP page loads.
  - expect(...).to_be_visible() for post-WebSocket-state assertions.
  - file_input.set_input_files(path) for rx.upload on_drop handlers.
  - exact=True on get_by_text() for dynamic values.

Actor: ephemeral REGISTRAR user (has leave_balance_import:write:*).
Target employees in CSV/form: seeded users not on the read-only mutation list.

NOTE: These tests are WRITTEN but NOT RUN at Phase 4 gate.
      Run at Phase 9 gate as part of E2E walkthrough ×3.
"""

from __future__ import annotations

import os
import tempfile
import uuid

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import BASE_URL, _login, _wait_for_admin_page

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E") != "1",
    reason="Set DURGAM_E2E=1 and start the app stack to run E2E tests",
)

_EPH_PASS = "Ephemeral_Dev1!XZ"
_PAGE_ANCHOR = "Leave Balance Import"
_PAGE_URL = f"{BASE_URL}/admin/leave/balance-import"

# Target employees: seeded users whose leave_balance rows we create and clean up.
# student_001 is not on the CLAUDE.md mutation-list for login restrictions;
# creating leave_balance rows for them (different table) is permitted.
_TARGET_EMP = "student_001"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _create_ephemeral_registrar() -> tuple[str, str]:
    """Create an ephemeral REGISTRAR user. Returns (username, password)."""
    from sqlalchemy import create_engine
    from sqlmodel import Session, select

    from durgam.config import settings
    from durgam.models.identity import Role, User, UserRole
    from durgam.services.password import hash_password

    suffix = uuid.uuid4().hex[:10]
    username = f"e2e_{suffix}"
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        user = User(
            username=username,
            email=f"e2e_{suffix}@sssihl.edu.in",
            password_hash=hash_password(_EPH_PASS),
            is_active=True,
        )
        session.add(user)
        session.flush()
        role = session.exec(select(Role).where(Role.code == "REGISTRAR")).first()
        if role:
            session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()
    engine.dispose()
    return username, _EPH_PASS


def _delete_ephemeral_user(username: str) -> None:
    """Hard-delete an ephemeral user and associated rows."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        for table in ("user_roles", "user_sessions", "password_reset_tokens"):
            conn.execute(
                text(f"DELETE FROM {table} WHERE user_id = "  # noqa: S608
                     "(SELECT id FROM users WHERE username = :u)"),
                {"u": username},
            )
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})
        conn.commit()
    engine.dispose()


def _delete_leave_balance(employee_username: str, leave_type: str) -> None:
    """Hard-delete a leave_balance row for the given employee and leave_type."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        conn.execute(
            text(
                "DELETE FROM leave_balances WHERE employee_user_id = "  # noqa: S608
                "(SELECT id FROM users WHERE username = :u) "
                "AND leave_type = :lt"
            ),
            {"u": employee_username, "lt": leave_type},
        )
        conn.commit()
    engine.dispose()


def _wait_for_balance_import_page(page: Page) -> None:
    """Wait for the balance import page to fully render after on_load guard fires."""
    _wait_for_admin_page(page, _PAGE_ANCHOR)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_csv_upload_valid_rows_commit_success(page: Page) -> None:
    """Upload a valid 1-row CSV → preview shows AY name + valid badge → commit → success flash."""
    actor, password = _create_ephemeral_registrar()
    try:
        # Pre-clean target balance so the import creates (not updates) for clarity.
        _delete_leave_balance(_TARGET_EMP, "CL")

        _login(page, actor, password)

        page.goto(_PAGE_URL)
        page.wait_for_load_state("networkidle")
        _wait_for_balance_import_page(page)

        # Assert AY is resolved (green banner present, not warning).
        # "Importing into AY:" text is in the resolved banner.
        expect(page.get_by_text("Importing into AY:", exact=True)).to_be_visible(
            timeout=10_000
        )

        # Create and upload a valid CSV for student_001 CL.
        csv_content = (
            "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
            f"{_TARGET_EMP},CL,0.0,10.0,2.0,0.0,0.0\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, prefix="e2e_lbi_"
        ) as f:
            f.write(csv_content)
            tmp_path = f.name

        try:
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(tmp_path)

            # Wait for valid rows badge to appear (WebSocket state update).
            expect(
                page.get_by_text("1 valid row(s)", exact=False)
            ).to_be_visible(timeout=15_000)

            # Commit button should be enabled (no invalid rows, AY resolved).
            commit_btn = page.get_by_role("button", name="Commit Import", exact=True)
            expect(commit_btn).to_be_visible(timeout=5_000)

            commit_btn.click()

            # Wait for success flash.
            expect(
                page.get_by_text("Import complete:", exact=False)
            ).to_be_visible(timeout=15_000)
        finally:
            os.unlink(tmp_path)

    finally:
        _delete_leave_balance(_TARGET_EMP, "CL")
        _delete_ephemeral_user(actor)


def test_csv_upload_invalid_rows_commit_disabled(page: Page) -> None:
    """Upload CSV with invalid rows → invalid badge visible → commit button disabled."""
    actor, password = _create_ephemeral_registrar()
    try:
        _login(page, actor, password)

        page.goto(_PAGE_URL)
        page.wait_for_load_state("networkidle")
        _wait_for_balance_import_page(page)

        # CSV with 2 invalid rows: negative balance + unknown leave type.
        csv_content = (
            "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
            f"{_TARGET_EMP},XX,0.0,10.0,2.0,0.0,0.0\n"
            f"{_TARGET_EMP},CL,-5.0,10.0,2.0,0.0,0.0\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, prefix="e2e_lbi_invalid_"
        ) as f:
            f.write(csv_content)
            tmp_path = f.name

        try:
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(tmp_path)

            # Wait for invalid rows badge to appear.
            expect(
                page.get_by_text("invalid row(s)", exact=False)
            ).to_be_visible(timeout=15_000)

            # Commit button must be visible but rendered with disabled styling
            # (opacity 0.5, cursor not-allowed — DD-M8.1-P4-1).
            commit_btn = page.get_by_role("button", name="Commit Import", exact=True)
            expect(commit_btn).to_be_visible(timeout=5_000)
            # Verify the button is actually disabled.
            expect(commit_btn).to_be_disabled()

        finally:
            os.unlink(tmp_path)

    finally:
        _delete_ephemeral_user(actor)


def test_per_employee_form_save(page: Page) -> None:
    """Per-employee form: select employee and leave type → enter fields → save → flash."""
    actor, password = _create_ephemeral_registrar()
    try:
        # Pre-clean target balance so the save is a fresh insert.
        _delete_leave_balance(_TARGET_EMP, "EL")

        _login(page, actor, password)

        page.goto(_PAGE_URL)
        page.wait_for_load_state("networkidle")
        _wait_for_balance_import_page(page)

        # Open the per-employee form.
        page.get_by_role("button", name="+ Add / Update Balance", exact=True).click()

        # Wait for modal heading.
        expect(
            page.get_by_role("heading", name="Set / Update Employee Balance")
        ).to_be_visible(timeout=10_000)

        # Select employee from dropdown. The select trigger is visible inside the modal.
        # Wait for the employee options to be populated (WebSocket round-trip from load).
        employee_option = page.locator(
            f"[data-value='{_TARGET_EMP}']"
        )
        expect(employee_option).to_be_attached(timeout=15_000)
        page.locator("button[role='combobox']").first.click()
        page.locator(f"[data-value='{_TARGET_EMP}']").first.click()

        # Select leave type EL.
        el_option = page.locator("[data-value='EL']")
        expect(el_option).to_be_attached(timeout=10_000)
        page.locator("button[role='combobox']").nth(1).click()
        page.locator("[data-value='EL']").first.click()

        # Fill numeric fields.
        page.get_by_placeholder("0.0").nth(1).fill("15.0")  # credited field

        # Submit the form.
        page.get_by_role("button", name="Save", exact=True).click()

        # Wait for success flash.
        expect(
            page.get_by_text("Balance saved for", exact=False)
        ).to_be_visible(timeout=15_000)

    finally:
        _delete_leave_balance(_TARGET_EMP, "EL")
        _delete_ephemeral_user(actor)
