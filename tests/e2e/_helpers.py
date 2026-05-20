"""Shared E2E helpers used by all test suites.

A single canonical _login() helper prevents selector drift between test
files (the root cause of the M2 selector bug: the helper was re-written
from memory in test_admin_suite.py with wrong placeholder text).

Rule (captured in CLAUDE.md): every new E2E file imports _login from here;
it must never duplicate the helper.
"""

from __future__ import annotations

import os
import re
import time

import httpx
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000")
MAILPIT_URL = os.environ.get("MAILPIT_URL", "http://localhost:8025")
MAILPIT_API = f"{MAILPIT_URL}/api/v1"


def _login(page: Page, username: str, password: str) -> None:
    """Submit login form and wait for navigation away from /login.

    Uses wait_for_url (not wait_for_load_state("networkidle")) because
    Reflex dispatches all events including redirects over WebSocket.
    WebSocket traffic does not affect Playwright's networkidle state,
    so networkidle fires before the redirect is received.

    Selectors verified against the rendered login page:
      - Username: placeholder "your.username"
      - Password: placeholder "••••••••••••" (12 bullet characters)
      - Submit:   button with text matching /Sign in/i
    """
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")  # OK — initial page load is HTTP
    page.get_by_placeholder("your.username").fill(username)
    page.get_by_placeholder("••••••••••••").first.fill(password)
    page.get_by_role("button", name=re.compile(r"Sign in", re.IGNORECASE)).click()
    # Wait for URL to leave /login — redirect is WebSocket-based, not HTTP
    page.wait_for_url(lambda url: "/login" not in url, timeout=10_000)


def _logout(page: Page) -> None:
    """Click the logout button and wait for /login redirect."""
    page.get_by_role("button", name="Log out").click()
    page.wait_for_url(f"{BASE_URL}/login", timeout=10_000)


def get_seeded_user_id(username: str) -> str:
    """Return the UUID of a seeded user as a string.

    Used by E2E tests that need a seeded user's DB UUID (e.g., to select them
    in the permission check widget). Never call on ephemeral users — those are
    created inline in the test and their IDs come from _create_ephemeral_user().
    """
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            if result is None:
                raise ValueError(f"Seeded user not found: {username}")
            return str(result[0])
    finally:
        engine.dispose()


def _wait_for_admin_page(page: Page, stable_text: str, timeout: int = 15_000) -> None:
    """Wait for an admin page to fully render after on_load guard fires.

    The admin_page() wrapper hides all content in rx.cond until _admin_guard()
    (or _config_guard) sets admin_authorized via WebSocket. networkidle fires
    before that WebSocket update, so always wait for a stable DOM anchor.
    """
    expect(page.get_by_text(stable_text)).to_be_visible(timeout=timeout)


def _hard_delete_by_code(table: str, code: str) -> None:
    """Hard-delete a config entity by its code column.

    Used in CRUD test finally-blocks to ensure cleanup even when a test
    fails before the soft-delete step. Also pre-cleans leftover entities
    from previous failed runs so tests are order-independent.

    Tables supported: campuses, schools, centres_of_excellence,
    departments, courses (and their FKs are cascade-deleted).
    """
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(f"DELETE FROM {table} WHERE code = :code"),  # noqa: S608
                {"code": code},
            )
            conn.commit()
    finally:
        engine.dispose()


def _latest_mailpit_email(
    to_address: str, subject_contains: str, timeout: int = 15
) -> dict:
    """Poll Mailpit REST API for the most recent matching email."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{MAILPIT_API}/messages", timeout=5)
        resp.raise_for_status()
        for msg in resp.json().get("messages", []):
            if (
                subject_contains.lower() in msg.get("Subject", "").lower()
                and any(
                    to_address in r.get("Address", "") for r in msg.get("To", [])
                )
            ):
                return msg
        time.sleep(1)
    raise AssertionError(
        f"No Mailpit email to {to_address!r} with subject containing "
        f"{subject_contains!r} within {timeout}s"
    )
