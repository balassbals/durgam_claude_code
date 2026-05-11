# DURGAM — University ERP for SSSIHL

**Stack**: Reflex (pure-Python) · PostgreSQL 16 (pinned) · SQLModel/SQLAlchemy 2.x · Alembic · Celery+Redis · MinIO · aiosmtplib+Mailpit · pytest+Playwright+hypothesis
**Spec**: `docs/durgam_rfp_v3.pdf` — all section references (§8, §12, etc.) point to this file.
**Python**: 3.13 (pinned via `.python-version`).
**Theme**: Puttaparthi Saffron–Indigo–Ivory (§15.1). Single committed theme; no alternatives in v3.
**Current milestone**: M1 — Authentication.

## Layering rules — strictly enforced
- **States → Services**: states orchestrate, services own the rules. States must not import SQLModel, SQLAlchemy, or any model.
- **Services → Repositories**: services never write SQL; repositories own all queries. Read-only convenience reads from a model are tolerated only inside the model's own repository.
- **Repositories → Models / Database**: only repositories may import SQLAlchemy session, `select`, etc.
- **Cross-cutting modules** (`auth`, `audit`, `notifications`, `storage`, `docgen`, `integrations`) are dependencies of services; services never reach across into another service. If two services need to coordinate, lift the coordinator into the page state or into a higher-level service.
- No layer above services may import a repository directly.

## Conventions
- Files and identifiers `snake_case`; classes `PascalCase`.
- Tables: lower_snake_case, plural (e.g. `users`, `leave_requests`). FKs: `<table_singular>_id`. Indexes: `ix_<table>_<col>`; uniques: `uq_<table>_<col>`.
- All models inherit `TimestampedSoftDelete` (id UUID v4, created_at, updated_at, created_by, updated_by, is_deleted, deleted_at, deleted_by).
- Generate migrations with: `uv run alembic revision --autogenerate -m "<verb_phrase>"`. Always review the generated diff; never blindly accept autogen.
- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- No hardcoded colours, fonts, or spacings; all design tokens via `ThemeContext` CSS variables.
- No `print()` in committed code; use `structlog`.
- No `os.environ.get(...)` outside `config.py`.
- All dependencies declared in `pyproject.toml` and locked via `uv.lock`. Never create `requirements.txt`, `requirements-dev.txt`, `Pipfile`, or `setup.py`. Install with `uv add <package>` (or `uv add --dev <package>` for dev-only). Run scripts and commands with `uv run <cmd>`, never bare `python` or `pytest`.
- Don't run `pip install` or `python -m pip` inside the repo. If a tool seems to need pip, that's a signal the tool is misconfigured — fix it via `uv` or surface it.
- **Seed data** lives in `scripts/seed.py`. Properties:
  - **Idempotent**: safe to run multiple times; uses upserts keyed on natural identifiers (codes, roll numbers, employee IDs), not auto-generated UUIDs.
  - **Synthetic only**: never hard-code real people's names, emails, phone numbers, Aadhaar, or PAN. Use Faker with a fixed seed for determinism. The University's mental-health counsellors, faculty mentors, and similarly named individuals are NOT to appear in seed data even as placeholders.
  - **Replaceable**: when sponsor data arrives, the M5 bulk-import flow loads it via the same validation path that real ongoing additions use. The seed script gets wiped and replaced; never merged.
  - **Re-runnable in CI**: every CI run starts from the seed; tests must pass against it.

## Permissions — `@require_role`
Every Reflex state event handler and every page route is decorated:
```python
@require_role(action="approve", resource="leave_request", scope="department")
async def approve_request(self, request_id: UUID): ...
```
The decorator calls `auth.permissions.can(user, action, resource, target)` and
raises `PermissionDenied` on failure. Every page additionally guards at mount
time. A handler without the decorator fails CI lint.

## Audit — `@audit_action`
Every state-changing handler is also decorated:
```python
@audit_action(action="approve", resource="leave_request")
async def approve_request(self, request_id: UUID): ...
```
The decorator records actor user/role, action, resource, resource_id, request id,
IP, user agent, and a before/after diff captured by the service. Audit rows go
to the append-only `auditlog` table; the application DB role has INSERT+SELECT only.

## Delete behaviour
- Soft delete is the default for every model. Sets `is_deleted=True`, `deleted_at=now()`, `deleted_by=actor.id`. The default repository query filter excludes soft-deleted rows.
- Hard delete is allowed only via a separate System Admin endpoint, only on rows already soft-deleted, and only after a confirmation dialog. Hard deletes are also audited.
- Every destructive action — soft delete, hard delete, cancel, withdraw, finalize — shows a confirmation dialog with the consequence in plain language ("This will withdraw your leave request. Your sanctioning authority will be notified.").

## AY immutability
- Models scoped to an academic year carry `academic_year_id`.
- A nightly job sets `academic_year.is_locked=true` on rollover.
- Repositories on AY-scoped models reject writes against locked years and raise `AcademicYearLockedError`. Services do not need to re-check; the repository is the gate.

