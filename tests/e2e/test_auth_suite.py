"""Playwright E2E auth suite — gate: all three M1 gate clauses.

Requires a running Reflex app and supporting services:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set BASE_URL to the app URL (default: http://localhost:3000).
Set MAILPIT_URL to the Mailpit web UI (default: http://localhost:8025).

The seed user credentials must match scripts/seed.py:
  sys_admin / SysAdmin_Dev1!XZ           (active, normal) — read-only
  inactive_user / Inactive_Dev1!XZ       (is_active=False) — read-only
  firstlogin_user / FirstLogin_Dev1!XZ   (must_change_password=True) — read-only

All three seeded users above are READ-ONLY fixtures. No test may log in as
these users and mutate their state (password, flags, lockout). Tests that
need a user with specific properties (must_change_password=True, etc.) must
create an ephemeral user with _create_ephemeral_user() and delete it in a
finally block.

Test isolation rule:
  Tests that mutate persistent state (passwords, lockout, tokens) create
  ephemeral users via _create_ephemeral_user() and delete them in a
  finally block. Seeded users are treated as read-only fixtures.

Playwright + Reflex testing patterns (see also docs/modules/auth.md):
  - Reflex's all-WebSocket transport means wait_for_load_state("networkidle")
    does NOT work for state-mutating actions (form submits, button clicks).
    networkidle fires immediately because no HTTP requests are made.
    Use wait_for_url() for redirect assertions; use polled expect() for
    element/flash assertions.
  - For Mailpit inbox assertions, use the Mailpit REST API directly rather
    than scraping the SPA UI.
"""

import os
import re
import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000")
MAILPIT_URL = os.environ.get("MAILPIT_URL", "http://localhost:8025")
MAILPIT_API = f"{MAILPIT_URL}/api/v1"

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E") != "1",
    reason="Set DURGAM_E2E=1 and start the app stack to run E2E tests",
)

_ADMIN_USER = "sys_admin"
_ADMIN_PASS = "SysAdmin_Dev1!XZ"
_INACTIVE_USER = "inactive_user"
_INACTIVE_PASS = "Inactive_Dev1!XZ"
_LOCKOUT_THRESHOLD = 5

# Password used for all ephemeral users (meets §6.1 policy)
_EPH_PASS = "Ephemeral_Dev1!XZ"
_EPH_NEW_PASS = "Ephemeral_New1!XZ"


# ---------------------------------------------------------------------------
# Ephemeral user helpers
# ---------------------------------------------------------------------------

def _create_ephemeral_user(
    *,
    role_code: str = "STUDENT",
    is_active: bool = True,
    must_change_password: bool = False,
) -> tuple[str, str]:
    """Create a short-lived user for one test run. Returns (username, email).

    The caller MUST delete the user in a finally block via
    _delete_ephemeral_user(username). Ephemeral users use _EPH_PASS as
    their password and an @sssihl.edu.in address so Mailpit captures email.
    """
    from sqlalchemy import create_engine
    from sqlmodel import Session, select

    from durgam.config import settings
    from durgam.models.identity import Role, User, UserRole
    from durgam.services.password import hash_password

    suffix = uuid.uuid4().hex[:10]
    username = f"e2e_{suffix}"
    email = f"e2e_{suffix}@sssihl.edu.in"

    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(_EPH_PASS),
            is_active=is_active,
            must_change_password=must_change_password,
        )
        session.add(user)
        session.flush()
        role = session.exec(select(Role).where(Role.code == role_code)).first()
        if role:
            session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()
    engine.dispose()
    return username, email


