import reflex as rx

from durgam.config import settings
from durgam.logging import configure_logging
from durgam.pages.admin import index as _admin_nav_register  # noqa: F401 — registers nav entries
from durgam.pages.admin.import_users import admin_import_users
from durgam.pages.admin.index import admin_index
from durgam.pages.admin.permissions import AdminPermissionsState, admin_permissions
from durgam.pages.admin.roles import admin_role_create, admin_role_detail, admin_roles
from durgam.pages.admin.user_detail import admin_user_create
from durgam.pages.admin.users import admin_users
from durgam.pages.audit.index import AuditLogState, audit_log
from durgam.pages.change_password import change_password
from durgam.pages.forgot_password import forgot_password
from durgam.pages.index import index
from durgam.pages.login import login
from durgam.pages.reset_password import reset_password
from durgam.pages.shared.permission_check_widget import PermissionCheckState
from durgam.states.admin_bulk_import import BulkImportState
from durgam.states.admin_index import AdminIndexState
from durgam.states.admin_roles import AdminRolesState
from durgam.states.admin_users import AdminUsersState
from durgam.states.auth import AuthState
from durgam.theme import apply_theme

configure_logging(debug=settings.debug)

app = rx.App(style=apply_theme())
app.add_page(
    index,
    route="/",
    # Single handler: resolve session + redirect unauthenticated to /login
    # + redirect must_change_password to /change-password. Merged into one
    # method to avoid Reflex 0.9.x multi-event sequencing issues.
    on_load=AuthState.home_on_load,
)
app.add_page(
    login,
    route="/login",
    # Resolve session only — no redirect (login page is accessible unauthenticated)
    on_load=AuthState.resolve_session,
)
app.add_page(forgot_password, route="/forgot-password")
app.add_page(
    reset_password,
    route="/reset-password",
    on_load=[AuthState.resolve_session, AuthState.load_reset_token],
)
app.add_page(
    change_password,
    route="/change-password",
    # Resolve session + redirect unauthenticated to /login (no must_change loop)
    on_load=AuthState.change_password_on_load,
)

# ── M2 Admin routes ────────────────────────────────────────────────────────────
app.add_page(admin_index, route="/admin", on_load=AdminIndexState.load_stats)
app.add_page(admin_users, route="/admin/users", on_load=AdminUsersState.load_users)
app.add_page(admin_user_create, route="/admin/users/new",
             on_load=[AdminUsersState.load_available_roles, PermissionCheckState.clear_widget])
app.add_page(admin_roles, route="/admin/roles", on_load=AdminRolesState.load_roles)
app.add_page(admin_role_create, route="/admin/roles/new",
             on_load=AdminRolesState.load_roles)
app.add_page(admin_role_detail, route="/admin/roles/[role_id]",
             on_load=[AdminRolesState.load_role_detail, PermissionCheckState.clear_widget])
app.add_page(admin_permissions, route="/admin/permissions",
             on_load=AdminPermissionsState.load_permissions)
app.add_page(admin_import_users, route="/admin/import",
             on_load=BulkImportState.reset_import)
app.add_page(audit_log, route="/audit", on_load=AuditLogState.load_audit)
