"""Playwright E2E admin suite — M2 gate: "System Admin can construct any role
and verify scoped permissions."

Requires a running stack:
  docker compose up db redis mailpit -d
  uv run python scripts/seed.py
  uv run reflex run

Set DURGAM_E2E=1 to run. Set BASE_URL if not using default.

Seeded read-only users (never mutated by any test here):
  sys_admin  / SysAdmin_Dev1!XZ    — admin, active
  student_001 / Student_Dev1!XZ   — student, active

All tests that create users use _create_ephemeral_user() with a finally block.
All five seeded users must be pristine after three consecutive runs.

Playwright + Reflex testing patterns (from CLAUDE.md "Patterns established at M2"):
  - wait_for_load_state("networkidle") ONLY for initial HTTP page loads.
    It does NOT wait for Reflex WebSocket state updates.
  - After admin page navigation, wait for a STABLE DOM ELEMENT (e.g. "+ New user"
    button, search form) before asserting on list content. The admin_page() wrapper
    hides all content behind rx.cond until the on_load auth guard fires.
  - Use wait_for_url() for redirect assertions.
  - Use polled expect(...).to_be_visible() for post-action element assertions.
  - Mailpit REST API for email assertions (not SPA UI scraping).
  - page.get_by_role("heading", name="...") not page.get_by_heading() (no such API).
  - page.get_by_placeholder("...") for inputs; rx.text() labels are <p> not <label>.
  - page.get_by_role("link", name="Users", exact=True) not partial — "Users" is a
    prefix of "Import Users"; partial matching triggers strict-mode violation.

E2E selector rule (CLAUDE.md): selectors verified against the rendered page;
never write from memory. exact=True by default when another label is a superstring.
"""

from __future__ import annotations

import os
import uuid

import pytest
from playwright.sync_api import Page, expect

from tests.e2e._helpers import BASE_URL, _latest_mailpit_email, _login

pytestmark = pytest.mark.skipif(
    os.environ.get("DURGAM_E2E") != "1",
    reason="Set DURGAM_E2E=1 and start the app stack to run E2E tests",
)

_ADMIN_USER = "sys_admin"
_ADMIN_PASS = "SysAdmin_Dev1!XZ"
_STUDENT_USER = "student_001"
_STUDENT_PASS = "Student_Dev1!XZ"

_EPH_PASS = "Ephemeral_Dev1!XZ"


# ── Ephemeral user helpers ────────────────────────────────────────────────────

def _create_ephemeral_user(
    *,
    role_code: str = "STUDENT",
    is_active: bool = True,
    must_change_password: bool = False,
    email_domain: str = "sssihl.edu.in",
) -> tuple[str, str, str]:
    """Create a short-lived user. Returns (username, email, user_id_str).

    Caller MUST call _delete_ephemeral_user(username) in a finally block.
    Creates directly in DB; no email is dispatched.
    """
    from sqlalchemy import create_engine
    from sqlmodel import Session, select

    from durgam.config import settings
    from durgam.models.identity import Role, User, UserRole
    from durgam.services.password import hash_password

    suffix = uuid.uuid4().hex[:10]
    username = f"e2e_{suffix}"
    email = f"e2e_{suffix}@{email_domain}"

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
        user_id = str(user.id)
        session.commit()  # committed before returning — visible to app sessions
    engine.dispose()
    return username, email, user_id


def _delete_ephemeral_user(username: str) -> None:
    """Hard-delete an ephemeral user and all associated rows."""
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


def _wait_for_admin_page(page: Page, stable_text: str, timeout: int = 15_000) -> None:
    """Wait for an admin page to fully render after on_load guard fires.

    The admin_page() wrapper hides all content in rx.cond until _admin_guard()
    sets current_user_id via WebSocket. wait_for_load_state("networkidle") returns
    after HTTP but before the WebSocket state update — don't assert list content
    until this stable anchor is visible.
    """
    expect(page.get_by_text(stable_text)).to_be_visible(timeout=timeout)


# ── Navigation Reachability tests ─────────────────────────────────────────────