## Testing — required for every milestone, every PR
- **Unit (`tests/unit/`)**: every service function, every rules-engine function, every validator. Fast, no I/O.
- **Integration (`tests/integration/`)**: services + real PostgreSQL container + repositories. Verifies constraints, cascades, soft-delete filtering, transaction rollback, audit-row creation.
- **E2E (`tests/e2e/`)**: Playwright scenarios for every major user journey in the milestone.
- **Property (`tests/property/`)**: hypothesis-driven tests for rule-heavy code (leave rules, permission resolution, announcement priority, attendance precedence).
- **Migrations**: forward and reverse, on a clone of the previous schema, in CI. Both must succeed.
- **Coverage thresholds**: services ≥ 85% line / 80% branch; rules engine ≥ 95% line / 90% branch; repositories ≥ 80%; UI states ≥ 70%. CI enforces; PRs that drop coverage are blocked.
- **Permission tests**: every protected handler has at least one permitted-principal test and one denied-principal test.
- **Audit tests**: every state-changing operation has a test asserting an `auditlog` row is created with the expected actor/action/resource and a non-null `diff_json`.

## Milestone discipline
- One milestone per branch, one PR per milestone.
- The PR description references the RFP milestone (e.g. "Implements §12 M8 — Leave Rules Module").
- Do not advance to the next milestone until the gate in §12 is fully passed and the administrator has signed Appendix C.
- Finishing a milestone requires updating in the same PR:
  - the **Current milestone** line at the bottom of this file,
  - `docs/modules/<module>.md` for any module touched,
  - `docs/milestones/<MN>.md` with the gate checklist as actually demonstrated.
- A version bump on Reflex, SQLModel, or any other framework dependency is itself a milestone-boundary activity; never inside an in-flight milestone.

## Known patterns and workarounds

### `_TIMESTAMPTZ` cast for SQLModel datetime columns

```python
_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))
```

**Why it exists:** SQLModel 0.0.38 stubs declare `sa_type` as `type[Any]` (a class),
but the implementation also accepts SQLAlchemy type instances such as
`sa.DateTime(timezone=True)`. Passing an instance directly causes a mypy
`[call-overload]` error. `cast(type[Any], ...)` satisfies the stub without a
`# type: ignore` comment.

**When to use it:** Any model file that defines a field with `sa_type=` pointing to an
SQLAlchemy type that requires constructor arguments. Currently used in
`durgam/models/base.py` (created_at, updated_at, deleted_at),
`durgam/models/crosscutting.py` (occurred_at, sent_at, read_at, decided_at), and
`durgam/models/identity.py` (last_login_at).
All new `datetime` fields must use `sa_type=_TIMESTAMPTZ` (not bare `DateTime`) so
psycopg3 returns timezone-aware values after `session.refresh()`.

## What NOT to do
- Don't generate UI mockups in lieu of real Reflex code.
- Don't write SQL strings inline anywhere outside Alembic migrations.
- Don't use `localStorage` / `sessionStorage` / browser cookies for **app state** — Reflex State is the source of truth. The two exceptions, both managed by the framework and not to be replicated or overridden:
  - Reflex's own session cookie for authentication.
  - Reflex's CSRF token cookie.
  Anything beyond these two is a smell; surface it before adding.
- Don't import from another service inside a service. If two services need each other, that's a design smell — surface it.
- Don't add a third-party package without justifying it in the PR; new deps cost.
- Don't skip the Mailpit / mock-data path "to save time"; both are first-class M0 deliverables.
- Don't reorder fields in an existing migration; add a new migration.
- Don't `@require_role` a handler with `'*'` to make a test pass; fix the test or the permission seed.
- Don't catch broad exceptions in services. Let them bubble; the page state turns them into user-visible errors.

## When stuck
If a question can't be answered from this file, the RFP, or the codebase, **stop and ask in the PR description** rather than guessing. Specifically:
- If the RFP is silent or contradicts itself, quote the contradicting passages and ask.
- If a permission boundary is unclear, propose a `(resource, action, scope)` triple and ask for confirmation.
- If a leave-rule edge case isn't in §11, propose a behaviour and ask before encoding.
- **Context-window discipline.** Long modules (M8 Leave Rules, M11 Faculty Research, M15 Campus) will not fit in a single session. Stop and checkpoint at the next clean boundary when ANY of the following is true:
  - The Claude Code UI shows context at or above 80%.
  - You've been working for more than ~90 minutes of session time without a commit.
  - You catch yourself summarising earlier code instead of reading it.
  - You're about to start a new sub-feature within the milestone.

  At the checkpoint: commit the current work (passing tests + green lint), update `docs/milestones/<MN>.md` with what's done and what's next in a 5-line "resume notes" block, then end the session. Resume in a new session by reading the resume notes first, then `git log -10` for context. Never `/compact` mid-milestone — it discards exactly the rules you need to keep.

## Session start checklist
At the start of every coding session, Claude Code runs:
1. `git status` — confirm clean working tree.
2. `cat CLAUDE.md | grep "Current milestone"` — confirm what's in flight.
3. `uv run pytest --collect-only -q | tail -5` — confirm tests are discoverable and the suite isn't broken.
4. Read the RFP section for the current milestone (§12 entry for the milestone in flight).

If any of the above fails or surprises, stop and surface it before writing code.

## Current milestone
**M1 — Authentication.**

This line is the source of truth for "where are we." Before opening a milestone-completing PR, Claude Code MUST:
1. Grep this file for "Current milestone" and update both occurrences (the top status line and this section).
2. Verify the update is part of the same commit as the gate-passing work — never a separate PR.
3. Confirm the update matches the milestone numbering in §12 of the RFP, not a guess.

See **Milestone discipline** above for the full closing checklist.