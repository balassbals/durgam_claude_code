# Auth Module — Architecture Reference (M1)

**RFP:** §9.1  
**Milestone:** M1 — Authentication  
**Status:** Implementation complete; E2E gate pending live-app run.

---

## Entities

| Entity | Table | Purpose |
|---|---|---|
| `User` | `users` | Identity, credentials, lockout state, must_change_password flag |
| `UserSession` | `user_sessions` | Authoritative server-side session record; opaque token (SHA-256 stored) |
| `PasswordResetToken` | `password_reset_tokens` | One-time, 30-minute expiry token for password reset flow |

---

## Session Storage Model (SD-001)

Reflex 0.9.2 stores its CLIENT_TOKEN in `window.sessionStorage` (not an HTTP cookie). The
`rx.Cookie()` API, which sets cookies via JavaScript, cannot produce an `HttpOnly` cookie.

**Path A chosen:** An opaque UUID v4 session token (distinct from user_id) is stored in:
- **Browser:** `rx.Cookie(name="dsession", same_site="lax", secure=True, max_age=604800)`
- **Database:** `user_sessions.token_hash` (SHA-256 of the raw token; token never stored in plain)

Server-side invalidation (logout, admin force-logout, idle expiry enforcement) always wins.

**HttpOnly gap:** Documented in `docs/tech_debt.md → TD-005` and
`docs/security_decisions.md → SD-001`. Compensating controls: opaque token, SameSite=Lax,
React XSS escaping, CLAUDE.md `rx.html()` prohibition.

**7-day sliding expiry:** `UserSession.last_active_at` and `expires_at` are updated on every
`AuthService.resolve_session()` call. The cookie's `max_age` is refreshed via
`BaseState.session_token` assignment on each authenticated page load.

---

## Decorator Contract (M1 Change from M0)

The M0 `@require_role` read `user_id` from `kwargs["user_id"]`. That pattern is **replaced**.

**M1 contract:**
- `@require_role(action, resource, scope)` — reads `args[0].current_user_id` (Reflex State).
  Raises `PermissionDenied` if the user is unauthenticated or the permission check fails.
  Opens its own database session from a module-level engine (`durgam/auth/decorators.py`).
- `@public_handler` — marks handlers that are intentionally unauthenticated (login,
  forgot_password, reset_password). Does not check current_user_id.
- `@audit_action(action, resource)` — records an AuditLog row after success. Required for
  ALL state-changing handlers. Reads actor context from the State (`current_user_id`,
  `current_role_code`, `client_ip`, `client_user_agent`, `request_id`).

**Rule (enforced by CI lint):**
> Every Reflex State event handler must wear EITHER `@require_role` OR `@public_handler`,
> PLUS `@audit_action`. No handler may be undecorated.

**Unit test contract:** Tests in `tests/unit/test_auth.py` construct a `MagicMock()` with
`current_user_id = str(uuid4())` as `args[0]` — NOT the old kwargs pattern. The M0
backward-compat kwarg pattern is removed by design.

---

## Layering

```
AuthState (durgam/states/auth.py)
  ↓ calls services via durgam/db.open_session()
AuthService / PasswordService (durgam/services/auth.py)
  ↓ calls repositories
UserRepository / UserSessionRepository / PasswordResetTokenRepository
(durgam/repositories/)
  ↓ SQL queries against
users / user_sessions / password_reset_tokens
```

**States must not import SQLModel, SQLAlchemy, or any model** (CLAUDE.md rule).
Database sessions are obtained exclusively via `durgam.db.open_session()`.

The decorators open their own sessions via `durgam/auth/decorators.py:_db_session()`.

---

## Rate Limiting and Lockout

Configured via `Settings` in `durgam/config.py` (overridable via env vars):

| Setting | Default | Meaning |
|---|---|---|
| `AUTH_USER_FAILURE_THRESHOLD` | 5 | Failed attempts before user lockout |
| `AUTH_USER_LOCKOUT_MINUTES` | 15 | Lockout duration |
| `AUTH_IP_THROTTLE_LIMIT` | 20 | Failed attempts per IP per window |
| `AUTH_IP_THROTTLE_WINDOW_MINUTES` | 15 | IP throttle window |

Rate limiting uses Redis (`durgam/auth/rate_limit.py`). Lockout state is persisted in
`users.locked_until` (timestamp). Per-user lockout survives Redis restarts; per-IP
rate limits do not (by design — IP bans are transient).

---

## Password Policy (§6.1)

Enforced by `durgam/services/password.py → validate_policy()`:
- Minimum 12 characters.
- At least one uppercase, one lowercase, one digit, one symbol.
- Not in top-10,000 common passwords (`scripts/data/common_passwords.txt`).
- Must not contain the user's email local-part or full name (case-insensitive substring).

Hashing: `bcrypt(cost=12)`. Verification: constant-time via `bcrypt.checkpw()`.

---

## Seed Credentials (dev/CI only)

| Username | Password | Role | Active |
|---|---|---|---|
| `sys_admin` | `SysAdmin_Dev1!XZ` | SYSTEM_ADMIN | Yes |
| `dean_sci` | `DeanSci_Dev1!XZ` | DEAN | Yes |
| `student_001` | `Student_Dev1!XZ` | STUDENT | Yes |
| `inactive_user` | `Inactive_Dev1!XZ` | STUDENT | No |

The inactive user is added at M1 for E2E lockout and inactive-user-rejection testing.

---

## Security Decisions Index

See `docs/security_decisions.md` for:
- **SD-001:** Session storage model (rx.Cookie, HttpOnly gap, Path B availability)
- **SD-002:** Reflex framework retained despite §6.1 cookie-model mismatch
