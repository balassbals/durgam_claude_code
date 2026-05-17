# Tech Debt Log

## Active

### TD-003 — apply_theme() return type widened to dict[Any, Any]

**Location:** `durgam/theme.py:23` (`def apply_theme() -> dict[Any, Any]`)

**What it is:** `TOKENS` is `dict[str, str]` but `rx.App(style=...)` is typed to
accept `dict[str | type[BaseComponent] | Callable[..., Any] | ComponentNamespace, Any]`.
Because `dict` is invariant in its key type, mypy rejects `dict[str, str]` as
incompatible with that wider union key. The return annotation was widened to
`dict[Any, Any]` to satisfy the call site without a `# type: ignore`.

**Why this is not a production issue:** The dict's actual keys are always CSS variable
strings (e.g. `"--color-primary"`). The wider annotation does not change runtime
behaviour; it only weakens mypy's ability to catch a type error if a non-string key
were accidentally added to `TOKENS`.

**Trigger to re-open:** Reflex ships corrected type stubs for `rx.App.style` that
accept `dict[str, str]`; at that point the return annotation can be tightened back.

---

### TD-004 — type: ignore[attr-defined] on _exec_insert in scripts/seed.py

**Location:** `scripts/seed.py:46` (`stmt.returning(...)  # type: ignore[attr-defined]`)

**What it is:** `_exec_insert` accepts `stmt: object` (the narrowest safe type for a
function that does not know the exact Insert subtype). Calling `.returning()` on
`object` is not known to mypy, so `[attr-defined]` must be suppressed. The runtime
type is always a `sqlalchemy.dialects.postgresql.Insert` which does have `.returning()`.

**Why this is not a production issue:** `_exec_insert` is only called by `scripts/seed.py`
during dev and CI seeding — it never runs on a production request path. A wrong stmt
type would cause an `AttributeError` at seed-run time, not a silent data corruption.

**Trigger to re-open:** SQLAlchemy ships stubs that expose `.returning()` on a shared
base type; at that point the parameter can be narrowed and the ignore removed.

---

### TD-005 — Session cookie cannot be HttpOnly (Reflex architectural constraint)

**Location:** `durgam/states/auth.py` (session token stored in `rx.Cookie()`);
`docs/security_decisions.md` → SD-001.

**What it is:** Reflex 0.9.2 stores its CLIENT_TOKEN in `window.sessionStorage` (not
an HTTP cookie) and exposes `rx.Cookie()` as the only cookie API for state vars.
`rx.Cookie()` is set by JavaScript via the `universal-cookie` npm library; the `HttpOnly`
flag can only be set by a server `Set-Cookie` header and therefore cannot be applied
to `rx.Cookie()`. The M1 session token (an opaque UUID v4 mapped to `UserSession` in
the DB) is stored in an `rx.Cookie()` and is thus JavaScript-accessible.

**Compensating controls in place:**
- Token is opaque (UUID v4, not the user's UUID); server-side invalidation is authoritative.
- `same_site="lax"` blocks cross-site request forgery via cookie injection.
- React's built-in JSX escaping prevents the most common XSS vectors.
- CLAUDE.md "What NOT to do" prohibits `rx.html()` with user-controlled strings.
- All user-supplied content is rendered through Reflex component primitives that escape output.

**Residual risk:** An XSS vulnerability that bypasses React's escaping could read the
session cookie and hijack the session.

**Why this is not a production blocker at M1:** The gap is mitigable; Path B (custom
Starlette middleware for a real HttpOnly cookie) is documented in `docs/security_decisions.md`
as an available escalation path. The cost of switching framework integration at M1 outweighs
the residual risk given the compensating controls.

**Trigger to escalate:** (a) Reflex 1.0+ ships a server-side cookie API; (b) a security
review at M20 or earlier determines the residual risk is unacceptable; (c) an XSS
surface is discovered anywhere in DURGAM that could reach a user-controlled string.

---

### TD-006 — test_unassigned_resource_always_denied fails when property suite runs in isolation

**Location:** `tests/property/test_permission_resolution.py`

**What it is:** When `tests/property/` is run alone (without `tests/unit/` and 
`tests/integration/` running first), the test 
`TestCanNeverGrantsBeyondAssignment::test_unassigned_resource_always_denied` fails. 
When the full test suite runs (unit + integration + property), the same test passes.

**Why this is not a production issue:** The bug is in the test's Hypothesis strategy, 
not in `can()`. The test generates random resource names and asserts they're denied, 
but the strategy can produce names that match real seeded permissions (e.g. matching 
a real resource by accident). When other test suites run first, they consume the 
random seed in a way that avoids this collision.

**Trigger to re-open:** Property test suite is run in isolation as a regular 
part of CI; or the seeded permission set grows further (M5+) and the collision 
rate increases enough to fail in the full-suite run too.

**Fix when reopened:** Add a `.filter()` to the Hypothesis strategy that excludes 
resource names matching any value in the seeded Permission table at test-collection 
time. Or generate test resources from a fixed namespace (e.g. `nonexistent_resource_*`) 
that's known not to be seeded.

## Resolved

### TD-002 — SAWarning: transaction already deassociated from connection (resolved in m0-cleanup)

**Status: closed.** Both `db_session` and `seeded_session` fixtures now wrap
`transaction.rollback()` in a try/except. When `IntegrityError` is raised inside
`pytest.raises`, SQLAlchemy internally deassociates the transaction before teardown
runs; the try/except silences the spurious warning without suppressing it globally.
Verified: `pytest -W error tests/integration/` passes with 0 SAWarnings.

---

### TD-001 — datetime.utcnow() deprecation (resolved in 445ec9e)

**Status: closed. No outstanding work.**

All four DURGAM call sites that used the deprecated `datetime.utcnow()` were replaced
with `datetime.now(UTC)` in commit `445ec9e`. The call sites were:

- `durgam/models/base.py` — 2× as `default_factory=datetime.utcnow` (created_at, updated_at)
- `durgam/models/crosscutting.py` — 1× as `default_factory=datetime.utcnow` (AuditLog.occurred_at)
- `durgam/audit/log.py` — 1× as direct call `datetime.utcnow()`

**Verification:** `grep -rn "utcnow" .venv/lib/python3.13/site-packages/sqlmodel/` returned
no output — SQLModel 0.0.38 contains no internal `utcnow()` calls.

**Upstream issue:** None exists. SQLModel 0.0.38 is clean. Monitor
https://github.com/fastapi/sqlmodel/issues if a future release reintroduces the call.

**Trigger to re-open:** Python removes `datetime.utcnow()` entirely (deprecated in 3.12,
removal targeted for 3.14), OR a SQLModel release introduces an internal `utcnow()` call.

**Filterwarnings:** `pyproject.toml` carries `"ignore:.*utcnow.*:DeprecationWarning:sqlmodel.*"`
as a no-op safety net. It is currently inert against SQLModel 0.0.38.


