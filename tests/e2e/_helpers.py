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
    # Wait for the post-login landing page to fully load before any subsequent
    # goto(). Without this, a fast goto() can interrupt Reflex's auth-state
    # settlement — the new page's on_load guard fires before the session cookie
    # is established, sees no auth, and redirects back to /login.
    page.wait_for_load_state("networkidle")


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


def _hard_delete_dept_by_code(code: str) -> None:
    """Hard-delete a department and its dependent join rows.

    Departments have DepartmentCampus join rows with a FK constraint on
    departments.id. Direct DELETE on departments would raise ForeignKeyViolation.
    Must delete department_campuses first.
    """
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "DELETE FROM department_campuses WHERE department_id = "
                    "(SELECT id FROM departments WHERE code = :code)"  # noqa: S608
                ),
                {"code": code},
            )
            conn.execute(
                text("DELETE FROM departments WHERE code = :code"),  # noqa: S608
                {"code": code},
            )
            conn.commit()
    finally:
        engine.dispose()


def _delete_university_missions_matching(pattern: str) -> None:
    """Hard-delete university_missions rows whose text matches a SQL LIKE pattern.

    Used to pre-clean accumulated test data before a test run, and as a
    fallback in finally blocks when the UI removal step is part of the test.
    """
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM university_missions WHERE statement LIKE :p"),  # noqa: S608
                {"p": pattern},
            )
            conn.commit()
    finally:
        engine.dispose()


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


def _hard_delete_calendar_entries_by_title(pattern: str) -> None:
    """Hard-delete calendar_entries rows whose title matches a SQL LIKE pattern."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM calendar_entries WHERE title LIKE :p"),  # noqa: S608
                {"p": pattern},
            )
            conn.commit()
    finally:
        engine.dispose()


def _hard_delete_academic_year_by_code(code: str) -> None:
    """Hard-delete an academic year and its dependent rows (holidays, calendar entries, student category counts)."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings

    engine = create_engine(settings.database_url_sync)
    try:
        with engine.connect() as conn:
            ay_id = conn.execute(
                text("SELECT id FROM academic_years WHERE code = :code"),  # noqa: S608
                {"code": code},
            ).fetchone()
            if ay_id:
                ay_uuid = ay_id[0]
                conn.execute(
                    text("DELETE FROM calendar_entries WHERE academic_year_id = :id"),
                    {"id": ay_uuid},
                )
                conn.execute(
                    text("DELETE FROM holidays WHERE academic_year_id = :id"),
                    {"id": ay_uuid},
                )
                conn.execute(
                    text("DELETE FROM student_category_counts WHERE academic_year_id = :id"),
                    {"id": ay_uuid},
                )
                conn.execute(
                    text("DELETE FROM academic_years WHERE id = :id"),
                    {"id": ay_uuid},
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


def _hard_delete_letterhead_by_role(role_code: str) -> None:
    """Hard-delete letterhead_assets (and their file_assets) for a given role_code.

    Removes letterhead rows first, then the associated file_asset rows
    (referenced by file_id FK). Also removes the storage blob.
    """
    from sqlalchemy import create_engine, text

    from durgam.config import settings
    from durgam.storage import get_storage_backend

    engine = create_engine(settings.database_url_sync)
    try:
        backend = get_storage_backend()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT la.id, fa.storage_key, la.file_id "
                    "FROM letterhead_assets la "
                    "JOIN file_assets fa ON fa.id = la.file_id "
                    "WHERE la.role_code = :rc"
                ),
                {"rc": role_code},
            ).fetchall()
            for row in rows:
                conn.execute(
                    text("DELETE FROM letterhead_assets WHERE id = :id"),
                    {"id": row[0]},
                )
                conn.execute(
                    text("DELETE FROM file_assets WHERE id = :id"),
                    {"id": row[2]},
                )
                try:
                    backend.delete(row[1])
                except FileNotFoundError:
                    pass
            conn.commit()
    finally:
        engine.dispose()


def _hard_delete_template_by_type(template_type: str) -> None:
    """Hard-delete template_assets (and their file_assets) for a given template_type."""
    from sqlalchemy import create_engine, text

    from durgam.config import settings
    from durgam.storage import get_storage_backend

    engine = create_engine(settings.database_url_sync)
    try:
        backend = get_storage_backend()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT ta.id, fa.storage_key, ta.file_id "
                    "FROM template_assets ta "
                    "JOIN file_assets fa ON fa.id = ta.file_id "
                    "WHERE ta.template_type = :tt"
                ),
                {"tt": template_type},
            ).fetchall()
            for row in rows:
                conn.execute(
                    text("DELETE FROM template_assets WHERE id = :id"),
                    {"id": row[0]},
                )
                conn.execute(
                    text("DELETE FROM file_assets WHERE id = :id"),
                    {"id": row[2]},
                )
                try:
                    backend.delete(row[1])
                except FileNotFoundError:
                    pass
            conn.commit()
    finally:
        engine.dispose()
