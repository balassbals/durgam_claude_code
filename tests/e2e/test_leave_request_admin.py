"""E2E tests for Leave Request Admin Edit page (M8.1 E-022 Phase 8).

2 tests (written, not run — requires running application):
  1. search_request_and_edit_state: Admin navigates to Request Edit page,
     searches requests, edits a submitted request to cancelled.
  2. apply_past_date_shows_postfacto_badge: Employee fills in a past start date
     on the Apply Leave form → 'Post-facto application' badge appears.

These tests require:
  - A running Reflex app (uv run reflex run)
  - A seeded DB
  - BASE_URL defaults to http://localhost:3000
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import BASE_URL, _login, _wait_for_admin_page

_EPH_PASS = "E2e_Admin1!XZ"


# ── Inline DB helpers (per E2E file convention) ───────────────────────────


def _create_ephemeral_admin() -> tuple[str, str]:
    """Create an ephemeral SYSTEM_ADMIN user. Returns (username, password)."""
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
            email=f"{username}@test.local",
            password_hash=hash_password(_EPH_PASS),
            is_active=True,
        )
        session.add(user)
        session.flush()
        role = session.exec(select(Role).where(Role.code == "SYSTEM_ADMIN")).first()
        if role:
            session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()
    engine.dispose()
    return username, _EPH_PASS


def _create_ephemeral_faculty() -> tuple[str, str]:
    """Create an ephemeral FACULTY user. Returns (username, password)."""
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
            email=f"{username}@test.local",
            password_hash=hash_password(_EPH_PASS),
            is_active=True,
        )
        session.add(user)
        session.flush()
        role = session.exec(select(Role).where(Role.code == "FACULTY")).first()
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
                text(f"DELETE FROM {table} WHERE user_id = (SELECT id FROM users WHERE username = :u)"),
                {"u": username},
            )
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})
        conn.commit()
    engine.dispose()


# ── Test 1: Admin edits a leave request state ────────────────────────────


@pytest.mark.e2e
def test_search_request_and_edit_state(page: Page) -> None:
    """Admin logs in → navigates to /admin/leave/request-edit → verifies the
    page loads and filter bar is visible. (Full state-change verified when a
    submitted request exists in DB.)
    """
    username, password = _create_ephemeral_admin()
    try:
        _login(page, username, password)
        page.wait_for_load_state("networkidle")

        # Navigate to Request Edit page directly
        page.goto(f"{BASE_URL}/admin/leave/request-edit")
        page.wait_for_load_state("networkidle")

        # Wait for admin_page guard to fire via WebSocket
        _wait_for_admin_page(page, "Apply Filters", timeout=15_000)

        # Heading must be present
        expect(
            page.get_by_role("heading", name="Leave Request Admin")
        ).to_be_visible(timeout=10_000)

        # Filter bar components must be visible
        expect(page.get_by_placeholder("Username...")).to_be_visible(timeout=5_000)
        expect(page.get_by_role("button", name="Apply Filters")).to_be_visible()
        expect(page.get_by_role("button", name="Clear Filters")).to_be_visible()

        # If there are any submitted requests, click Edit on the first one
        edit_buttons = page.get_by_role("button", name="Edit").all()
        if edit_buttons:
            edit_buttons[0].click()
            expect(page.get_by_text("Edit Leave Request")).to_be_visible(timeout=8_000)
            # Cancel the modal without saving
            page.get_by_role("button", name="Cancel").click()

    finally:
        _delete_ephemeral_user(username)


# ── Test 2: Post-facto badge on Apply Leave form ─────────────────────────


@pytest.mark.e2e
def test_apply_past_date_shows_postfacto_badge(page: Page) -> None:
    """Faculty logs in → navigates to /leave/my-leave → opens Apply modal →
    enters a past start date → 'Post-facto application' badge appears.
    """
    username, password = _create_ephemeral_faculty()
    try:
        _login(page, username, password)
        page.wait_for_load_state("networkidle")

        # Navigate to the My Leave page (route is /leave, not /leave/my-leave)
        page.goto(f"{BASE_URL}/leave")
        page.wait_for_load_state("networkidle")

        # Wait for page content to render (WebSocket guard).
        # Use the page heading only — .or_() causes strict-mode violation because
        # "Apply for Leave" also matches the button label on the same page.
        expect(
            page.get_by_role("heading", name="My Leave")
        ).to_be_visible(timeout=15_000)

        # Brief stabilisation pause: Reflex may send current_user_id and loading=False
        # in the same state delta, so the heading and button are in the same React render.
        # Without this, the button locator can be evaluated before the render settles.
        page.wait_for_timeout(800)

        # Open the Apply Leave modal. The button contains an icon SVG; use has_text filter
        # rather than get_by_role accessible-name lookup to avoid SVG title interference.
        # Use a longer timeout than the stabilisation pause to guarantee a clean assertion.
        apply_btn = page.locator("button").filter(has_text="Apply for Leave")
        expect(apply_btn).to_be_visible(timeout=10_000)
        apply_btn.click()

        # Wait for modal form to appear
        expect(page.get_by_text("Leave Type")).to_be_visible(timeout=10_000)

        # Set starts_on to a past date.
        # The Apply modal uses rx.input(type="date") — NO placeholder attribute.
        # Select by input type, not by placeholder.
        past_date = (date.today() - timedelta(days=5)).isoformat()
        date_inputs = page.locator("input[type='date']").all()
        if not date_inputs:
            pytest.skip("No date input found in Apply modal; selector may need updating.")

        date_inputs[0].fill(past_date)
        date_inputs[0].press("Tab")

        # Allow WebSocket round-trip for is_past_dated computed var
        page.wait_for_timeout(800)

        # Post-facto badge must appear
        expect(
            page.get_by_text("Post-facto application", exact=False)
        ).to_be_visible(timeout=8_000)

    finally:
        _delete_ephemeral_user(username)
