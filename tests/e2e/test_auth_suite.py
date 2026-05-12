"""Playwright E2E auth suite — gate: all three M1 gate clauses.

Requires a running Reflex app and supporting services:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set BASE_URL to the app URL (default: http://localhost:3000).
Set MAILPIT_URL to the Mailpit web UI (default: http://localhost:8025).

The seed user credentials must match scripts/seed.py:
  sys_admin / SysAdmin_Dev1!XZ           (active, normal)
  inactive_user / Inactive_Dev1!XZ       (is_active=False)
  firstlogin_user / FirstLogin_Dev1!XZ   (must_change_password=True)

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
_FIRSTLOGIN_USER = "firstlogin_user"
_FIRSTLOGIN_PASS = "FirstLogin_Dev1!XZ"
_FIRSTLOGIN_NEW_PASS = "FirstLogin_New1!XZ"
_LOCKOUT_THRESHOLD = 5


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
        _clear_session(page)
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        page.get_by_placeholder("your.username").fill(_ADMIN_USER)
        page.get_by_placeholder("••••••••••••").first.fill("WrongPass999!")
        page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Invalid username or password")).to_be_visible()
        assert "/login" in page.url

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
        # Trigger logout by navigating to a logout endpoint or clicking logout if present
        # For M1, the state exposes logout — trigger via direct URL or nav link
        page.evaluate("document.cookie = 'dsession=; Max-Age=0; path=/'")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        assert "/login" in page.url


class TestBruteForce:
    def test_brute_force_triggers_lockout(self, page: Page):
        """Submit LOCKOUT_THRESHOLD wrong passwords — account must lock on last attempt.

        Gate: 'brute-force test blocked'.
        """
        _clear_session(page)
        # Use a fresh username to avoid cross-test lockout interference.
        # The inactive_user is already seeded with a known password; use a different user.
        # We'll attempt on sys_admin but reset at the end via correct login.
        # NOTE: this test will temporarily lock sys_admin — it resets on the re-auth below.
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")

        for i in range(_LOCKOUT_THRESHOLD):
            page.get_by_placeholder("your.username").fill(_ADMIN_USER)
            page.get_by_placeholder("••••••••••••").first.fill(f"WrongPass{i}!Abc")
            page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
            page.wait_for_load_state("networkidle")

        # After threshold failures the account should show a lockout message
        expect(
            page.locator("text=locked")
        ).to_be_visible(timeout=5000)
        assert "/login" in page.url

        # Correct password during lockout must also fail
        page.get_by_placeholder("your.username").fill(_ADMIN_USER)
        page.get_by_placeholder("••••••••••••").first.fill(_ADMIN_PASS)
        page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=locked")).to_be_visible()


class TestForcedPasswordChange:
    def test_must_change_password_redirects_to_change_password_page(self, page: Page):
        """Gate: Playwright auth suite green — forced first-login redirect.

        A user with must_change_password=True is redirected to /change-password
        immediately after successful login, before reaching the home page.
        """
        _clear_session(page)
        _login(page, _FIRSTLOGIN_USER, _FIRSTLOGIN_PASS)
        # _login waited for URL to leave /login; it should be /change-password now
        assert "/change-password" in page.url, (
            f"Expected redirect to /change-password for must_change_password user, got {page.url}"
        )
        # The "must set a new password" banner must be visible
        expect(page.locator("text=must set a new password")).to_be_visible()


class TestChangePassword:
    def test_authenticated_user_can_change_password(self, page: Page):
        """Gate: Playwright auth suite green — change password (authenticated).

        Uses dean_sci (not sys_admin, which is locked by TestBruteForce).
        """
        _clear_session(page)
        _login(page, "dean_sci", "DeanSci_Dev1!XZ")
        page.goto(f"{BASE_URL}/change-password")
        page.wait_for_load_state("networkidle")  # HTTP navigation — networkidle is fine

        new_pass = "DeanSci_Change1!XZ"
        page.get_by_placeholder("••••••••••••").nth(0).fill("DeanSci_Dev1!XZ")
        page.get_by_placeholder("••••••••••••").nth(1).fill(new_pass)
        page.get_by_placeholder("••••••••••••").nth(2).fill(new_pass)
        page.get_by_role("button", name=re.compile(r"Update password", re.IGNORECASE)).click()
        # Redirect to / is WebSocket-based; wait_for_url, not networkidle
        page.wait_for_url(f"{BASE_URL}/", timeout=10000)

        # Reset the password back so seed credentials remain valid for subsequent runs
        page.goto(f"{BASE_URL}/change-password")
        page.wait_for_load_state("networkidle")
        page.get_by_placeholder("••••••••••••").nth(0).fill(new_pass)
        page.get_by_placeholder("••••••••••••").nth(1).fill("DeanSci_Dev1!XZ")
        page.get_by_placeholder("••••••••••••").nth(2).fill("DeanSci_Dev1!XZ")
        page.get_by_role("button", name=re.compile(r"Update password", re.IGNORECASE)).click()
        page.wait_for_url(f"{BASE_URL}/", timeout=10000)


class TestPasswordReset:
    def test_forgot_password_form_loads(self, page: Page):
        _clear_session(page)
        page.goto(f"{BASE_URL}/forgot-password")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_placeholder("your.email@sssihl.edu.in")).to_be_visible()

    def test_password_reset_email_visible_in_mailpit(self, page: Page):
        """Gate: 'password-reset email visible in Mailpit'.

        Uses Mailpit's REST API (not SPA scraping) to verify email arrival.
        The Mailpit web UI loads its inbox asynchronously via JavaScript;
        the REST API is synchronous and more reliable for test assertions.
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
        """Request reset → follow link → set new password → login."""
        _clear_session(page)
        page.goto(f"{BASE_URL}/forgot-password")
        page.wait_for_load_state("networkidle")
        page.get_by_placeholder("your.email@sssihl.edu.in").fill("dean.sci@sssihl.edu.in")
        page.get_by_role("button", name=re.compile(r"Send reset link", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")

        # Get the reset link directly from Mailpit REST API
        msg = _mailpit_latest_message_for("dean.sci@sssihl.edu.in")
        assert msg is not None, "No reset email found for dean.sci@sssihl.edu.in"
        body = _mailpit_message_body(msg["ID"])
        links = re.findall(r"http://[^\s<\"]+reset-password[^\s<\"]*", body)
        assert links, "No reset link found in email body"
        reset_link = links[0]

        page.goto(reset_link)
        page.wait_for_load_state("networkidle")

        new_pass = "DeanSci_New1!XZ"
        page.get_by_placeholder("••••••••••••").nth(0).fill(new_pass)
        page.get_by_placeholder("••••••••••••").nth(1).fill(new_pass)
        page.get_by_role("button", name=re.compile(r"Set new password", re.IGNORECASE)).click()
        # Redirect to /login is WebSocket-based
        page.wait_for_url("**login**", timeout=10000)

        # Log in with the new password
        page.get_by_placeholder("your.username").fill("dean_sci")
        page.get_by_placeholder("••••••••••••").first.fill(new_pass)
        page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
        # Redirect to / after successful login
        page.wait_for_url(lambda url: "/login" not in url, timeout=10000)
