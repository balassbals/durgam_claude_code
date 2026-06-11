# Developer Runbook — DURGAM

## Prerequisites

- Docker (with Compose v2)
- [uv](https://docs.astral.sh/uv/) ≥ 0.5
- Python 3.13 (managed by uv via `.python-version`)

## Local dev setup

```bash
git clone <repo> durgam && cd durgam

# Install all deps (creates .venv)
uv sync

# Copy env template
cp .env.example .env
# .env has safe dev defaults — no changes needed for local dev
```

## Start dev services

```bash
# Start all infrastructure (postgres, redis, mailpit, minio)
docker compose up db redis mailpit minio -d

# Verify postgres is healthy
docker compose exec db pg_isready -U durgam

# Apply schema
uv run alembic upgrade head

# Load seed data
uv run python scripts/seed.py

# Start Reflex dev server
uv run reflex run
# App available at http://localhost:3000
# Mailpit web UI at http://localhost:8025
# MinIO console at http://localhost:9001 (admin / minioadmin)
```

## Running tests

### Unit tests (no Postgres required)

```bash
uv run pytest tests/unit/ -v
```

### Integration tests (require Postgres)

Integration tests use `TEST_DATABASE_URL` which defaults to `durgam_test`.
The conftest creates `durgam_test` automatically if it doesn't exist, then
creates all tables at session start and drops them at session end.
The only prerequisite is that the `db` service is running.

```bash
# Make sure docker compose db is running
docker compose up db -d

# Run integration tests
uv run pytest tests/integration/ -v
```

### All tests with coverage

```bash
uv run pytest tests/unit/ tests/integration/ --cov=durgam --cov-report=html
```

### E2E tests (require running app)

```bash
# Start the full stack
docker compose up -d
uv run reflex run &

# Wait for app to be ready, then:
BASE_URL=http://localhost:3000 uv run pytest tests/e2e/ -v
```

## Database operations

```bash
# Check current migration state
uv run alembic current

# Generate a new migration after model changes
uv run alembic revision --autogenerate -m "describe_the_change"
# REVIEW the generated file before applying!

# Apply migrations
uv run alembic upgrade head

# Roll back one step
uv run alembic downgrade -1

# Roll back to empty schema
uv run alembic downgrade base
```

## Code quality

```bash
# Lint and auto-fix
uv run ruff check . --fix

# Format
uv run ruff format .

# Type check
uv run mypy durgam/

# Pre-commit (runs automatically on git commit after install)
uv run pre-commit install
uv run pre-commit run --all-files
```

## CI notes

CI runs on GitHub Actions. The `ci.yml` workflow has six jobs:
1. **lint** — ruff check + ruff format --check
2. **type-check** — mypy durgam/
3. **test-unit** — pytest tests/unit/
4. **test-integration** — pytest tests/integration/ against a postgres:16 service
5. **migration-check** — upgrade head → downgrade -1 → upgrade head
6. **docker-build** — docker build --target app

All jobs must pass before merging to main.

## Seed data users (M0)

| Username | Email | Role | Dev password |
|----------|-------|------|-------------|
| sys_admin | sys.admin@sssihl.edu.in | SYSTEM_ADMIN | sys_admin_dev |
| dean_sci | dean.sci@sssihl.edu.in | DEAN | dean_sci_dev |
| student_001 | student.001@sssihl.edu.in | STUDENT | student_001_dev |

Password hashes use a dev-only SHA-256 scheme — never use in production.

## M8 Leave Rules — operations

### Celery beat entries (leave jobs)

The following tasks are registered in `durgam/tasks/leave_jobs.py` and scheduled in `durgam/tasks/celery_app.py`:

| Task | Schedule | Description |
|------|----------|-------------|
| `leave-forfeit-late-cl` | Nightly 00:30 UTC | Forfeits a CL for each employee who has a LateAttendanceMarker this month and hasn't already had a CL deducted. |
| `leave-lapse-unavailed-cl` | Dec 31 23:00 UTC | Lapses unused CL at year end — sets closing_balance = 0 (CL doesn't carry forward). |
| `leave-credit-el-hpl-jan` | Jan 1 02:00 UTC | Credits half-yearly EL and HPL for eligible employees (≥6 months service). |
| `leave-credit-el-hpl-jul` | Jul 1 02:00 UTC | Same as above for the July half-year credit. |
| `leave-check-overstay` | Nightly 01:00 UTC | Marks leave requests as overstayed when the end date has passed and they remain in-flight; sends notification to HR. |

### Known gaps at M8 close

- **TD-036**: CL annual credit at AY start is NOT scheduled. Until E-016 (legacy balance import) lands, leave balances must be seeded manually at go-live via direct SQL or a one-off import script.
- **TD-037**: Notification rows for leave events appear to not be enqueued (0 rows in `notifications` table after full gate walkthrough including submit → approve → balance debit). Investigate before TD-032 (dispatch worker) becomes meaningful. See `docs/tech_debt.md` → TD-037.

### Leave sanction matrix seed

73 rules are loaded from `seeds/leave_sanction_matrix.yaml` by `uv run python scripts/seed.py`. The seed is idempotent — re-running upserts by (applicant_role_code, leave_type, scope_type, priority) natural key and soft-deletes orphaned rows. If the YAML is edited, re-run the seed; no migration is needed unless the schema changes.

### vc_user (seeded demo user)

The M8 seed adds `vc_user / ViceChancellor_Dev1!XZ` with the VC role. This user is the final-stage approver for SCL walkthroughs (FACULTY → DIRECTOR-recommend → VC-final channel). It is a read-only seeded fixture — do not use it in tests that mutate state.

---

## M8.1 — Leave Module Follow-ups

### Annual CL credit job (`credit_annual_cl`)

**Schedule:** `0 3 1 1 *` (Jan 1, 03:00 UTC). Registered in `durgam/tasks/celery_app.py` as `leave-credit-annual-cl`.

**What it does:** For each active employee, looks up their `LeaveCreditPolicy` row for leave_type `"CL"`, computes entitlement (prorated for employees who joined in the current calendar year; full entitlement for all others), creates a `leave_credit_runs` row (idempotent — skips if row already exists for that user + year), and upserts `LeaveBalance.credited`.

**Manual run:**
```bash
uv run celery -A durgam.tasks.celery_app call durgam.tasks.leave_jobs.credit_annual_cl
```
Or with a specific reference date (for testing):
```bash
uv run celery -A durgam.tasks.celery_app call durgam.tasks.leave_jobs.credit_annual_cl --args='["2026-01-01"]'
```

**Known gaps:** Schedule hardcoded in celery_app.py (→ TD-040). AY-locked employees raise `AcademicYearLockedError` — task logs and skips; does not abort the run.

---

### Balance import operations (`/admin/leave/balance-import`)

**Purpose:** Bootstrap existing employees' accumulated balances at go-live (E-016).

**Roles with access:** SYSTEM_ADMIN, REGISTRAR, DEPUTY_REGISTRAR, REGISTRAR_OFFICE, DIRECTOR, DEPUTY_DIRECTOR, DIRECTOR_OFFICE.

**Two-stage flow:**
1. Upload CSV → preview screen shows resolved AY name, valid rows, invalid rows (unknown username / negative balance / bad leave_type). Commit button disabled if any invalid rows.
2. Commit → one `LeaveBalance` upsert per valid row (overwriting all 5 balance fields). One audit row per upserted row.

**CSV format (7 columns):**
```
employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed
```
`closing_balance` is recomputed server-side. Sample fixture: `tests/fixtures/leave_balance_import_sample.csv`.

**Idempotency:** Re-importing the same CSV writes audit rows showing no diff (values unchanged). Re-importing with updated values overwrites and writes a diff audit row.

**Per-employee form:** Below the CSV section; same upsert path; useful for individual corrections post-go-live.

---

### Balance edit operations (`/admin/leave/balance-edit`)

**Purpose:** Correct individual balance rows after go-live (E-022).

**Editable fields:** `opening_balance`, `credited`, `availed`, `forfeited`, `encashed`. `closing_balance` recomputed and displayed read-only.

**Audit:** Every save writes an auditlog row with `before`/`after` diff.

**Known gap:** Sticky first-column scroll not working (UI-POLISH-M8.1-01). Functional behaviour unaffected.

---

### Request edit operations (`/admin/leave/request-edit`)

**Purpose:** Correct leave request states and related data (E-022).

**Allowed transitions:**

| Current state | Allowed new states |
|---------------|--------------------|
| `submitted`   | `cancelled`, `rejected` |
| `in_review`   | `cancelled`, `rejected` |
| `approved`    | `cancelled`, `withdrawn` (only if `today ≤ ends_on`) |

`approved → cancelled` and `approved → withdrawn` both delegate to `LeaveRequestService.withdraw()` which triggers the E-017 balance reversal path.

**Window-elapsed guard:** For approved leaves where `ends_on < today`, the New State dropdown is disabled and an amber informational banner explains the constraint. Use `/admin/leave/balance-edit` for balance corrections in this case.

**Note on `approved → rejected`:** Explicitly forbidden (DD-M8.1-P8-5). If an approved leave needs to be undone, use `approved → cancelled`.

---

### Post-facto leave applications

Faculty can apply with `starts_on` in the past. An amber "Post-facto application" badge appears on the Apply modal. `is_post_facto = True` is set at submit time and never changes.

On approval, if `is_post_facto = True` and `leave_type == "CL"`, any CL forfeitures in months covered by the leave period are automatically reversed (one per month with a `LateAttendanceMarker`). This is idempotent.

---

### Withdraw approved leave

Faculty can withdraw their own approved leave from `/leave` while `today ≤ ends_on`. A "Withdraw (post-approval)" action is shown on in-flight rows with `state == "approved"`.

**Requirements:** Reason ≥ 10 characters required. Modal shows confirmation.

**Balance:** `LeaveBalance.availed` decremented by unused tail (formula: `sanctioned_days × max(0, (ends_on − max(starts_on, today)).days + 1) / chargeable_days`). For CML: HPL re-credited at 2×. SCL/EOL/SL: no balance change.

**Notifications:** Fan-out to HOD → AHOD fallback → DIRECTOR + DIRECTOR_OFFICE. Campus-dept scope deferred (TD-038).

---

### Known limitation — TD-034

Full-suite `pytest` invocations (bare or `tests/unit/ tests/integration/`) produce 56 false failures in `tests/integration/test_m5b_purchase_rules.py` due to `seeded_session`/`db_session` fixture-pool interaction. This is pre-existing since M8. Gate ritual uses scoped invocations only. See `docs/prompts/gate_verification.md` → M8.1 lessons for the workaround.
