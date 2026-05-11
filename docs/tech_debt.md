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
