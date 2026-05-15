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

Playwright + Reflex testing patterns (inherited from M1):
  - wait_for_load_state("networkidle") ONLY for initial HTTP page loads.
  - Use wait_for_url() for redirect assertions.
  - Use polled expect(...).to_be_visible() for post-action element assertions.
  - Mailpit REST API for email assertions (not SPA UI scraping).
  - page.get_by_role("heading", name="...") not page.get_by_heading() (no such API).
  - page.get_by_placeholder("...") for inputs; forms use rx.text() labels not <label>.

E2E selector rule (CLAUDE.md): every selector verified against the rendered page
before committing. Never write selectors from memory or from the page's intent.
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
    This creates the user directly in the DB; no email is sent.
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
        session.commit()
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


# ── Navigation Reachability tests ─────────────────────────────────────────────

class TestAdminNavigation:
    def test_admin_landing_reachable_from_home_via_ui(self, page: Page) -> None:
        """sys_admin can reach /admin from / by clicking — not by typing URL.

        This is the Navigation Reachability rule from UX Charter §2 + CLAUDE.md.
        The Admin link appears in the nav shell only after home_on_load fires
        _load_nav_entries() for sys_admin.
        """
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)

        # Admin link must be visible in the nav shell without typing a URL.
        admin_link = page.get_by_role("link", name="Admin")
        expect(admin_link).to_be_visible(timeout=10_000)
        admin_link.click()
        page.wait_for_url(f"{BASE_URL}/admin", timeout=10_000)
        expect(page.get_by_text("Admin Dashboard")).to_be_visible(timeout=8_000)

    def test_users_reachable_from_admin_nav(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        # Wait for nav entries to populate after home_on_load fires.
        page.get_by_role("link", name="Users").click(timeout=10_000)
        page.wait_for_url(f"{BASE_URL}/admin/users", timeout=10_000)
        # "Users" heading is rendered by rx.heading — use role="heading".
        expect(page.get_by_role("heading", name="Users")).to_be_visible(timeout=8_000)

    def test_roles_reachable_from_admin_nav(self, page: Page) -> None:
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        page.get_by_role("link", name="Roles").click(timeout=10_000)
        page.wait_for_url(f"{BASE_URL}/admin/roles", timeout=10_000)
        expect(page.get_by_role("heading", name="Roles")).to_be_visible(timeout=8_000)


# ── User CRUD E2E ─────────────────────────────────────────────────────────────

class TestAdminUserCreation:
    def test_create_user_flow_sends_welcome_email(self, page: Page) -> None:
        """Gate Step 2: create user via UI → temp password shown → welcome email in Mailpit."""
        username = f"e2e_{uuid.uuid4().hex[:8]}"
        email = f"{username}@sssihl.edu.in"

        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/users/new")
        page.wait_for_load_state("networkidle")

        # Form inputs use rx.input(name=..., placeholder=...).
        # The visible labels are rx.text() (renders as <p>), NOT <label> elements.
        # Selector: get_by_placeholder(), NOT get_by_label().
        page.get_by_placeholder("e.g. jsmith").fill(username)
        page.get_by_placeholder("jsmith@sssihl.edu.in").fill(email)
        page.get_by_role("button", name="Create user").click()

        # Temp password must appear in the UI (exactly once).
        try:
            expect(page.get_by_text("Temporary password")).to_be_visible(timeout=10_000)
        finally:
            _delete_ephemeral_user(username)

        # Welcome email must arrive in Mailpit (creation was via UI → email IS sent).
        _latest_mailpit_email(email, "DURGAM account has been created", timeout=15)

    def test_new_user_must_change_password_on_first_login(self, page: Page) -> None:
        """Gate Step 3: new user with must_change_password=True is redirected on login."""
        username, email, _ = _create_ephemeral_user(
            must_change_password=True, role_code="STUDENT"
        )
        try:
            _login(page, username, _EPH_PASS)
            page.wait_for_url(f"{BASE_URL}/change-password", timeout=10_000)
            # rx.heading renders as heading role — use get_by_role not get_by_heading.
            expect(
                page.get_by_role("heading", name="Change password")
            ).to_be_visible(timeout=5_000)
        finally:
            _delete_ephemeral_user(username)


class TestAdminUserList:
    def test_user_appears_in_admin_list(self, page: Page) -> None:
        """Admin user list shows all active users including programmatically created ones."""
        username, email, _ = _create_ephemeral_user(role_code="STUDENT")
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/users")
            page.wait_for_load_state("networkidle")
            # Allow extra time for Reflex WebSocket state update to render the table.
            expect(page.get_by_text(username)).to_be_visible(timeout=15_000)
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

            # Form uses rx.input(name=..., placeholder=...) — use get_by_placeholder.
            page.get_by_placeholder("e.g. HOD").fill(role_code)
            page.get_by_placeholder("e.g. Head of Department").fill("Gate Test Role")
            page.get_by_placeholder("0–100 (higher = more privileged)").fill("30")
            page.get_by_role("button", name="Create role").click()
            page.wait_for_url(f"{BASE_URL}/admin/roles/**", timeout=10_000)

            # Verify we're on the role detail page.
            expect(page.get_by_text("Gate Test Role")).to_be_visible(timeout=8_000)

            # Step 7: use the permission check widget (on_submit form).
            import uuid as _uuid
            fake_scope_id = str(_uuid.uuid4())

            page.get_by_placeholder("UUID of the user").fill(user_id)
            page.get_by_placeholder("e.g. read").fill("read")
            page.get_by_placeholder("e.g. department").first.fill("department")
            page.get_by_placeholder("e.g. department (optional)").fill("department")
            page.get_by_placeholder("UUID of scoped object (optional)").fill(fake_scope_id)
            page.get_by_role("button", name="Check").click()

            # The result must be ✗ Denied (user has no department:read permission).
            expect(page.get_by_text("✗ Denied")).to_be_visible(timeout=8_000)

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


# ── Soft-delete ───────────────────────────────────────────────────────────────

class TestUserDeletion:
    def test_user_visible_in_list_before_deletion(self, page: Page) -> None:
        """User created programmatically appears in the admin user list."""
        username, email, _ = _create_ephemeral_user(role_code="STUDENT")
        try:
            _login(page, _ADMIN_USER, _ADMIN_PASS)
            page.goto(f"{BASE_URL}/admin/users")
            page.wait_for_load_state("networkidle")
            # Allow extra time for Reflex WebSocket state update.
            expect(page.get_by_text(username)).to_be_visible(timeout=15_000)
        finally:
            _delete_ephemeral_user(username)


# ── Bulk import ───────────────────────────────────────────────────────────────

class TestBulkImport:
    def test_import_page_loads_and_has_template_link(self, page: Page) -> None:
        """Verify the bulk import page is reachable and has a template download link."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin/import")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Import Users")).to_be_visible(timeout=8_000)
        expect(page.get_by_text("users_import_template.csv")).to_be_visible(timeout=5_000)


# ── Basic-user access control ─────────────────────────────────────────────────

class TestBasicUserAccessControl:
    def test_student_has_no_admin_nav_link(self, page: Page) -> None:
        """Gate Step 10: student_001 sees no Admin link in the nav."""
        _login(page, _STUDENT_USER, _STUDENT_PASS)
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        # Allow nav entries to populate (or confirm they don't for student).
        admin_links = page.get_by_role("link", name="Admin")
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
        expect(page.get_by_text("DURGAM")).to_be_visible(timeout=8_000)
        expect(page.get_by_text(_ADMIN_USER)).to_be_visible(timeout=5_000)

    def test_logout_reachable_from_admin_page(self, page: Page) -> None:
        """UX Charter §1: logout reachable without scrolling on every authenticated page."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("button", name="Log out")).to_be_visible(timeout=5_000)

    def test_admin_pages_have_footer(self, page: Page) -> None:
        """UX Charter §1: footer with institutional name on admin pages."""
        _login(page, _ADMIN_USER, _ADMIN_PASS)
        page.goto(f"{BASE_URL}/admin")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Sri Sathya Sai Institute")).to_be_visible(timeout=5_000)