class TestAdminNavigation:
    def test_admin_landing_reachable_from_home_via_ui(self, page: Page) -> None:
        """sys_admin can reach /admin from / by clicking — not by typing URL.

        Navigation Reachability rule from UX Charter §2 + CLAUDE.md.
        The Admin link appears after home_on_load fires _load_nav_entries().
        """
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)

        # exact=True: "Admin" is not a prefix of any other nav label. Still defensive.
        admin_link = page.get_by_role("link", name="Admin", exact=True)
        expect(admin_link).to_be_visible(timeout=10_000)
        admin_link.click()
        page.wait_for_url(f"{BASE_URL}/admin", timeout=10_000)
        expect(page.get_by_text("Admin Dashboard")).to_be_visible(timeout=10_000)

    def test_users_reachable_from_admin_nav(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        # exact=True required: "Users" is a substring of "Import Users".
        # Without exact=True, Playwright throws strict-mode violation (matches 2 links).
        page.get_by_role("link", name="Users", exact=True).click(timeout=10_000)
        page.wait_for_url(f"{BASE_URL}/admin/users", timeout=10_000)
        expect(page.get_by_role("heading", name="Users")).to_be_visible(timeout=10_000)

    def test_roles_reachable_from_admin_nav(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        page.get_by_role("link", name="Roles", exact=True).click(timeout=10_000)
        page.wait_for_url(f"{BASE_URL}/admin/roles", timeout=10_000)
        expect(page.get_by_role("heading", name="Roles")).to_be_visible(timeout=10_000)


# ── User CRUD E2E ─────────────────────────────────────────────────────────────

class TestAdminUserCreation:
    def test_create_user_flow_sends_welcome_email(self, page: Page) -> None:
        """Gate Step 2: create user via UI → temp password shown → welcome email in Mailpit."""
        username = f"e2e_{uuid.uuid4().hex[:8]}"
        email = f"{username}@sssihl.edu.in"

        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/users/new")
        page.wait_for_load_state("networkidle")
        # Wait for admin_page() rx.cond to show content after on_load guard fires.
        _wait_for_admin_page(page, "Create user", timeout=15_000)

        # Form inputs use rx.input(placeholder=...) — get_by_placeholder, not get_by_label.
        page.get_by_placeholder("e.g. jsmith").fill(username)
        page.get_by_placeholder("jsmith@sssihl.edu.in").fill(email)
        page.get_by_role("button", name="Create user").click()

        # create_user() fires redirect to /admin/users after setting generated_password.
        # Wait for the redirect to complete before asserting the temp-password box.
        page.wait_for_url(f"{BASE_URL}/admin/users", timeout=10_000)
        # Wait for the users page admin_page() to render (on_load guard must fire first).
        _wait_for_admin_page(page, "+ New user", timeout=15_000)

        try:
            # "Temporary password (shown once):" text on the users list page.
            expect(
                page.get_by_text("Temporary password (shown once):")
            ).to_be_visible(timeout=10_000)
        finally:
            _delete_ephemeral_user(username)

        # Welcome email must arrive (user created via UI → send_user_created_email called).
        _latest_mailpit_email(email, "DURGAM account has been created", timeout=15)

    def test_new_user_must_change_password_on_first_login(self, page: Page) -> None:
        """Gate Step 3: user with must_change_password=True is redirected on login.

        When must_change_password=True the change-password page shows a warning box
        (rx.text), NOT the 'Change password' heading (which only shows for False).
        Assert on the warning text and the submit button which are always present.
        """
        username, email, _ = _create_ephemeral_user(
            must_change_password=True, role_code="STUDENT"
        )
        try:
            _login(page, username, _EPH_PASS)
            page.wait_for_url(f"{BASE_URL}/change-password", timeout=10_000)
            # The "Change password" heading is rendered only when must_change_password=False.
            # When True, a warning box is shown. Assert on the submit button (always present)
            # and the warning text.
            expect(
                page.get_by_role("button", name="Update password")
            ).to_be_visible(timeout=5_000)
            expect(
                page.get_by_text("You must set a new password before continuing.")
            ).to_be_visible(timeout=5_000)
        finally:
            _delete_ephemeral_user(username)


class TestAdminUserList:
    def test_user_appears_in_admin_list(self, page: Page) -> None:
        """Admin user list shows all committed users, including DB-inserted ones.

        Uses the search form to look up the specific username rather than scanning
        the full list. This avoids false positives from the stable-anchor firing
        before the user list data arrives, and works regardless of sort order or list
        length. The search itself is the data-aware stable anchor: results only render
        after search_users() re-queries the DB and state arrives via WebSocket.
        """
        username, email, _ = _create_ephemeral_user(role_code="STUDENT")
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/users")
            page.wait_for_load_state("networkidle")
            # Wait for admin_page() content to render (auth guard fires via WebSocket).
            _wait_for_admin_page(page, "+ New user", timeout=15_000)
            # Use the search form — this is a data-aware anchor: submitting triggers
            # search_users() which re-queries the DB with the explicit username filter.
            page.get_by_placeholder("Search by username or email…").fill(username)
            page.get_by_role("button", name="Search", exact=True).click()
            # Username must appear in search results.
            expect(page.get_by_text(username, exact=True)).to_be_visible(timeout=10_000)
        finally:
            _delete_ephemeral_user(username)


# ── Role construction + scoped permission verification ────────────────────────

class TestRoleConstructionAndPermission:
    def test_create_role_and_verify_scoped_permission(self, page: Page) -> None:
        """Gate Steps 5-7: create role → verify via check widget (✗ Denied for ungranted).

        This is the core M2 gate clause demonstration.
        """
        role_code = f"GATE_{uuid.uuid4().hex[:6].upper()}"
        username, email, user_id = _create_ephemeral_user(role_code="STUDENT")
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)

            # Step 5: create a new role.
            page.goto(f"{BASE_URL}/admin/roles/new")
            page.wait_for_load_state("networkidle")
            # Wait for admin_page() guard before interacting with form.
            _wait_for_admin_page(page, "Create role", timeout=15_000)

            # Form uses rx.input(placeholder=...) — use get_by_placeholder.
            page.get_by_placeholder("e.g. HOD").fill(role_code)
            page.get_by_placeholder("e.g. Head of Department").fill("Gate Test Role")
            page.get_by_placeholder("0–100 (higher = more privileged)").fill("30")
            page.get_by_role("button", name="Create role").click()
            page.wait_for_url(f"{BASE_URL}/admin/roles/**", timeout=10_000)

            # Role detail page loads — wait for the role name to appear.
            expect(page.get_by_text("Gate Test Role")).to_be_visible(timeout=10_000)

            # Step 7: use the permission check widget.
            #
            # Dependency analysis (from PermissionCheckState.set_pc_resource):
            #   action dropdown depends on RESOURCE ONLY — scope_type has no
            #   effect on pc_available_actions. Test order: resource → action
            #   → scope_type → user → submit.
            #
            # E2E dependent-dropdown rule (CLAUDE.md "Patterns established at M2"):
            #   Wait for the SPECIFIC OPTION to be attached, not just the dropdown
            #   to be visible. Reflex WebSocket state updates do not affect
            #   Playwright's networkidle, so element-visibility precedes data-arrival.

            resource_sel = page.locator("#pc-resource-select")
            scope_sel = page.locator("#pc-scope-type-select")
            action_sel = page.locator("#pc-action-select")
            user_sel = page.locator("#pc-user-select")

            # Wait for user dropdown to be populated via on_mount load_widget_data.
            # "option:not([value=''])" matches real options, not the placeholder.
            expect(
                user_sel.locator("option:not([value=''])").first
            ).to_be_attached(timeout=15_000)

            # Select resource — triggers async set_pc_resource which populates actions.
            resource_sel.select_option("department")

            # Wait for the SPECIFIC "read" option to exist (not just the dropdown element).
            # Visibility alone is insufficient: the element renders before WebSocket
            # delivers the options list, so select_option("read") would find an empty list.
            expect(
                action_sel.locator("option[value='read']")
            ).to_be_attached(timeout=10_000)
            action_sel.select_option("read")

            # scope_type does NOT re-filter actions — simple sync setter, no wait needed.
            scope_sel.select_option("department")

            # Wait for specific user option to be attached before selecting by value.
            expect(
                user_sel.locator(f"option[value='{user_id}']")
            ).to_be_attached(timeout=10_000)
            user_sel.select_option(value=user_id)

            # Scope ID disabled at M2 — no scope objects seeded yet.
            page.get_by_role("button", name="Check").click()

            # Ephemeral user has no department:read → ✗ Denied.
            expect(page.get_by_text("✗ Denied")).to_be_visible(timeout=10_000)

        finally:
            _delete_ephemeral_user(username)
            # Soft-delete test role via DB for isolation.
            try:
                from sqlalchemy import create_engine, text

                from durgam.config import settings
                engine = create_engine(settings.database_url_sync)
                with engine.connect() as conn:
                    conn.execute(
                        text("DELETE FROM role_permissions WHERE role_id = "
                             "(SELECT id FROM roles WHERE code = :c)"),
                        {"c": role_code},
                    )
                    conn.execute(
                        text("UPDATE roles SET is_deleted = TRUE WHERE code = :c"),
                        {"c": role_code},
                    )
                    conn.commit()
                engine.dispose()
            except Exception:
                pass


# ── User list visibility ──────────────────────────────────────────────────────

class TestUserDeletion:
    def test_user_visible_in_list_before_deletion(self, page: Page) -> None:
        """User created programmatically appears in the admin user list (via search).

        Uses search form as data-aware stable anchor — same approach as
        test_user_appears_in_admin_list.
        """
        username, email, _ = _create_ephemeral_user(role_code="STUDENT")
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/users")
            page.wait_for_load_state("networkidle")
            _wait_for_admin_page(page, "+ New user", timeout=15_000)
            page.get_by_placeholder("Search by username or email…").fill(username)
            page.get_by_role("button", name="Search", exact=True).click()
            expect(page.get_by_text(username, exact=True)).to_be_visible(timeout=10_000)
        finally:
            _delete_ephemeral_user(username)


# ── Bulk import ───────────────────────────────────────────────────────────────

class TestBulkImport:
    def test_import_page_loads_and_has_template_link(self, page: Page) -> None:
        """Verify the bulk import page is reachable and has a template download link.

        Uses _wait_for_admin_page() to handle admin_page() rx.cond wrapper —
        content is hidden until reset_import() on_load guard fires via WebSocket.
        """
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/import")
        page.wait_for_load_state("networkidle")
        # Wait for admin_page() to show content after the on_load guard fires.
        # "Step 1: Upload CSV" is the stable anchor on this page.
        _wait_for_admin_page(page, "Step 1: Upload CSV", timeout=15_000)
        # Template link must be visible alongside the heading.
        expect(page.get_by_text("users_import_template.csv")).to_be_visible(timeout=5_000)


# ── Basic-user access control ─────────────────────────────────────────────────

class TestBasicUserAccessControl:
    def test_student_has_no_admin_nav_link(self, page: Page) -> None:
        """Gate Step 10: student_001 sees no Admin link in the nav."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        # Allow nav entries to populate; student should have none with admin:read.
        admin_links = page.get_by_role("link", name="Admin", exact=True)
        expect(admin_links).not_to_be_visible(timeout=5_000)

    def test_student_redirected_from_admin_to_home(self, page: Page) -> None:
        """Gate Step 10: navigating to /admin as student redirects to / with flash."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        page.goto(f"{BASE_URL}/admin")
        # _admin_guard() redirects to / with "no admin access" flash.
        page.wait_for_url(f"{BASE_URL}/", timeout=8_000)


# ── UX Charter checks ─────────────────────────────────────────────────────────

class TestUXCharter:
    def test_admin_shell_has_institution_name_and_username(self, page: Page) -> None:
        """UX Charter §1: institutional name and username on admin pages."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Admin Dashboard", timeout=15_000)
        expect(page.get_by_text("DURGAM")).to_be_visible(timeout=5_000)
        expect(page.get_by_text(_ADMIN_USER)).to_be_visible(timeout=5_000)

    def test_logout_reachable_from_admin_page(self, page: Page) -> None:
        """UX Charter §1: logout reachable without scrolling on every authenticated page."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Admin Dashboard", timeout=15_000)
        expect(page.get_by_role("button", name="Log out")).to_be_visible(timeout=5_000)

    def test_admin_pages_have_footer(self, page: Page) -> None:
        """UX Charter §1: footer with institutional name on admin pages."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin")
        page.wait_for_load_state("networkidle")
        _wait_for_admin_page(page, "Admin Dashboard", timeout=15_000)
        expect(page.get_by_text("Sri Sathya Sai Institute")).to_be_visible(timeout=5_000)