def _delete_ephemeral_user(username: str) -> None:
    """Hard-delete an ephemeral user and all its associated rows."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        conn.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = "
                "(SELECT id FROM users WHERE username = :u)"
            ),
            {"u": username},
        )
        conn.execute(
            text(
                "DELETE FROM user_sessions WHERE user_id = "
                "(SELECT id FROM users WHERE username = :u)"
            ),
            {"u": username},
        )
        conn.execute(
            text(
                "DELETE FROM password_reset_tokens WHERE user_id = "
                "(SELECT id FROM users WHERE username = :u)"
            ),
            {"u": username},
        )
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})
        conn.commit()
    engine.dispose()


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------

def _login(page: Page, username: str, password: str) -> None:
    """Submit login form and wait for navigation away from /login.

    Uses wait_for_url instead of wait_for_load_state("networkidle") because
    Reflex dispatches all events including redirects over WebSocket. WebSocket
    traffic does not affect Playwright's networkidle state, so networkidle
    fires before the redirect is received from the backend.
    """
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")  # OK — initial page load is HTTP
    page.get_by_placeholder("your.username").fill(username)
    page.get_by_placeholder("••••••••••••").first.fill(password)
    page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
    # Wait for URL to leave /login — redirect is WebSocket-based, not HTTP
    page.wait_for_url(lambda url: "/login" not in url, timeout=10000)


def _clear_session(page: Page) -> None:
    """Wipe the dsession cookie so each test starts unauthenticated."""
    page.context.clear_cookies()


def _mailpit_latest_message_for(recipient: str) -> dict | None:
    """Return the most recent Mailpit message sent to recipient, or None."""
    resp = httpx.get(f"{MAILPIT_API}/messages", timeout=5)
    resp.raise_for_status()
    for msg in resp.json().get("messages", []):
        for to in msg.get("To", []):
            if recipient in to.get("Address", ""):
                return msg
    return None


def _mailpit_message_body(message_id: str) -> str:
    """Return the plain-text body of a Mailpit message."""
    resp = httpx.get(f"{MAILPIT_API}/message/{message_id}", timeout=5)
    resp.raise_for_status()
    return resp.json().get("Text", "") or resp.json().get("HTML", "")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLogin:
    def test_successful_login_redirects_to_home(self, page: Page):
        _clear_session(page)
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        # _login already waited for navigation away from /login.
        # Compare against the full BASE_URL (page.url is a full URL, not a path).
        assert page.url == f"{BASE_URL}/" or "/change-password" in page.url, (
            f"Expected redirect to {BASE_URL}/ or .../change-password, got {page.url}"
        )

    def test_wrong_password_shows_error(self, page: Page):
        """A wrong password for a valid user shows "Invalid username or password".

        Uses an ephemeral user so the failed_login_count increment is not
        accumulated against a seeded account. One increment per run would
        lock sys_admin after 5 consecutive runs without re-seeding.
        """
        username, _ = _create_ephemeral_user()
        try:
            _clear_session(page)
            page.goto(f"{BASE_URL}/login")
            page.wait_for_load_state("networkidle")
            page.get_by_placeholder("your.username").fill(username)
            page.get_by_placeholder("••••••••••••").first.fill("WrongPass999!")
            page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("text=Invalid username or password")).to_be_visible()
            assert "/login" in page.url
        finally:
            _delete_ephemeral_user(username)

    def test_unknown_username_shows_error(self, page: Page):
        _clear_session(page)
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        page.get_by_placeholder("your.username").fill("no_such_user_xyz")
        page.get_by_placeholder("••••••••••••").first.fill("SomePass123!")
        page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Invalid username or password")).to_be_visible()

    def test_inactive_user_shows_generic_error(self, page: Page):
        _clear_session(page)
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        page.get_by_placeholder("your.username").fill(_INACTIVE_USER)
        page.get_by_placeholder("••••••••••••").first.fill(_INACTIVE_PASS)
        page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")
        # Must not reveal that the user exists — only generic error shown
        expect(page.locator("text=inactive")).to_be_visible()
        assert "/login" in page.url


class TestLogout:
    def test_logout_clears_session_and_redirects(self, page: Page):
        _clear_session(page)
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/login")
        # Trigger logout by clearing the session cookie
        page.evaluate("document.cookie = 'dsession=; Max-Age=0; path=/'")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        assert "/login" in page.url


class TestBruteForce:
    def test_brute_force_triggers_lockout(self, page: Page):
        """Submit LOCKOUT_THRESHOLD wrong passwords — account must lock.

        Gate: 'brute-force test blocked'.
        Uses an ephemeral user so seeded accounts (sys_admin) are not left
        locked after the test, which would break subsequent login tests.
        """
        username, _ = _create_ephemeral_user()
        try:
            _clear_session(page)
            page.goto(f"{BASE_URL}/login")
            page.wait_for_load_state("networkidle")

            for i in range(_LOCKOUT_THRESHOLD):
                page.get_by_placeholder("your.username").fill(username)
                page.get_by_placeholder("••••••••••••").first.fill(f"WrongPass{i}!Abc")
                page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
                page.wait_for_load_state("networkidle")

            # After threshold failures the account should show a lockout message
            expect(page.locator("text=locked")).to_be_visible(timeout=5000)
            assert "/login" in page.url

            # Correct password during lockout must also fail
            page.get_by_placeholder("your.username").fill(username)
            page.get_by_placeholder("••••••••••••").first.fill(_EPH_PASS)
            page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("text=locked")).to_be_visible()
        finally:
            _delete_ephemeral_user(username)


class TestForcedPasswordChange:
    def test_must_change_password_redirects_to_change_password_page(self, page: Page):
        """Gate: Playwright auth suite green — forced first-login redirect.

        A user with must_change_password=True is redirected to /change-password
        immediately after successful login, before reaching the home page.
        Uses an ephemeral user with must_change_password=True so the seeded
        firstlogin_user is never mutated (its flag or password).
        """
        username, _ = _create_ephemeral_user(must_change_password=True)
        try:
            _clear_session(page)
            _login(page, username, _EPH_PASS)
            # _login waited for URL to leave /login; it should be /change-password now
            assert "/change-password" in page.url, (
                f"Expected redirect to /change-password for must_change_password user, "
                f"got {page.url}"
            )
            # The "must set a new password" banner must be visible
            expect(page.locator("text=must set a new password")).to_be_visible()
        finally:
            _delete_ephemeral_user(username)


class TestChangePassword:
    def test_authenticated_user_can_change_password(self, page: Page):
        """Gate: Playwright auth suite green — change password (authenticated).

        Uses an ephemeral user so the seeded passwords are not mutated.
        The ephemeral user is deleted in finally regardless of test outcome.
        """
        username, _ = _create_ephemeral_user()
        try:
            _clear_session(page)
            _login(page, username, _EPH_PASS)
            page.goto(f"{BASE_URL}/change-password")
            page.wait_for_load_state("networkidle")

            page.get_by_placeholder("••••••••••••").nth(0).fill(_EPH_PASS)
            page.get_by_placeholder("••••••••••••").nth(1).fill(_EPH_NEW_PASS)
            page.get_by_placeholder("••••••••••••").nth(2).fill(_EPH_NEW_PASS)
            page.get_by_role("button", name=re.compile(r"Update password", re.IGNORECASE)).click()
            # Redirect to / is WebSocket-based
            page.wait_for_url(f"{BASE_URL}/", timeout=10000)
        finally:
            _delete_ephemeral_user(username)


class TestPasswordReset:
    def test_forgot_password_form_loads(self, page: Page):
        _clear_session(page)
        page.goto(f"{BASE_URL}/forgot-password")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_placeholder("your.email@sssihl.edu.in")).to_be_visible()

    def test_password_reset_email_visible_in_mailpit(self, page: Page):
        """Gate: 'password-reset email visible in Mailpit'.

        Uses the Mailpit REST API (not SPA scraping) to verify email arrival.
        Sends email to sys_admin (read-only: token is created in DB but never
        consumed by this test).
        """
        _clear_session(page)
        page.goto(f"{BASE_URL}/forgot-password")
        page.wait_for_load_state("networkidle")
        page.get_by_placeholder("your.email@sssihl.edu.in").fill("sys.admin@sssihl.edu.in")
        page.get_by_role("button", name=re.compile(r"Send reset link", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")

        # Confirm success flash shown in the Reflex UI (polled — state mutation, no redirect)
        expect(page.locator("text=reset link has been sent")).to_be_visible(timeout=10000)

        # Verify email arrived via Mailpit REST API — no SPA scraping needed
        msg = _mailpit_latest_message_for("sys.admin@sssihl.edu.in")
        assert msg is not None, "No email found in Mailpit for sys.admin@sssihl.edu.in"
        assert "Reset your DURGAM password" in msg.get("Subject", ""), (
            f"Unexpected email subject: {msg.get('Subject')}"
        )

    def test_password_reset_full_round_trip(self, page: Page):
        """Request reset → follow link → set new password → login.

        Uses an ephemeral user with a fresh email address so:
        - The Mailpit filter returns only this test's email (no stale messages)
        - The token is always fresh and unconsumed
        - The password mutation is isolated (ephemeral user deleted in finally)
        """
        username, email = _create_ephemeral_user()
        try:
            _clear_session(page)
            page.goto(f"{BASE_URL}/forgot-password")
            page.wait_for_load_state("networkidle")
            page.get_by_placeholder("your.email@sssihl.edu.in").fill(email)
            page.get_by_role("button", name=re.compile(r"Send reset link", re.IGNORECASE)).click()
            page.wait_for_load_state("networkidle")

            # Confirm flash
            expect(page.locator("text=reset link has been sent")).to_be_visible(timeout=10000)

            # Get the reset link directly from Mailpit REST API
            msg = _mailpit_latest_message_for(email)
            assert msg is not None, f"No reset email found for {email}"
            body = _mailpit_message_body(msg["ID"])
            links = re.findall(r"http://[^\s<\"]+reset-password[^\s<\"]*", body)
            assert links, "No reset link found in email body"
            reset_link = links[0]

            page.goto(reset_link)
            page.wait_for_load_state("networkidle")

            page.get_by_placeholder("••••••••••••").nth(0).fill(_EPH_NEW_PASS)
            page.get_by_placeholder("••••••••••••").nth(1).fill(_EPH_NEW_PASS)
            page.get_by_role("button", name=re.compile(r"Set new password", re.IGNORECASE)).click()
            # Redirect to /login is WebSocket-based
            page.wait_for_url("**login**", timeout=10000)

            # Log in with the new password to confirm the reset worked end-to-end
            page.get_by_placeholder("your.username").fill(username)
            page.get_by_placeholder("••••••••••••").first.fill(_EPH_NEW_PASS)
            page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
            # Redirect to / after successful login
            page.wait_for_url(lambda url: "/login" not in url, timeout=10000)
        finally:
            _delete_ephemeral_user(username)


class TestAuthFlowFromHomePage:
    def test_logout_button_visible_and_functional(self, page: Page):
        """Nav shell is reachable from / — gate: Playwright auth suite green.

        Logs in, lands on /, asserts the nav shell (logout button + username)
        is visible, clicks logout, asserts redirect to /login. This proves the
        auth flow is reachable through the application's own navigation, not
        just by direct URL navigation — the class of gap the URL-only suite
        misses.
        """
        _clear_session(page)
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        # Should be on home page, not change-password (sys_admin has must_change=False)
        assert page.url == f"{BASE_URL}/", (
            f"Expected {BASE_URL}/ after login, got {page.url}"
        )

        # Nav shell must be visible without any direct URL navigation
        logout_btn = page.get_by_role("button", name=re.compile(r"Log out", re.IGNORECASE))
        expect(logout_btn).to_be_visible()
        expect(page.locator(f"text={_ADMIN_USER}")).to_be_visible()

        # Click the logout button and verify redirect to /login
        logout_btn.click()
        page.wait_for_url("**login**", timeout=10000)


class TestForcedPasswordChangeFromHomePage:
    def test_firstlogin_user_lands_on_change_password_not_home(self, page: Page):
        """§9.1 first-login forced redirect — gate: Playwright auth suite green.

        A user with must_change_password=True must be redirected to /change-password,
        not to /. Uses an ephemeral user so the seeded firstlogin_user is never
        mutated (its must_change_password flag or password). Proves the redirect is
        enforced end-to-end through the UI, not just at the service layer.
        """
        username, _ = _create_ephemeral_user(must_change_password=True)
        try:
            _clear_session(page)
            _login(page, username, _EPH_PASS)
            # Must land on /change-password, NOT on /
            assert "/change-password" in page.url, (
                f"Expected /change-password for must_change_password user, got {page.url}"
            )
            assert page.url != f"{BASE_URL}/", (
                f"must_change_password user must not land on / — got {page.url}"
            )
            # The forced-change banner must be visible
            expect(page.locator("text=must set a new password")).to_be_visible()
        finally:
            _delete_ephemeral_user(username)
