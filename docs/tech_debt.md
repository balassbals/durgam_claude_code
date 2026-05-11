# Tech Debt Log

## Active

### TD-002 — SAWarning: transaction already deassociated from connection

**Location:** `tests/conftest.py:66` (`transaction.rollback()` in `db_session` fixture)

**Full warning text:**
```
SAWarning: transaction already deassociated from connection
```

**Code path that produces it:**
The `db_session` fixture wraps each test in an explicit SQLAlchemy transaction
(`connection.begin()` → `Session(bind=connection)`). When a test uses
`pytest.raises(sa.exc.IntegrityError)` and calls `db_session.flush()`, SQLAlchemy
internally marks the connection's transaction as rolled-back the moment the
`IntegrityError` propagates (it calls `connection._handle_dbapi_exception`). The
transaction object is now "deassociated" — it no longer controls the connection.
When fixture teardown then calls `transaction.rollback()` on line 66, SQLAlchemy
warns because `transaction` is already dead.

Affected tests (all four intentionally raise `IntegrityError`):
- `TestIdentityModels::test_role_unique_code_enforced`
- `TestConfigAnchorModels::test_academic_year_unique_code`
- `TestConfigAnchorModels::test_holiday_unique_date_per_ay`
- `TestConfigAnchorModels::test_student_category_count_unique_per_ay`

**Why this is not a production issue:** `BaseRepository` never wraps calls in a
shared test-style connection/transaction pair. In production, `IntegrityError` bubbles
out of the repository, rolls back the ORM session automatically, and is handled by the
page state as a user-visible error. The test-only pattern (bind a `Session` to a
pre-begun `Connection`) is the source of the mismatch, not the repository logic.

**Reproduces under `-W error`?** Yes. Running `pytest -W error` without a
`filterwarnings` exception for `SAWarning` would turn these four warnings into errors
and fail the integration tests. The fix is to wrap `transaction.rollback()` in a
try/except in the `db_session` and `seeded_session` fixtures, or to use SQLAlchemy's
`begin_nested` pattern instead. Deferred to M1; does not affect production behaviour.

---

## Resolved

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
