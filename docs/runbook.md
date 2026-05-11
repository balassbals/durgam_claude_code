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
