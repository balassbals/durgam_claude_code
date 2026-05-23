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

### TD-008 — Shared test database allows cross-engine fixture contamination

**Location:** `tests/conftest.py` (`db_engine`, `seeded_db_engine` fixtures);
`tests/integration/test_org_core.py` (the two VM tests with the
`_clean_university_vm` workaround).

**What it is:** `db_engine` and `seeded_db_engine` both target
`settings.test_database_url` — the same physical database. When a test
using `seeded_session` runs (triggering `seed()` with a commit), the
committed seed data becomes visible to subsequent tests using
`db_session`, because `db_session`'s `transaction.rollback()` only undoes its
own writes, not data committed by the other engine. Test execution order
determines whether the contamination manifests. At M3 close-out the
order was benign; M4 Session 1's changes shifted the order and exposed
two vision/mission tests that assume empty `university_vision_missions`
and `university_missions` tables.

**Current workaround:** `_clean_university_vm()` deletes the leaked rows at
the start of the two affected tests, inside their rolled-back
transaction. Safe but symptom-level.

**Why this is not a production issue:** It is purely a test-infrastructure
isolation problem. Production code is unaffected — the vision/mission
behavior is correct (verified: edit persists in manual UI testing).

**Trigger to re-open / proper fix:** When a third test hits this class of
bug, or proactively at the next test-infrastructure pass. Proper fix
options: (a) `seeded_db_engine` uses an isolated schema or separate
database from `db_engine`; (b) the seeded fixture cleans up its committed
data in teardown; (c) all integration tests that assume empty tables
explicitly clean those tables at setup (generalize the
`_clean_university_vm` pattern into a reusable fixture).

---

### TD-007 — Mobile and tablet responsiveness deferred across modules

**Location:** Every admin and config page (multiple files in `durgam/pages/`).

**What it is:** The two-tier responsive table component code exists
(`durgam/pages/shared/data_table.py`) and is wired into all list pages.
However, actual rendering at 360px and 768px viewports has not been verified
or tuned. At 360px, tables don't consistently convert to cards. At 768px,
the navbar layout cramps. Forms reflow acceptably but not gracefully.

**Why this is not a production issue at M3:** All M3 admin and config
workflows are used by university administrators (Registrar, HoDs, sys_admin)
who work primarily at desktop. Students who reach the read-only `/about`
pages can read them on any device, though formatting is not ideal on mobile.

**Compensating decision:** Three-width responsiveness checks have been removed
from the M3+ gate verification ritual (see `docs/prompts/gate_verification.md`
Step 5). The UI Polish milestone (scheduled before M20) will conduct dedicated
mobile and tablet polish across all modules accumulated through M19.

**Trigger to re-open:** (a) Mobile usage by faculty becomes an operational need
(e.g., approving leave requests on phone); (b) university mandates an
accessibility audit; (c) UI Polish milestone arrives per project plan.

---

### TD-009 — Seed data uses institution-specific names and codes

**Location:** `scripts/seed.py`

**What it is:** `scripts/seed.py` uses names close to SSSIHL's real
structure (campus codes PSN/BRN/NDG/ATP, school/department names,
role names). This is intentional for making gate demonstrations
realistic and for testing multi-campus logic. However it implies a
specific institution.

**Why this is not a development issue:** Seed is a development/demo
artifact only — it is never run in production. At deployment, the
institution configures real data through admin UIs. The seed is
discarded or kept only for CI/test environments.

**Trigger to re-open:** (a) The codebase is open-sourced or shared
outside the development team — at that point, seed should be
anonymised or replaced with fully fictional data. (b) M20 (final
milestone) review — confirm seed is clearly labelled as demo-only
before any external handoff.

---

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


