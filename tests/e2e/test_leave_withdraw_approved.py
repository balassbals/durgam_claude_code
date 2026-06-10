"""E2E tests for E-017 withdraw-approved leave (post-approval path).

Tests (written, NOT run — require DURGAM_E2E=1 and a running app):
  1. Withdraw button visible for approved leave within the withdrawal window.
  2. Withdraw button absent when today > ends_on (past the withdrawal window).
  3. Full modal submit flow — reason entered, submit → request moves to history.

Each test creates an ephemeral FACULTY user and inserts an approved LeaveRequest
directly in the DB (bypassing the full approval workflow). The test cleans up
all inserted rows in a finally block.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import BASE_URL, _login

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E") != "1",
    reason="Set DURGAM_E2E=1 and start the app stack to run E2E tests",
)

_EPH_PASS = "Ephemeral_Dev1!XZ"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _create_ephemeral_faculty() -> tuple[str, str]:
    """Create an ephemeral FACULTY user. Returns (username, password)."""
    import uuid as _uuid

    from sqlalchemy import create_engine
    from sqlmodel import Session, select

    from durgam.config import settings
    from durgam.models.identity import Role, User, UserRole
    from durgam.services.password import hash_password

    suffix = _uuid.uuid4().hex[:10]
    username = f"e2e_{suffix}"
    email = f"e2e_{suffix}@sssihl.edu.in"
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(_EPH_PASS),
            is_active=True,
        )
        session.add(user)
        session.flush()
        role = session.exec(select(Role).where(Role.code == "FACULTY")).first()
        if role:
            session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()
        user_id = str(user.id)
    engine.dispose()
    return username, user_id


def _create_approved_leave(
    user_id: str,
    *,
    starts_on: date,
    ends_on: date,
) -> str:
    """Insert an approved LeaveRequest directly in the DB. Returns request id."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    leave_id = str(uuid.uuid4())
    with engine.connect() as conn:
        # Resolve active academic year
        row = conn.execute(
            text(
                "SELECT id FROM academic_years "
                "WHERE starts_on <= :today AND ends_on >= :today "
                "AND is_deleted = false LIMIT 1"
            ),
            {"today": date.today()},
        ).fetchone()
        ay_id = str(row[0]) if row else None
        if ay_id is None:
            engine.dispose()
            pytest.skip("No active academic year configured — cannot run E2E test")

        conn.execute(
            text(
                "INSERT INTO leave_requests "
                "(id, requestor_user_id, academic_year_id, leave_type, "
                " starts_on, ends_on, chargeable_days, sanctioned_days, "
                " state, reason, is_deleted, created_at, updated_at) "
                "VALUES (:id, :uid, :ay, 'CL', :s, :e, 3.0, 3.0, "
                "        'approved', 'E2E test leave', false, NOW(), NOW())"
            ),
            {
                "id": leave_id,
                "uid": user_id,
                "ay": ay_id,
                "s": starts_on.isoformat(),
                "e": ends_on.isoformat(),
            },
        )
        conn.commit()
    engine.dispose()
    return leave_id


def _delete_ephemeral_faculty(username: str) -> None:
    """Hard-delete the ephemeral user and associated leave rows."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        conn.execute(
            text(
                "DELETE FROM leave_requests WHERE requestor_user_id = "
                "(SELECT id FROM users WHERE username = :u)"
            ),
            {"u": username},
        )
        conn.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = "
                "(SELECT id FROM users WHERE username = :u)"
            ),
            {"u": username},
        )
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})
        conn.commit()
    engine.dispose()


def _wait_for_leave_page(page: Page, timeout: int = 15_000) -> None:
    """Wait until the My Leave page has loaded past the spinner."""
    expect(page.get_by_role("heading", name="My Leave")).to_be_visible(timeout=timeout)
    # Wait for the spinner to disappear
    page.wait_for_function(
        "() => !document.querySelector('[data-radix-scroll-area-viewport] [data-loading]')",
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWithdrawApprovedLeave:

    def test_withdraw_button_visible_for_approved_in_window(self, page: Page) -> None:
        """Approved leave with ends_on >= today shows 'Withdraw (post-approval)' button."""
        username, user_id = _create_ephemeral_faculty()
        today = date.today()
        leave_id = _create_approved_leave(
            user_id,
            starts_on=today - timedelta(days=1),
            ends_on=today + timedelta(days=1),
        )
        try:
            _login(page, username, _EPH_PASS)
            page.goto(f"{BASE_URL}/leave")
            page.wait_for_load_state("networkidle")
            expect(page.get_by_role("heading", name="My Leave")).to_be_visible(timeout=15_000)
            # Wait for in-flight section to appear
            expect(page.get_by_text("In-Flight Requests")).to_be_visible(timeout=15_000)
            # The withdraw post-approval button must be visible
            expect(
                page.get_by_role("button", name="Withdraw (post-approval)")
            ).to_be_visible(timeout=10_000)
        finally:
            _delete_ephemeral_faculty(username)

    def test_withdraw_button_absent_after_ends_on(self, page: Page) -> None:
        """Approved leave with ends_on < today does NOT show 'Withdraw (post-approval)'."""
        username, user_id = _create_ephemeral_faculty()
        today = date.today()
        leave_id = _create_approved_leave(
            user_id,
            starts_on=today - timedelta(days=5),
            ends_on=today - timedelta(days=1),
        )
        try:
            _login(page, username, _EPH_PASS)
            page.goto(f"{BASE_URL}/leave")
            page.wait_for_load_state("networkidle")
            expect(page.get_by_role("heading", name="My Leave")).to_be_visible(timeout=15_000)
            # Past-window approved leave should be in history, not in-flight
            # "Withdraw (post-approval)" must NOT appear
            expect(
                page.get_by_role("button", name="Withdraw (post-approval)")
            ).not_to_be_visible(timeout=5_000)
        finally:
            _delete_ephemeral_faculty(username)

    def test_withdraw_modal_submit_flow(self, page: Page) -> None:
        """Open modal, enter reason >= 10 chars, submit → request moves to history."""
        username, user_id = _create_ephemeral_faculty()
        today = date.today()
        _create_approved_leave(
            user_id,
            starts_on=today,
            ends_on=today + timedelta(days=2),
        )
        try:
            _login(page, username, _EPH_PASS)
            page.goto(f"{BASE_URL}/leave")
            page.wait_for_load_state("networkidle")
            expect(page.get_by_role("heading", name="My Leave")).to_be_visible(timeout=15_000)
            expect(page.get_by_text("In-Flight Requests")).to_be_visible(timeout=15_000)

            # Open the withdraw modal
            page.get_by_role("button", name="Withdraw (post-approval)").click()
            expect(
                page.get_by_role("heading", name="Withdraw Approved Leave")
            ).to_be_visible(timeout=10_000)

            # Submit button disabled until reason is >= 10 chars
            submit_btn = page.get_by_role("button", name="Confirm Withdrawal")
            expect(submit_btn).to_be_disabled(timeout=5_000)

            # Enter a valid reason
            reason_input = page.get_by_placeholder("Provide a reason (minimum 10 characters)...")
            reason_input.fill("Change of plans — no longer required.")

            # Submit button now enabled
            expect(submit_btn).to_be_enabled(timeout=5_000)
            submit_btn.click()

            # Modal should close and success toast should appear
            expect(
                page.get_by_role("heading", name="Withdraw Approved Leave")
            ).not_to_be_visible(timeout=10_000)
            expect(
                page.get_by_text("Your leave has been withdrawn")
            ).to_be_visible(timeout=10_000)
        finally:
            _delete_ephemeral_faculty(username)
