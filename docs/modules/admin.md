# Admin Module

**RFP reference:** §9.2  
**Milestone:** M2  
**Gate clause:** "System Admin can construct any role and verify scoped permissions."

---

## Overview

The Admin module provides `sys_admin` with user management, role management, permission
visibility, bulk CSV import, and password management. It is the first module with real
navigation entries, establishing several patterns inherited by all subsequent modules.

---

## Routes

| Route | Page | State | On-load handler |
|---|---|---|---|
| `/admin` | admin_index | AdminIndexState | `load_stats` |
| `/admin/users` | admin_users | AdminUsersState | `load_users` |
| `/admin/users/new` | admin_user_create | AdminUsersState | `load_available_roles` |
| `/admin/roles` | admin_roles | AdminRolesState | `load_roles` |
| `/admin/roles/new` | admin_role_create | AdminRolesState | `load_roles` |
| `/admin/roles/{role_id}` | admin_role_detail | AdminRolesState | `load_role_detail` |
| `/admin/permissions` | admin_permissions | AdminPermissionsState | `load_permissions` |
| `/admin/import` | admin_import_users | BulkImportState | `reset_import` |

---

## Permission requirements

| Action | Required permission |
|---|---|
| View /admin, /admin/users, /admin/users/new | `user:read:*` |
| Create/edit/delete users | `user:write:*` |
| Hard-delete users | `user:delete:*` |
| View roles | `role:read:*` |
| Create/edit/delete roles | `role:write:*` |
| View permissions | `permission:read:*` |
| Bulk import | `user:write:*` |

All admin handlers use `@require_role` + `@audit_action` decorators.

---

## User CRUD

### Create

`AdminUsersState.create_user()` is a **non-trivial handler** (form validation + service
call + temp password display + email). It:
1. Validates username and email are non-empty and unique.
2. Calls `UserAdminService.create_user()` which generates a 16-char temp password.
3. Sets `must_change_password=True` on the new user.
4. Displays the temp password exactly once in the UI (dismiss button).
5. Sends `send_user_created_email()` with the temp password.

### Delete policy

**Soft-delete:** sets `is_deleted=True`, emails the user, excludes from list views.

**Hard-delete:** permanently removes the user row. Blocked by `HardDeleteBlockedError`
if any auditlog rows reference this user (the auditlog is INSERT+SELECT only — actor
references cannot be nulled). The user must be soft-deleted first.

Hard delete is only available on already-soft-deleted users via a "Permanently delete"
button on the user detail page, with a stronger confirmation dialog.

### Password reset

`AdminUsersState.reset_user_password()` generates a new temp password, sets
`must_change_password=True`, emails the user. The temp password is shown once in
the admin UI.

---

## Role CRUD and permission assignment

`AdminRolesState.create_role()` creates a role with code, name, level, and description.
`AdminRolesState.save_role_permissions()` calls `RoleAdminService.update_permissions()`
which atomically replaces the role's permission set (deletes existing `RolePermission`
rows and inserts the new set).

The role detail page embeds a **resource-first permission accordion**: resources listed
as collapsible sections; each section shows actions with scope checkboxes. Only seeded
(resource, action, scope) triples are shown.

---

## Permission policy: seed-only

Permissions are defined exclusively in `scripts/seed.py`. The `/admin/permissions` page
is a read-only listing. No create form exists. Future milestones extend the seed when
they introduce new resources. See CLAUDE.md "Patterns established at M2."

---

## Bulk import

Two-stage flow per §16:
1. **Upload:** `rx.upload` accepts a CSV file.
2. **Validate:** `BulkImportService.validate_user_csv()` checks schema, role codes,
   duplicate detection (within file and against existing DB). Shows preview table with
   ✓/✗ status per row.
3. **Commit:** `BulkImportService.commit_user_import()` commits valid rows individually
   (partial success — errors do not block valid rows). Downloads error-report CSV.

CSV schema: `username,email,role_code` (required), `full_name` (optional).

---

## Navigation registration

```python
# durgam/pages/admin/__init__.py
from durgam.nav.registry import NavEntry, register

register(NavEntry(label="Admin", href="/admin", ..., permission_action="read", permission_resource="user"))
register(NavEntry(label="Users", href="/admin/users", ..., permission_action="read", permission_resource="user"))
# etc.
```

`BaseState._load_nav_entries()` calls `can()` for each entry and caches
`visible_nav_entries` in state at login time. The nav shell reads this cache — no DB
calls at render time.

---

## Permission check widget

`durgam/pages/shared/permission_check_widget.py` provides a form on role detail and
user detail pages. Inputs: user UUID, action, resource, scope_type, scope_id. Calls
`can()` live and shows ✓ Granted / ✗ Denied inline. Used for the M2 gate Step 7
demonstration.

---

## Known gotcha: can() scope_id discrimination

`can()` was fixed at M2 to correctly deny when `scope_id=None` is passed to the check
but the `UserRole` has a specific `scope_id`. Before the fix, a user scoped to
department X incorrectly returned `True` for `can(..., scope_id=None)`.

See `tests/unit/test_permissions.py` for the five discrimination cases.
