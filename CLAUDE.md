# DURGAM — University ERP for SSSIHL

**Stack**: Reflex (pure-Python) · PostgreSQL 16 (pinned) · SQLModel/SQLAlchemy 2.x · Alembic · Celery+Redis · MinIO · aiosmtplib+Mailpit · pytest+Playwright+hypothesis
**Spec**: `docs/durgam_rfp_v3.pdf` — all section references (§8, §12, etc.) point to this file.
**Python**: 3.13 (pinned via `.python-version`).
**Theme**: Puttaparthi Saffron–Indigo–Ivory (§15.1). Single committed theme; no alternatives in v3.
**Current milestone**: M10 (Faculty Module) — in progress. M9 closed 2026-06-14, merged as 2d819c4, tag m9-close. M10 branch: m10-faculty. Phase P1 shipped (`27d323a`) + P1.1 fix (`f2b671b`) + P2 photo upload (TBD); Phase P3 next.
**Previous milestone**: M9 closed 2026-06-14, merged as 2d819c4, tag m9-close.

## Authority files (binding, in priority order)

Every milestone planning prompt and every implementation decision must read these in order:

1. **`docs/durgam_rfp_v3.pdf`** — the frozen v3 specification. All section references (§8, §12, etc.) point to this file.
2. **`docs/rfp_errata.md`** — gaps, ambiguities, and corrections discovered after v3 was frozen. Binding alongside the RFP. If the RFP and an erratum disagree, the erratum wins (it captures the more current understanding).
3. **`docs/ux_charter.md`** — front-end standards. Read at every milestone gate and during planning.
4. **`docs/milestones/M{N}.md`** — the in-flight milestone's notes, inherited items, and gate checklist.
5. **CLAUDE.md** (this file) — project conventions, layering rules, established patterns.

The RFP is NOT re-issued when gaps are found. Single frozen v3 + a growing errata document is cleaner than maintaining v3.1, v3.2, etc. Each erratum entry names the source authority (usually the original informal requirements), the gap, and which milestone absorbs the correction.


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

## Permissions — `@require_role` and `@public_handler`
Every Reflex state event handler must wear EITHER `@require_role` OR `@public_handler`,
PLUS `@audit_action`. A handler without one of these fails CI lint.

**Authenticated handlers** (require a logged-in user):
```python
@require_role(action="approve", resource="leave_request", scope="department")
@audit_action(action="approve", resource="leave_request")
async def approve_request(self, request_id: UUID): ...
```
`@require_role` reads `self.current_user_id` from the Reflex State instance (M1 contract).
Raises `PermissionDenied` if unauthenticated or the permission check fails.

**Public handlers** (login, forgot_password, reset_password — no session required):
```python
@public_handler
@audit_action(action="login", resource="session")
async def login(self) -> None: ...
```
`@public_handler` marks the handler as intentionally unauthenticated. It does NOT
introduce an anonymous principal with a universal permission. `@audit_action` is still
required; the actor_user_id in the audit row will be None for unauthenticated actions.

Do not decorate with `@require_role(action="*", resource="*", scope="*")` or similar
wildcards to bypass access control. If an endpoint is genuinely public, use `@public_handler`.

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

## Testing rules

- **E2E tests that mutate persistent state** (passwords, account flags, tokens, lockout
  counters, or any DB field written by a failing/succeeding auth operation) must either
  (a) create per-test fresh users via a helper that tears them down in a `finally` block,
  or (b) reset mutated state at teardown. Option (a) is preferred — it isolates tests from
  each other even when a test fails before teardown. Option (b) fails silently if the test
  crashes mid-way and leaves dirty state for subsequent runs. This applies to ALL persistent
  mutations, including slow-burn ones: submitting one wrong password increments
  `failed_login_count` by 1 per run. After N consecutive runs without re-seeding, a seeded
  account locks. Use ephemeral users for ANY test that submits wrong credentials against a
  known-good username. The seed is shared across runs and must not be assumed to be in any
  particular state. Note: `alembic downgrade base` also counts as state mutation against the
  dev DB — migration tests must target the test database.

  **Seeded users are read-only fixtures.** No test may log in as a seeded user and mutate
  their state. The following seeded users must be treated as read-only:
  - `sys_admin` / `SysAdmin_Dev1!XZ` — normal active user (can be used for read-only login tests)
  - `dean_sci` / `DeanSci_Dev1!XZ` — Dean role
  - `firstlogin_user` / `FirstLogin_Dev1!XZ` — `must_change_password=True` (read-only fixture)
  - `inactive_user` / `Inactive_Dev1!XZ` — `is_active=False` (read-only fixture)
  - `student_001` / `Student_Dev1!XZ` — Student role

  A test that needs a user with `must_change_password=True`, a locked account, or any
  other specific flag MUST create an ephemeral user with that flag set via
  `_create_ephemeral_user(must_change_password=True)`. This bug class was discovered
  four separate times at M1; it must not recur at M2 or later milestones.

- **Every E2E suite run must be deterministic.** Run the suite three times in succession
  as part of milestone gate verification. Non-determinism is a gate failure, not a flake
  to retry. Timeout fixes and retry loops mask root causes; they are not acceptable fixes.

- **Migration tests must target the test database** (`settings.test_database_url`), not
  the dev database. `alembic downgrade base` wipes all data — running it against the dev
  DB destroys seed data and breaks subsequent E2E runs silently.

- **Navigation reachability**: URL-based Playwright scenarios verify that pages work
  when reached directly. They do NOT verify that pages are reachable through the
  application's own navigation. Every module's E2E suite must include at least one
  scenario per user journey that starts at a natural entry point (typically `/`) and
  navigates to the feature the way a real user would. Specifically:
  - Every module that adds authenticated UI must include a test that logs in and
    verifies the relevant UI is reachable from the home page or the nav shell.
  - Forced-redirect flows (e.g., `must_change_password`) must be tested end-to-end
    through the login form, not just at the service or state layer.
  This gap was discovered at M1 gate and must not recur at M2.

- **Reflex + Playwright**: `wait_for_load_state("networkidle")` is NOT safe for
  assertions after state-mutating actions. Reflex is all-WebSocket; networkidle fires
  immediately with no HTTP traffic. Use `wait_for_url()` for redirect assertions and
  polled `expect(...).to_be_visible()` for flash/element assertions.

These rules were learned at M1 and apply to M3, M5, and all subsequent milestones.

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
  - Reflex's own CLIENT_TOKEN (stored in sessionStorage, not a cookie).
  - The `dsession` auth cookie managed by `BaseState.session_token` (SD-001).
  - Reflex's CSRF token cookie.
  Anything beyond these two is a smell; surface it before adding.
- **Never use `rx.html()` or any HTML-passthrough primitive for content that includes any user-controlled string.** The M1 session token is stored in a JS-accessible cookie (see TD-005); an XSS exposure leaks sessions. If a use case appears to require `rx.html()` with user content, stop and raise it as a design question. Lint enforces this.
- Don't import from another service inside a service. If two services need each other, that's a design smell — surface it.
- Don't add a third-party package without justifying it in the PR; new deps cost.
- Don't skip the Mailpit / mock-data path "to save time"; both are first-class M0 deliverables.
- Don't reorder fields in an existing migration; add a new migration.
- Don't `@require_role` a handler with `'*'` to make a test pass; fix the test or the permission seed.
- Don't catch broad exceptions in services. Let them bubble; the page state turns them into user-visible errors.
- **Never access SQLModel object attributes after `session.commit()` or after an `open_session()` block closes.** `expire_on_commit=True` (the default) marks all attributes expired; accessing them on a detached instance raises `DetachedInstanceError`. Reflex catches this exception silently — the failure looks like `rx.redirect()` "didn't happen" with no visible error. Pattern: read all needed attributes into local variables INSIDE the `with open_session()` block, BEFORE `session.commit()`. See `docs/modules/auth.md` → "Known gotcha" for the full example.

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

## Patterns established at M2

These patterns were decided at M2 and apply to every subsequent milestone.

### Navigation registry

Each module contributes nav entries via its `__init__.py`:

```python
# durgam/pages/<module>/__init__.py
from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="Module Name", href="/module", icon="icon",
    group="GroupName",
    permission_action="read", permission_resource="resource",
))
```

`BaseState._load_nav_entries()` calls `can()` per entry at login and caches
`visible_nav_entries: list[dict]` in state. The nav shell reads this cache — no DB
calls at render time. Mobile drawer and desktop nav share the same list.

`permission_action=None` means the entry is visible to all authenticated users.

### Responsive table two-tier rule

**Tier 1 — Card layout (≤4 key columns, lookup/management tables):**  
Used for user list, role list, permission list, and any future module with a
management-focused list (HoD list, course list, etc.). Below 768px each row becomes
a stacked card. Use `durgam/pages/shared/data_table.py` with `TableColumn`.

Card field spec for existing M2 tables:
- User list cards: username, email, role badges, status visible; last_login_at hidden; actions in kebab.
- Role list cards: name, code, permission count badge; level/created_at hidden; actions in kebab.
- Permission list cards: resource, action, scope visible; no actions (read-only).

**Tier 2 — Horizontal scroll with sticky first column (5+ comparison columns):**  
Used for course allocation, faculty workload, attendance sheets, exam results, leave
requests, audit log, and any table where users scan across columns to compare values.
The first column (name/date/ID) is sticky; remaining columns scroll horizontally.
Apply directly with `rx.table` + `overflow_x="auto"` and a sticky first-column style.

### Confirmation dialog pattern

Always use `durgam/pages/shared/confirmation_dialog.py` for destructive actions.
The dialog MUST:
- Name the affected resource (e.g., "Delete user 'jdoe'?").
- State the consequence in plain language (e.g., "This will deactivate the account.").
- Offer a clear cancel button.
- NOT appear for non-destructive saves.

### Permissions are seed-only

All (resource, action, scope) permission triples are defined in `scripts/seed.py`.
No create/update/delete UI exists for permissions. When a new module introduces a new
resource, add the permission triples to `scripts/seed.py` in that module's branch.
The permission catalog is a system-design concern, not a runtime admin concern.

The M2 seed enumerates the (resource, action, scope) triples that exist in the system
at this milestone. Future milestones extend the seed for new resources.

**Action vocabulary (established at M2):**
- `read` / `write` / `delete` — CRUD operations on a resource.
- `configure` — system-level configuration (e.g. system:configure:*).
- `approve` — approval workflow action (e.g. leave_request:approve:department).
- **`manage` is NOT used.** The old `system:manage:*` triple was replaced with
  `system:read:*`, `system:write:*`, `system:configure:*` at M2 close-out. Any
  code path that called `can("manage", ...)` must use the specific action instead.

### Hard-delete audit policy

`UserAdminService.hard_delete_user()` (and any future hard-delete service method) MUST
check for audit log rows before deleting. If `COUNT(auditlog WHERE actor_user_id = user_id) > 0`,
raise `HardDeleteBlockedError` with an explanatory message. The auditlog is
INSERT+SELECT only — `actor_user_id` cannot be nulled after the fact. This applies to
any model that appears as `actor_user_id` in the auditlog.

## Session start checklist
At the start of every coding session, Claude Code runs:
1. `git status` — confirm clean working tree.
2. `cat CLAUDE.md | grep "Current milestone"` — confirm what's in flight.
3. `uv run pytest --collect-only -q | tail -5` — confirm tests are discoverable and the suite isn't broken.
4. Read the RFP section for the current milestone (§12 entry for the milestone in flight).

If any of the above fails or surprises, stop and surface it before writing code.

### Route protection rule (applies to ALL authenticated pages from M2 onward)

**Applies to:** `/` (home page), `/change-password`, all `/admin/*` pages, and
every authenticated page added in M3+.

Every authenticated page must guard its on_load handler AGAINST BOTH
unauthenticated AND authenticated-but-unauthorized states, before rendering
any content:

1. Wrap the page in `rx.cond(BaseState.admin_authorized, content, rx.fragment())`
   via `admin_page(content)`. `admin_authorized` is set to True ONLY after
   `_admin_guard()` confirms BOTH authentication AND `can("read","user")` pass.
   This means authenticated-but-unauthorized users (e.g. student_001) also see
   a blank screen before redirect — not chrome.
2. `_admin_guard()` clears `self.flash = ""` and `self.admin_authorized = False`
   at the start of every admin navigation (stale notifications from prior page
   do not persist).
3. Return the guard redirect if not None (short-circuit before any data load).
4. Only then load data and populate state.

For home page: `rx.cond(AuthState.current_user_id != "", content, rx.fragment())`.
For admin pages: `admin_page(content)` which uses `BaseState.admin_authorized`.

Do NOT use `@require_role` on on_load handlers — it raises `PermissionDenied`
instead of redirecting, which shows admin chrome + error toast to unauthenticated
users.

`@require_role` + `@audit_action` remain correct on business-logic handlers
(create, update, delete) that operate inside an already-authenticated session.

**Manual incognito check at every gate.** Visit each protected page without
a session; it must redirect to `/login`, no chrome visible at any moment.
From M3 onward, unguarded pages are a gate failure even if integration tests pass.

This rule was established at M2 after discovering admin pages rendered chrome
for unauthenticated users. First instance: M1 home page (home_on_load). Second:
M1 change-password (change_password_on_load). Third: M2 admin pages (_admin_guard).

### E2E helper sharing rule

When a new test file needs to log in, it imports `_login()` (and other shared
helpers) from `tests/e2e/_helpers.py`. It must NEVER duplicate the helper.

The canonical selectors (verified against the rendered login page):
  - Username placeholder: `"your.username"`
  - Password placeholder: `"••••••••••••"` (12 bullet characters)
  - Submit button: regex `r"Sign in"` (case-insensitive)

Duplication creates selector drift across files (root cause of the M2 E2E
regression where the duplicated helper used wrong placeholder text, blocking
all 14 M2 tests).

### E2E test selector rule

Selectors must be written against the actual rendered page, not assumed
from the page's intent or the source code. Verify each new test locally
against a running app before committing.

Known selector rules in DURGAM (from M2 verification):
- Inputs: use `page.get_by_placeholder("...")` — forms use `rx.input(placeholder=...)`
  with `rx.text()` for labels. `rx.text()` renders as `<p>`, NOT `<label>`, so
  `page.get_by_label()` will NOT find inputs.
- Headings: use `page.get_by_role("heading", name="...")` — `rx.heading()` renders
  as a heading role element. `page.get_by_heading()` does NOT exist in Playwright Python.
- Email assertions: only call `_latest_mailpit_email()` if the test ACTUALLY sent an
  email (e.g., user created via the UI form, not via `_create_ephemeral_user()`).
  `_create_ephemeral_user()` inserts directly into the DB; no email is dispatched.
- Nav links: `page.get_by_role("link", name="Admin")` — the nav links are rendered
  by `rx.link()` which produces `<a>` elements with role=link.

From M3 onward, no test ships without a local-run verification of its specific
selectors. A test that passes locally but was never run against the rendered page
is not a verified test.

### E2E selector specificity rule

When selecting by accessible name, use `exact=True` whenever the name could be a
prefix of another rendered label. The M2 "Users"/"Import Users" case is canonical:

```python
page.get_by_role("link", name="Users", exact=True)   # correct
page.get_by_role("link", name="Users")                # strict-mode violation
```

Partial-match selectors either throw a strict-mode violation (2+ matches) or
silently select the wrong element. Default to exact=True for all nav link/button
name selectors. The preferred alternative is `locator('a[href="..."]')`.

### Page-on-load data refresh rule

Every list page that displays mutable data MUST:
1. Reset the list state var to `[]` at the START of the on_load handler (before
   the DB query). This prevents stale rows from a previous navigation from
   lingering if the new query is slow.
2. Re-query the DB in the on_load handler on EVERY navigation, not only on first
   mount. The Reflex WebSocket connection may persist between same-session
   navigations; without an explicit reset, old data stays visible.

```python
async def load_users(self) -> None:
    guard = self._admin_guard()
    if guard is not None:
        return guard
    self.users = []          # ← reset first
    self.total_users = 0
    with open_session() as session:
        ...                  # query and populate self.users
```

### E2E dependent-dropdown rule

When a test interacts with a dropdown whose options are populated by an async
server response to a prior selection, the test MUST wait for the **specific option**
to be attached — not just for the dropdown element to be visible.

Reflex WebSocket state updates do NOT affect Playwright's `networkidle` state, so
the dropdown element renders (becomes visible) before the server delivers the options
list. Calling `select_option("read")` immediately after "visible" will find an empty
list and fail. This is the same WebSocket-state-arrival principle as the M1
`wait_for_url` rule.

**Pattern:**
```python
# Wrong — dropdown visible but options not yet delivered
expect(action_sel).to_be_visible(timeout=10_000)
action_sel.select_option("read")           # may find empty list

# Correct — wait for the specific option to exist in the DOM
expect(action_sel.locator("option[value='read']")).to_be_attached(timeout=10_000)
action_sel.select_option("read")           # option is guaranteed present
```

Also: `option:not([value=''])` targets real options excluding the placeholder, useful
for waiting until a dropdown is fully populated:
```python
expect(user_sel.locator("option:not([value=''])").first).to_be_attached(timeout=15_000)
```

From M3 onward, every test that interacts with a dependent dropdown (action filtered
by resource, scope_id filtered by scope_type, etc.) must use this pattern.

### Admin page stable-anchor wait rule

After navigating to an admin page via `page.goto()`, never immediately assert
on list content. The `admin_page()` wrapper hides all content in `rx.cond`
until `_admin_guard()` fires via WebSocket (AFTER `wait_for_load_state("networkidle")`
returns, because networkidle is HTTP-only). Always wait for a stable DOM anchor
that is unconditionally present once the guard succeeds:

```python
page.goto(f"{BASE_URL}/admin/users")
page.wait_for_load_state("networkidle")
# Wait for admin_page() to show content after on_load guard fires.
_wait_for_admin_page(page, "+ New user", timeout=15_000)
# Now assert on list content.
expect(page.get_by_text(username)).to_be_visible(timeout=10_000)
```

`_wait_for_admin_page()` is defined in `tests/e2e/test_admin_suite.py`. Add an
equivalent helper in every new E2E file that uses admin pages.

### E2E exact=True rule for dynamic values

Any `get_by_text()` on a dynamic value (username, email, code, name generated
by the test) MUST use `exact=True`. Dynamic values frequently appear as substrings
of other DOM text:
- A username `e2e_abc123` is a prefix of its email `e2e_abc123@sssihl.edu.in`.
- A role code `GATE_XYZ` could be a substring of a role name `Gate XYZ Role`.
- A short code can appear inside a longer label.

Without `exact=True`, Playwright's substring matching finds multiple elements and
throws a strict-mode violation. This is the third instance of this discipline at M2
(after "Users"/"Import Users" and "Admin"/"Admin Dashboard"):

```python
# Wrong — strict-mode violation if email also visible
expect(page.get_by_text(username)).to_be_visible()

# Correct
expect(page.get_by_text(username, exact=True)).to_be_visible()
```

From M3 onward: any `get_by_text` on a test-generated value defaults to
`exact=True` unless intentional substring matching is required and documented.

### Notification lifecycle rule

Notifications/flashes are tied to a single page visit:

1. **On every admin navigation:** `_admin_guard()` clears `self.flash = ""`.
   Stale flash from a prior page does not persist to the next page.
2. **`generated_password` (temp password):** cleared at the start of `load_users()`
   when the user navigates back to `/admin/users`. Shown once; gone on next visit.
3. **On logout:** `AuthState.logout()` clears `self.flash = ""` and
   `self.admin_authorized = False` before redirecting to `/login`. No notifications
   follow the user to the login page.
4. **Persistent notifications (the only known M2 case):** the temp password box
   persists until the user clicks Dismiss or navigates away. No other notification
   is marked persistent.

### State-binding rule for checkboxes and toggles

A widget's visual state (checked/unchecked, on/off) MUST be bound directly to
the source-of-truth state variable — not to a separate intermediate variable or
to a `default_*` prop.

The M2 permission accordion bug (Bug H): count badges used `role_perm_ids` (correct),
but checkboxes used `default_checked=item["granted"]=="true"` (React uncontrolled mode).
React only reads `defaultChecked` at MOUNT; it ignores subsequent state changes.
Navigating between roles updated `perm_table["granted"]` correctly, but the checkboxes
stayed at their original mounted state.

**Fix pattern**: use `checked=State.source_of_truth_set.contains(item_id)` (controlled
mode) and `on_change=State.toggle(item_id)`. The handler updates the source-of-truth
set; the checkbox re-renders reactively. The count badge and the checkbox both read
from the same state — they cannot diverge.

```python
# Wrong — uncontrolled; only works at mount; diverges from live state
rx.checkbox(default_checked=item["granted"] == "true")

# Correct — controlled; reactive; same source of truth as count badges
rx.checkbox(
    checked=State.checked_ids.contains(item["id"]),  # type: ignore[attr-defined]
    on_change=State.toggle(item["id"]),
)
```

From M3 onward: any checkbox or toggle that displays the current state of a DB
record MUST use the controlled pattern.

### Ephemeral form state rule

Form widgets that hold user-input state (search boxes, permission check widget,
temp filters, selected-value dropdowns) MUST be reset on every page on_load.
Stale form values from a prior page visit must not appear when the user returns.

The M2 widget Bug J: permission check widget retained selected values and result
after navigating away and returning. Fix: add `PermissionCheckState.clear_widget`
to the page's `on_load` chain via `app.add_page(... on_load=[main_handler, clear_widget])`.

Pattern: same lifecycle rule as flash notifications — ephemeral state is scoped to
a single page visit and is cleared by on_load before new state is computed.

```python
# In the state class:
def clear_widget(self) -> None:
    self.pc_result = ""
    self.pc_selected_resource = ""
    # ... other ephemeral fields

# In durgam.py:
app.add_page(page_fn, route="...",
             on_load=[MainState.load_data, WidgetState.clear_widget])
```

### Standard color tokens (established at M2)

All buttons and notifications use named standard styles. No component hard-codes colors.

**Buttons** (use helpers from `durgam/pages/components.py`):
- `primary_btn(...)` — primary action (Save, Submit, Create, Confirm)
- `secondary_btn(...)` — secondary action (Cancel, Back, Close)
- `destructive_btn(...)` — destructive action (Delete, Deactivate)

**Notifications** (use helpers from `durgam/pages/components.py`):
- `flash_success(message)` — green tint
- `flash_error(message)` — red tint
- `flash_warning(message)` — amber tint
- `flash_info(message)` — indigo tint

Token names live in `durgam/theme.py`: `--color-destructive`, `--color-success-bg`,
`--color-success-border`, etc. From M3 onward, new buttons and notifications reference
these helpers; deviating requires adding a named token, never inlining colors.

### Ephemeral-user dropdown filter rule

Any UI dropdown that selects a user MUST exclude usernames matching the ephemeral
test pattern (`e2e_%`). Pass `exclude_ephemeral=True` to `UserRepository.list_paginated`.
This prevents test-run pollution from appearing to real admins.

The `e2e_` prefix is the documented ephemeral convention; see `tests/e2e/_helpers.py`.

The user list page (`/admin/users`) does NOT filter — all users including e2e_ are
shown there as a diagnostic aid. Only per-user selection dropdowns (e.g., permission
check widget) filter them out.

### Gate-verification seeded-user rule

Gate-verification tests use seeded users for assertions about the permission
system, not ephemeral users. Ephemeral users (`e2e_*`) are for tests that
create/edit/delete users in isolation (e.g., `test_create_user_flow`).

The user dropdown filter (`exclude_ephemeral=True`) excludes `e2e_*` users
from per-user selection widgets by design — to keep test pollution out of the
admin UI. Tests that interact with these dropdowns MUST use seeded users.

To get a seeded user's UUID at test-setup time:
```python
from tests.e2e._helpers import get_seeded_user_id
student_id = get_seeded_user_id("student_001")
```

Seeded users used for permission-check widget assertions are read-only fixtures
(see "Testing rules" above). The test reads their UUID but must NOT modify the
user row. This rule was discovered at M2 when `test_create_role_and_verify_scoped_permission`
created an ephemeral user and then could not find them in the widget dropdown.

### Migration test isolation

Migration tests (`tests/integration/test_migrations.py`) must call `_reset_test_db()`
at the start of any test that runs a downgrade/upgrade cycle. The `seeded_db_engine`
session fixture's teardown drops all SQLModel tables but leaves `alembic_version` at
the current head — creating an inconsistent state. `_reset_test_db()` drops
`alembic_version` and all SQLModel tables, then runs `upgrade head` from scratch.

## Patterns established at M3

These patterns were discovered at M3 and apply to every subsequent milestone.

### open_session() does NOT auto-commit

`open_session()` in `durgam/db.py` uses `with Session(engine) as session:`. In SQLAlchemy 2.0.49,
this calls `session.close()` on exit — NOT `session.commit()`. Every state handler that writes
to the DB must call `session.commit()` inside the `with open_session() as session:` block after
all service/repo calls succeed:

```python
with open_session() as session:
    svc = _svc(session)
    svc.update(entity_id, fields, actor_id)
    session.commit()  # REQUIRED — open_session does NOT auto-commit
```

Read-only handlers do not need a commit. This bug class appeared at Session 5 (campus/school/
centre CRUD appeared to succeed but no data persisted). Verified by SQLAlchemy test:
`with Session(engine) as session: session.flush()` → second session sees no data.

### rx.form on_submit is the canonical form pattern

For any form with multiple inputs in Reflex 0.9.x, use `rx.form` with `on_submit=State.handler`
rather than individual `on_click=State.save` on a button:

```python
rx.form(
    rx.input(name="form_name", value=State.form_name, on_change=State.set_form_name),
    rx.input(type="hidden", name="editing_id", value=State.editing_id),
    primary_btn("Save", type="submit"),
    on_submit=State.save_handler,
    reset_on_submit=False,
)
```

The handler receives `form_data: dict` with all named input values:
```python
async def save_handler(self, form_data: dict) -> None:
    name = form_data.get("form_name", "").strip()
```

This guarantees form data reaches the handler even if intermediate `on_change` round-trips
were dropped. The handler must still call `session.commit()` for writes.

### _config_guard checks write permission, not read

`_config_guard(resource, action="write")` defaults to checking write (not read) permission.
All users have read access to M3 resources (via BASIC_USER seed), so checking read would
let every authenticated user reach admin config pages. Always pass `action="write"` or
`action="configure"` explicitly for config pages:

- `/admin/config` landing: `_config_guard("university_vision_mission", "write")`
  (REGISTRAR has this; STUDENT does not)
- `/admin/config/campuses`: `_config_guard("campus", "write")` (SYSTEM_ADMIN only)
- `/admin/config/schools`: `_config_guard("school", "write")`
- `/admin/config/centres`: `_config_guard("centre", "write")`
- `/admin/config/departments`: `_config_guard("department", "write")`
- `/admin/config/class-timings`: `_config_guard("class_timings_config", "configure")`
- `/admin/config/working-days`: `_config_guard("working_days_config", "configure")`

### Page-handler wiring verification (M3)

The unit + integration test suite does NOT cover whether a Reflex form's submit actually
triggers the right state handler, or whether a page's on_load guard prevents rendering.
Manual verification of at least one create + edit + delete flow AND one route-guard
incognito check is required at every session boundary before continuing.

Bugs found at Session 5: CRUD didn't persist (missing session.commit); _config_guard
admitted all authenticated users (checked read permission which BASIC_USER has). Both
were invisible to pytest; only manual UI testing revealed them.

### Nav entry visibility: permission_any for multi-role entries

When a nav entry should be visible to multiple roles via different permission paths (e.g.
Vision & Mission — Registrar via `university_vision_mission:write:*` AND HoD via
`department_vision_mission:write:department`), use `permission_any`:

```python
register(NavEntry(
    label="Vision & Mission",
    href="/admin/config/vision-mission",
    icon="target",
    group="Config",
    permission_any=(
        ("write", "university_vision_mission", None),
        ("write", "department_vision_mission",  "department"),
    ),
))
```

The entry shows if the user passes `can()` for ANY tuple. All nav checks use
`any_scope=True` — a scoped role (e.g. HoD scoped to DMACS) is treated as "has
this permission for any department" rather than "has it for DMACS specifically". The
page does the specific-scope authorization; nav is a discovery signal only.

Single-gate entries (only one role path) continue to use `permission_action /
permission_resource / permission_scope_type`. Both forms cannot be set on the same entry.

When adding ANY new nav entry, ask: "which distinct user types should see this, and do
they reach it via different permission paths?" If multiple paths → `permission_any`. If
one path → single-gate.

`can(any_scope=True)` is also available for multi-gate page guards via
`_config_guard_any(gates: list[tuple[action, resource, scope_type]])` on BaseState.
Use this for pages that multiple roles can reach via different permissions (e.g. the
vision/mission page is accessible to Registrar AND HoD).

### Modal overlay pattern for config page forms and detail panels

Config pages with a list + create/edit/detail sub-view must render create, edit, and
detail content as **fixed-position modal overlays** — not inline at the top of the page.
Inline content renders at a known DOM position; the viewport does not move to show it
when the user triggered the action from a scrolled position.

Use `form_modal(content, is_open, max_width="520px")` from `durgam/pages/components.py`:

```python
def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading("New Campus"),
            rx.form(... on_submit=State.save_campus ...),
            gap="0", align="start", width="100%",
        ),
        is_open=CampusConfigState.show_form,
    )
```

`form_modal` uses the same `position="fixed"` + semi-transparent backdrop pattern as
`confirmation_dialog`. The modal appears centered in the viewport regardless of scroll
position. Closing it (Cancel / Save) returns the user to their scroll position in the
underlying list.

**Note**: `rx.scroll_to()` was attempted first but is unreliable in Reflex 0.9.x for
this use case (fires before new content renders). Modal overlay is the correct pattern.

Applied at M3 Session 6 to: campuses, schools, centres, departments, courses.

### Notification pattern for config pages

Config pages use inline state changes (not full page redirects) for sub-navigation
(list → detail → form). The on_load-based flash lifecycle rule does NOT apply: on_load
only fires on full page navigation, not on state-change-based sub-navigation.

Instead, config pages use `config_toast` — a fixed-position toast component:

```python
# In page:
config_toast(State.flash, State.flash_type, State.dismiss_flash)
```

`config_toast` renders in the top-right corner, fixed position, z-index 1000 — always
visible regardless of scroll position. Includes an ✕ close button that calls
`BaseState.dismiss_flash`. Both bugs (sticky + scroll-to-bottom) are solved in one component.

Auto-dismiss (timer) is deferred to the UI Polish milestone — `@rx.event(background=True)`
cannot be yielded from handlers decorated with `@require_role` + `@audit_action` without
refactoring the auth decorator chain.

Additional rule: `open_create`, `open_edit`, and `open_detail` must clear flash at their
start (`self.flash = ""; self.flash_type = "info"`) so stale notifications from prior
actions don't appear when the user opens a new form or detail panel. Discovered at M3
Session 6 (Bug 2: "Code required" error appearing on edit open).

This pattern was established at M3 Session 6 after two failed rounds of the on_load
lifecycle approach.

### Permission triple completeness rule

When a service method or UI handler exists for an action on a resource, the
corresponding permission triple MUST exist in `scripts/seed.py` AND be assigned
to at least one role that has the UI for that action.

At each session boundary, audit all three together:
- Every service method's action (create → write, update → write, soft_delete → delete)
- Every UI handler's `@require_role(action=..., resource=...)` decorator
- Every `(resource, action, scope)` triple in `scripts/seed.py`

If a handler has `@require_role(action="delete", resource="X")` but `X:delete:*`
is not in the seed, the call raises `PermissionDenied` for every user.

Gap discovered at M3: `course:delete:*` was absent from the seed while
`soft_delete_course` was decorated `@require_role(action="delete", resource="course")`.
sys_admin got PermissionDenied on soft-delete despite having all other course
permissions.

When adding a new resource: seed read + write + delete triples. Only omit delete
if no delete UI exists at that milestone (e.g., program and subdepartment at M3).

### Auto-create implicit join rows on entity creation

When an entity has a required FK to another entity AND a separate join table
that represents the same relationship, the create handler must write BOTH the
FK row AND the join row in the same transaction. The join table is the source
of truth for queries that count relationships; a missing join row shows zero
even though the FK is set.

Example: `Department` has `main_campus_id` (FK to `campuses`) AND
`department_campuses` join table. The `save_department` create path calls
`svc.create(...)` AND `svc.add_campus(new_dept.id, main_campus_id, actor_id)`
before `session.commit()`. The seed script does both; the UI handler must too.

Same pattern applies wherever dual-representation exists (FK + join table
for the same relationship). Discovered as Bug 1 at M3 Session 6.

### Form Cancel button separation rule

Cancel buttons inside `rx.form` must carry `type="button"` to prevent the
browser from submitting the form. Without it, `<button>` defaults to
`type="submit"` and triggers the form's `on_submit` handler (including
validation), which is Bug 2's root cause at M3 Session 6.

```python
# In the page:
primary_btn("Save", type="submit"),
secondary_btn("Cancel", on_click=State.cancel_form, type="button"),

# In the state:
def cancel_form(self) -> None:
    self.show_form = False
    # ... reset form fields ...
    self.flash = ""          # clear any validation errors shown before cancel
    self.flash_type = "info"
```

### Flash lifecycle in handlers that call load_*

`_config_guard()` (called inside every `load_*` handler) clears `self.flash`.
If a handler sets flash and then calls `load_*`, the flash is erased before
Reflex sends the final state to the client — the success message is never seen.

Fix: set `self.flash` and `self.flash_type` AFTER the `await self.load_*()` call.
On error paths that return early without calling `load_*`, set flash before return.

```python
# Wrong — flash set before load; _config_guard inside load clears it
self.flash = "Saved."
await self.load_items()    # clears flash!

# Correct — flash set after load so the message survives
await self.load_items()
self.flash = "Saved."      # set after _config_guard has already run
self.flash_type = "success"

# Error paths return early and don't call load — set flash before return
except SomeError as e:
    self.flash = e.message
    self.flash_type = "error"
    return
```

This pattern applies to every `save_*`, `soft_delete_*`, and inline action
handler in M3 and all subsequent milestones. Discovered as Bug 3 at M3 Session 6.

### List page loading state rule

Every list page must have a `loading: bool = True` state variable.
The page renders a spinner while `loading` is `True`; the real list (or genuine
empty state) when `False`. The `on_load` handler sets `loading = True` after the
guard passes, populates the list, then sets `loading = False`. Starting at `True`
means the spinner shows on first mount rather than the empty state.

```python
class SomeConfigState(BaseState):
    items: list[dict] = []
    loading: bool = True   # True so first render shows spinner, not empty state

    async def load_items(self) -> None:
        guard = self._config_guard("resource", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.items = []       # reset before query (page-on-load data refresh rule)
        with open_session() as session:
            ...               # query and populate self.items
        self.loading = False
        self._load_nav_entries()
```

Page pattern — wrap the data_table in a loading cond:
```python
rx.cond(
    State.loading,
    rx.center(rx.spinner(), padding="2rem"),
    data_table(rows=State.items, ..., empty_message="No items found."),
)
```

Without this, list pages flash an empty state for ~100–200ms before the DB
query returns. Discovered and fixed at Session 6.

### Never name a service method `list`

Naming a service method `list` shadows the Python builtin `list` type in class-body
annotation evaluation, causing `TypeError: 'function' object is not subscriptable` for
any return type annotation like `-> list[Campus]` in a later method. Use entity-specific
names (`list_campuses`, `list_all`) or add `from __future__ import annotations` to the
service file to defer annotation evaluation. Discovered at Session 4.

### Fine-grained scope checks in handler body

`@require_role` performs a COARSE permission check: "does this user hold a role
that grants (action, resource, scope_type) for ANY scope?" It passes `scope_id=None`
to `can()` unless the state class exposes a `scope_id` attribute.

For scope-restricted resources (e.g. HoD can only edit THEIR department's V&M):

**Problem**: `@require_role(scope="department")` calls `can(scope_id=None)`. In
`can()`, a `UserRole` with `scope_id=<DMACS UUID>` is skipped when `scope_id=None`
and `any_scope=False` → `PermissionDenied` even though the user has the permission.

**Fix — two layers**:
1. Decorator uses `any_scope=True` for the coarse check (passes the guard).
2. Handler body calls `can()` directly with the **exact** resource UUID for the
   fine-grained check, rejecting mismatches with a user-friendly error:

```python
@require_role(action="write", resource="department_vision_mission",
              scope="department", any_scope=True)   # ← coarse: user has SOME dept write
@audit_action(action="write", resource="department_vision_mission")
async def save_dept_vision(self, form_data: dict) -> None:
    dept_uuid = UUID(self.dept_id)
    with open_session() as session:
        if not can(UUID(self.current_user_id), "write",
                   "department_vision_mission", "department", dept_uuid, session):
            self.flash = "You can only edit your own department's data."
            self.flash_type = "error"
            return                                    # ← fine: exact dept check
        ...
```

`any_scope=True` is ONLY appropriate for handler decorators where the handler body
performs the fine-grained check. Never use it for nav or UI visibility — use the
existing `any_scope=True` path inside `get_visible_entries()` for that purpose.

Discovered at M3 Session 7 gate verification when `hod_dmacs` got
`PermissionDenied` on `save_department_vision` despite having the correct
scope binding (`HOD` role with `scope_id=<DMACS UUID>` in `user_roles`).

### Singleton config edit page pattern

Singleton config pages (one row in the table) use a get_or_create-on-load approach:
the state's load handler calls `service.get_class_timings()` (or equivalent), which
calls `repo.get_or_create_*()` to ensure a row exists. The form pre-populates from
that row. The save handler passes new values to `service.save_*()`, which validates
and updates the same singleton row. No create/delete UI exists. Pattern established
at Session 7 for `ClassTimingsConfig` and `WorkingDaysConfig`.

### Update-only entity UI pattern

For entities where the business rule forbids deletion (E-001 — vision/mission):
- No delete button appears anywhere in the UI.
- The service `delete_*` stubs always raise `NotDeletableError`.
- The repository exposes no delete methods (test `test_repo_exposes_no_delete_methods`
  enforces this).
- Individual sub-entities (e.g. mission statements) MAY be soft-deleted/removed; only
  the parent entity (UniversityVisionMission, DepartmentVisionMission) is delete-blocked.
- Repository remove methods for sub-entities must be named `remove_*` (not `soft_delete_*`)
  to avoid triggering the no-delete-method test.

### E2E CRUD test isolation pattern

Every E2E test that creates a system entity (campus, school, centre, department,
course) MUST:

1. **Pre-clean at the start**: call `_hard_delete_by_code(table, code)` before
   the test body. This ensures a leftover entity from a previous failed run
   does not cause a unique-constraint error on create.

2. **Wrap body in `try/finally`**: call `_hard_delete_by_code` in the `finally`
   block to clean up even if the test fails before the soft-delete step.

3. **Use a stable, non-seeded code**: pick a code that doesn't appear in the
   seed script (e.g. TST, TSC, TCE, TDE, TST101). Never reuse a seeded code.

Background: soft-deleted entities keep their `code` value with a DB-level unique
constraint that applies to ALL rows including soft-deleted. If the test fails
before soft-deleting, the next run tries to create the same code and gets a
unique constraint error (rather than the intended test failure). The pre-clean
and finally-cleanup together prevent this.

This pattern was discovered at M3 gate verification when CRUD tests failed
consistently after the first run.

### Compound state invariants — application enforcement on ALL paths

When an entity has a "primary" FK relationship that should always match one of its
many-to-many join rows (e.g., `departments.main_campus_id` must equal one of the
dept's `department_campuses.campus_id` rows), the application must enforce this
invariant on EVERY code path that can change either the FK or the join rows. The FK
constraint alone allows the inconsistency because the foreign key points at the parent
campus table, not at the join row.

For Department/DepartmentCampus:
- **create_department**: auto-creates the `DepartmentCampus` row for `main_campus_id`
  (Session 6, Bug 1 — "auto-create implicit join rows on entity creation").
- **remove_campus_link**: blocked when removing main; user must promote a replacement
  first (Session 7, Bug B).
- **update_department**: auto-creates the `DepartmentCampus` row for the new
  `main_campus_id` if it doesn't already exist (Session 7, Bug E).
- **promote_and_remove_main_campus**: atomic promotion + removal (Session 7, Bug B).

Pattern for update paths:
```python
def update(self, dept_id, fields, actor_id):
    dept = self.get(dept_id)
    new_main_id = fields.get("main_campus_id")
    if new_main_id is not None and new_main_id != dept.main_campus_id:
        links = self._depts.list_campus_links(dept_id)
        if new_main_id not in {link.campus_id for link in links}:
            self._depts.upsert_campus_link(dept_id, new_main_id)  # auto-add
    # ... apply remaining fields, save ...
```

Audit every entity with this dual-representation pattern (FK + join) and enforce the
invariant on every mutation path. This was discovered across THREE separate scenarios
at M3 Session 7 verification — each caught only by manual integration testing, not
by unit tests (which test methods in isolation and miss cross-path consistency).

### E2E test cleanup with dependent rows

When an E2E test creates an entity that has dependent join rows (e.g., Department
has DepartmentCampus rows with a FK constraint on departments.id), cleanup MUST
delete the dependent rows FIRST, then the parent. Direct SQL DELETE on the parent
raises `ForeignKeyViolation`.

Add a dedicated helper per table with known dependents rather than extending the
generic `_hard_delete_by_code`. Example:

```python
def _hard_delete_dept_by_code(code: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM department_campuses WHERE department_id = "
            "(SELECT id FROM departments WHERE code = :code)"
        ), {"code": code})
        conn.execute(text("DELETE FROM departments WHERE code = :code"), {"code": code})
        conn.commit()
```

Discovered at M3 gate: `_hard_delete_by_code("departments", "TDE")` raised
ForeignKeyViolation because the test's create flow auto-created a `department_campuses`
row that the generic helper didn't clean up first.

### E2E test text isolation

E2E tests that insert content visible in the rendered UI (mission text, search input,
etc.) MUST use a unique-per-run identifier so accumulated data from prior runs doesn't
cause Playwright strict-mode violations:

```python
test_id = uuid.uuid4().hex[:8]
mission_text = f"E2E test mission {test_id} — safe to remove."
```

Pair with:
- **Pre-test cleanup**: delete any rows matching a broad `LIKE 'E2E test mission%'`
  pattern at the start of the test body.
- **`try/finally` cleanup**: target the same pattern in the `finally` block so rows
  are removed even if the UI removal step in the test fails.

Discovered at M3 gate: mission text accumulated 8 copies across 8 prior test runs,
causing `page.get_by_text(text, exact=True)` to resolve to 8 elements → strict-mode
violation on the next run.

### About-page read-only display pattern

Public read-only pages visible to all authenticated users use:
1. `rx.cond(AuthState.current_user_id != "", content, rx.fragment())` — not `admin_page()`.
2. In the on_load handler: `self._resolve_session()` + check `self.current_user_id`; redirect to `/login` if absent. No `_admin_guard` or `_config_guard` needed.
3. Nav entries registered with `permission_action=None` so all authenticated users see them.
4. No write handlers — no `@require_role` or `@audit_action` decorations needed.

Pattern established at Session 7 for `/about/university`, `/about/departments`,
`/about/departments/[dept_code]`.

## Patterns established at M4

### Seed data is development/demo only — no institution-specific data

`scripts/seed.py` populates a development database for feature testing and
gate verification. It is NOT a deployment artifact.

Rules:
- Use placeholder/example domains for emails (e.g., `example.com`,
  `dev.local`, or Mailpit-compatible addresses). Never use the real
  institution's domain (`sssihl.edu.in` or similar) in seed.
- Use clearly-fictional but realistic names for entities. Close to
  real is fine for demonstrating the feature; the exact real names
  are not needed.
- Demo user passwords follow the `_Dev1!XZ` convention — obviously
  development-only.
- Any data that implies "this IS the live institutional configuration"
  does not belong in seed. That data gets configured through the
  admin UI during real deployment.
- When a seed row represents a bootstrap placeholder for
  runtime-managed data (e.g., RoleEmail addresses), add a code
  comment saying so — e.g.:
  `# Bootstrap placeholder — real addresses configured via admin UI
  by Registrar/SysAdmin.`

### Three-phase calendar collaboration with sequential confirm gates

The calendar collaboration chain uses three sequential phases, each gated by an
irreversible confirm action on the AcademicYear model:

1. **Phase 1 (Registrar framework)**: creatable when AY is unlocked. Registrar
   confirms → sets `master_calendar_locked=True`.
2. **Phase 2 (IQAC)**: creatable when `master_calendar_locked=True` AND
   `iqac_confirmed=False`. IQAC confirms → sets `iqac_confirmed=True`.
3. **Phase 3 (All others)**: creatable when `iqac_confirmed=True`.

Entry types are a fixed set defined in `ENTRY_TYPE_ROLE_MAP` (18 types across
4 phase sets). Adding or changing types requires a code change. Confirm actions
trigger phase-transition email notifications via fire-and-forget
`asyncio.create_task()`.

### AY-locked repository enforcement (AcademicYearLockedError)

All repositories on AY-scoped models call `_check_ay_locked()` before any write.
If `academic_year.is_locked=True`, the repo raises `AcademicYearLockedError`.
Services do not re-check; the repository is the gate. A nightly Celery task
locks expired AYs automatically.

### Celery task pattern — scheduled job tested by direct call

Celery tasks in `durgam/tasks/` are tested by calling the task function directly
(no broker needed). The beat schedule is the production dispatch mechanism; tests
verify the function logic only. Docker compose services for celery_worker and
celery_beat are behind the `celery` profile (opt-in). All container services use
`- /app/.venv` anonymous volumes to prevent overwriting the host venv.

### Fixed-type-set decision

Entry types, role codes, and permission triples are code-defined constants, not
runtime-configurable. This applies to `ENTRY_TYPE_ROLE_MAP`, `EXCLUDED_ROLES`,
and the phase sets. If a future requirement asks for configurable types, it must
address role-mapping and phase-gating implications.

## Patterns established at M5a

### File upload zone render-after-confirm guard

File upload zones render only after their dependent form fields have confirmed
through state (`rx.cond(field != "", upload_zone, placeholder)`). This prevents the
on_drop/on_change race where the upload handler fires before a prior field's WebSocket
round-trip completes. Applies to every reuse of `file_upload_zone`.

```python
rx.cond(
    State.form_role_code != "",
    file_upload_zone(
        on_drop=State.upload_handler,
        accept={...},
        label="...",
    ),
    rx.box(
        rx.text("Enter a role code to enable upload", ...),
        border="2px dashed var(--color-rule)",
        opacity="0.5",
    ),
)
```

The upload zone only renders after the server has received and confirmed the required
field via WebSocket. Even with this guard, the service must still validate the field
(defense in depth) — but the UI prevents the confusing UX where a file uploads, bytes
transfer, and then the server rejects with "field required."

Discovered at M5a: Playwright's `set_input_files` triggers `on_drop` before a prior
`on_change` completes its WebSocket round-trip. In production, a fast user or laggy
connection would hit the same race.

## Patterns established at M5b

### When you've claimed PASS, verify against user-visible behavior

The unit/integration test passing is necessary but not sufficient. For features involving multi-step user flows (save → load → render, create → approve, upload → confirm), the test must exercise the full path: state handler → DB row → loaded row dict → rendered UI condition. The Round 5 counsellor file-id bug was hidden across three rounds because tests at single layers all passed while the integrated flow silently dropped data.

Before claiming PASS:
1. If the feature has a save/persist step: write a test that calls the state handler and queries the DB for the resulting row's expected fields.
2. If the feature renders something: assert the state's row-dict contains the values the UI's rx.cond checks.
3. If the feature triggers a download: assert the URL or trigger is the same pattern as the working precedent (e.g. counsellor downloads should match letterhead download pattern from durgam/pages/admin/config/letterheads.py).

### When manual verification conflicts with your report, the report is wrong

If the user says "this doesn't work" and your last report said PASS, do not re-assert PASS. Investigate first:
1. Show the exact current code (file:line) implementing the feature.
2. Query the live DB to show the relevant rows have the expected state.
3. Trace the execution path from user action to visible output.
4. State whether the bug is missing-code, present-but-incorrect-condition, or present-but-blocked-upstream.
Only then propose a fix.

### When you defer something, defer it explicitly

If the spec calls for feature X and you build the simpler-but-different feature Y because Y is easier or because some dependency doesn't yet exist, flag it: "Built Y instead of X because Z; recorded as forward concern." Do not silently substitute. The Round 5 CSV-vs-DOCX divergence was found three rounds late because Y looked similar enough to X that the build report glossed it.

### When you change permissions, verify the inheritance chain

seed.py uses list composition for many role grants ("AHOD": _PUBLIC_READ + _HOD_SPECIFIC). Adding to _HOD_SPECIFIC propagates to AHOD. But some roles have inline lists (HOD_OFFICE) that do NOT inherit. Before assuming a permission propagates, verify the actual composition in seed.py role_perm_map.

### When you investigate a "pre-existing" failure, downgrade the schema too

Stashing code does not unwind migrations. A "pre-existing failure" run that compares stashed code against current schema is invalid. Either alembic downgrade to the prior head before testing, or run against a fresh DB with only baseline migrations applied. State this explicitly in your report.

### Reference patterns in this codebase

When implementing common shapes, follow the existing pattern rather than inventing:
- File downloads in kebab menus: durgam/pages/admin/config/letterheads.py lines around 41 (rx.link with DOWNLOAD_PREFIX)
- Render-after-confirm form with uploads: durgam/states/config_counsellor.py post-Round-5 (staged file vars, single save with file_ids passed to create)
- Ordered multi-select with visible order: durgam/pages/components.py role_multi_select_ordered
- Scope label resolution: durgam/scopes/registry.py resolve_scope_label
- Live-sourced role picker: BaseState._load_role_options + RoleRepository.list_active
- DOCX-on-letterhead generation: durgam/docgen/merge.py render_docx_template (returns tuple[bytes, list[str]] — destructure warnings)

## Patterns established at M6a

### Audit emission pattern — `_set_audit()` + `audit_snapshot()`

Every `@audit_action`-decorated handler must call `self._set_audit()` to provide
`resource_id` and `before`/`after` diffs. The decorator reads `_audit_pending`
from the state after the handler returns and passes the data to `write_audit_row()`.

```python
@require_role(action="write", resource="campus")
@audit_action(action="write", resource="campus")
async def save_campus(self, form_data: dict) -> None:
    with open_session() as session:
        svc = _svc(session)
        if not editing_id:
            entity = svc.create(code, name, actor_id)
            after_snap = audit_snapshot(entity)       # INSIDE session block
            session.commit()
            self._set_audit(resource_id=str(entity.id), after=after_snap)
        else:
            before_snap = audit_snapshot(svc.get(UUID(editing_id)))
            entity = svc.update(UUID(editing_id), fields, actor_id)
            after_snap = audit_snapshot(entity)
            session.commit()
            self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
```

**Rules**:
- `audit_snapshot(entity)` must be called INSIDE `with open_session()` (before session
  closes and detaches the entity).
- `_set_audit()` is called AFTER `session.commit()` succeeds — the snapshot dict is a
  plain dict and is safe outside the session block.
- For deletes: capture `before_snap` before the service delete call; no `after`.
- On error paths (except blocks): do NOT call `_set_audit()` — the mutation didn't happen.
- The decorator resets `_audit_pending = None` BEFORE calling the handler (prevents
  leakage from a prior handler that raised).
- Use `action="login_failed"` override for the login failure split:
  `self._set_audit(action="login_failed", resource_id=normalized_username, after={...})`.

### `audit_snapshot()` — automatic sensitive-field redaction

`audit_snapshot(entity)` serializes all column attributes of a SQLModel entity.
Fields listed in the entity class's `_audit_redact_fields: ClassVar[set[str]]`
are replaced with `"<redacted>"`. Currently only `User` has this:

```python
_audit_redact_fields: ClassVar[set[str]] = {"password_hash", "aadhaar_enc", "pan_enc"}
```

Any new model that stores sensitive data must define `_audit_redact_fields`.

### `_current_user_roles` — actor role snapshot at session resolve time

`BaseState._current_user_roles` is populated once per page navigation inside
`_resolve_session()` and `AuthState._resolve_session_state()`. The decorator
reads it without a per-action DB query and passes it as `actor_roles_json` to
the audit row. The column is JSONB with a GIN index for M6b scope-filter queries.

### `AuthError.reason` — machine-readable failure codes

`AuthError` now carries a `reason` keyword argument for audit trail differentiation:
- `not_found` — username not in DB
- `inactive` — account deactivated
- `locked` — account temporarily locked
- `invalid_credentials` — wrong password

Handlers use `exc.reason` in `_set_audit(after={"reason": exc.reason, ...})`.

## Patterns established at M6b

### Resource label resolver — registry + batch resolution

`durgam/audit/labels.py` provides `bulk_resolve_labels(rows, session)` which
enriches raw AuditLog dicts with human-readable labels for actor, resource,
FK fields in diff_json, and actor_roles_json scope entries. Each resource type
registers a resolver via `@register_resolver("resource_name")`; resolvers share
a `_simple_resolver(Model, label_fn)` factory. FK fields are mapped via `FK_FIELDS`
constant. The list-page post-processor `_add_display_fields()` at
`durgam/pages/audit/index.py` converts enriched dicts into display-ready fields
(occurred_at_display, actor_display, resource_display, scope_display, diff_summary).

### Sys-admin-only read page pattern

Pages visible only to SYSTEM_ADMIN use `_config_guard("resource", "read")` in
on_load (not `"write"` or `"configure"`). The nav entry uses the same gate:
`permission_action="read", permission_resource="resource"`. The audit log
(`/audit`) is the canonical example: `_config_guard("audit_log", "read")` +
nav entry gated by `audit_log:read`.

### JSONB containment for actor-role-scope filtering

Scope filtering queries `actor_roles_json` using the PostgreSQL `@>` containment
operator with a JSONB cast:

```python
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

stmt = stmt.where(
    AuditLog.actor_roles_json.op("@>")(
        cast([{"scope_type": stype, "scope_id": sid}], JSONB)
    )
)
```

See `durgam/pages/audit/index.py` `_build_filtered_stmt()`. The `actor_roles_json`
column has a GIN index (`ix_audit_logs_actor_roles_json_gin`) for query performance.

### CSV export with row cap

`durgam/services/audit_export.py` — `AuditCsvExportService.export()` produces
RFC 4180 CSV with `csv.QUOTE_ALL` (all fields quoted) and a UTF-8 BOM prefix
for Excel compatibility. The handler applies a 10,000-row LIMIT and flashes a
warning when the unfiltered count exceeds the cap. Download is triggered via
`rx.download(data=bytes, filename=str)`.

### Drawer body three-section convention

The audit detail drawer (`durgam/pages/audit/index.py`) establishes the pattern
for read-only forensic detail views:
- **Section A** — header key-value grid (actor, role, resource, IDs with copy)
- **Section B** — diff table with FK-label resolution, `(new)`/`(deleted)` null
  semantics, `<redacted>` pill rendering
- **Section C** — collapsible raw JSON accordion with code blocks and copy buttons

Diff entries are pre-processed by `_build_diff_entries()` into a flat list for
`rx.foreach` (Reflex cannot iterate `Var[dict]` keys). Detail-only fields are
added by `_add_detail_fields()`, separate from `_add_display_fields()`, to avoid
inflating list-row dicts.

### Radix Select.Item rejects `value=""`

`rx.select.item("...", value="")` crashes at compile time — Radix reserves empty
string as the "clear selection" sentinel. Use `value="all"` with a descriptive label
(e.g. "All scopes") for "no filter" items. All filter state vars that feed a
`rx.select` must default to `"all"`, not `""`.

## Patterns established at M7

### Approval engine — service-layer state machine with direct audit

The approval engine (`durgam/services/approval_request.py`) owns the state machine
(submitted → in_review → approved/rejected/withdrawn/cancelled). Audit rows are written
via `write_audit_row()` directly inside the service transaction — NOT via the
`@audit_action` decorator — because the service must record the transition atomically
with the state change. The decorator pattern is used for page-state handlers that call
into the service.

### Scope-chain routing via `resolve_stage_approvers`

`durgam/services/approval_routing.py` walks dept → school → campus → universitywide to
find users holding the required channel role at the most-specific scope. The walk order
is fixed; the first scope level with at least one matching user wins. This avoids
returning approvers at every level and duplicating notifications.

### Post-approval callback dispatch

`ApprovalRequestService._run_post_approval()` (`durgam/services/approval_request.py`)
dispatches by `process.code` on terminal approval. Single-consumer pattern for v1 — only
`NRF_APPROVAL` has a handler (`_create_nrf_from_approval`). New processes that need
post-approval side effects add a branch here. Deferred imports are used inside the handler
to avoid cross-service import at module level.

### Dynamic nav gating for approver roles (TD-024)

The "Approvals" nav entry uses `dynamic_check=is_channel_approver` on its `NavEntry`
registration (`durgam/pages/approvals/__init__.py`). The entry is visible if EITHER:
- The user holds the static `approval_request:approve:*` permission (5 roles + SYSTEM_ADMIN), OR
- The user holds any role that appears in any active `ApprovalProcess.channel_role_codes`.

The inbox page guard mirrors this logic: `ApproverInboxState._potential_approver_guard()`
checks both paths before rendering. The `is_channel_approver()` function is defined once
in `durgam/pages/approvals/__init__.py` and imported by both the nav registration and
the state guard — single source of truth prevents drift.

### Skip-self-at-stage routing for approval channels

When the requestor is the sole holder of a channel role at a given stage, that stage
is auto-skipped on submit and on approve-advance. An `auto_skip_stage` audit row is
written for each skip. If ALL stages are skipped (requestor is sole holder of every
channel role), the request is auto-approved. The skip logic lives in
`ApprovalRequestService._should_skip_stage()`.

### Explicit manual setters for form-bound state vars

Every State var bound to a form input (`on_change`, `value` binding) requires a
corresponding `def set_<var>(self, value): self.<var> = value` method. Reflex's implicit
auto-setters throw runtime errors in this codebase. Caught and fixed in M7 for
`SubmitRequestState` NRF fields; same pattern applied in M6b for `AuditLogState` filters.

### Empty-string Select.Item sentinel discipline

Carried forward from M6b (`value="all"`, not `value=""`). See M6b patterns section;
not duplicated here.

## Patterns established at M8.1

### Radix Select portal rendering — Playwright E2E pattern

`rx.select.root` renders its items in a browser portal only AFTER the trigger button
is clicked. Items appear as `<div role="option">` elements — NOT as `<option>` elements
and NOT with any `data-value` attribute visible to Playwright. Selectors like
`[data-value='foo']` will never attach, even with a long timeout.

**Correct pattern:**

```python
import re

# 1. Click the trigger to open the portal
page.locator("button[role='combobox']").first.click()
# 2. Wait for ANY option to attach (portal has mounted)
expect(page.get_by_role("option").first).to_be_attached(timeout=15_000)
# 3. Click by accessible name — regex for prefix-match, exact=True for full label
page.get_by_role("option", name=re.compile(r"^employee_username")).first.click()
```

When a page has multiple `rx.select.root` elements, the FIRST combobox button is
`.first`. After that selection closes the portal, click the SECOND combobox using
`.nth(1)` — NOT `.first` (which re-opens the first dropdown):

```python
page.locator("button[role='combobox']").nth(1).click()
expect(page.get_by_role("option").first).to_be_attached(timeout=10_000)
page.get_by_role("option", name="EL – Earned Leave", exact=True).click()
```

Use the full display label with `exact=True` when the short code (e.g. "EL") is a
substring of other option labels. Partial matching causes strict-mode violations.

Discovered at M8.1 Phase 9.1 when `[data-value='faculty_user']` never attached.

### `rx.input(type="date")` has no placeholder

`rx.input(type="date")` renders a native date picker. The `placeholder` prop has no
effect — the input does not render a `placeholder` attribute. Playwright's
`get_by_placeholder("YYYY-MM-DD")` returns zero elements.

**Correct selector:**

```python
date_inputs = page.locator("input[type='date']").all()
date_inputs[0].fill("2026-01-15")   # YYYY-MM-DD ISO format
date_inputs[0].press("Tab")         # trigger on_change round-trip
```

Discovered at M8.1 Phase 9.1 when `test_apply_past_date_shows_postfacto_badge` SKIPPED
because `get_by_placeholder("YYYY-MM-DD").all()` returned an empty list.

### Reflex 0.9.x API drift patterns (M8.1 Phase 4)

Three Reflex idioms that produce silent or runtime failures in Reflex 0.9.x:

1. **`nav_shell()` takes no positional arguments.** `nav_shell(content)` is wrong; wrap
   both `nav_shell()` and the content in the same `rx.vstack`.
2. **`rx.select.root` uses `on_change`, NOT `on_value_change`.** `on_value_change` fires
   on Radix-internal events and does not pass the selected value to the state handler.
3. **`rx.input(type="hidden")` renders visibly** in Reflex 0.9.x. Carry hidden IDs via
   explicit state vars (`self.editing_id`), not hidden form inputs.

Rule: check the Reflex 0.9.x changelog before using any new prop. When a callback or
hidden field "doesn't fire," check the prop name first.

### WebSocket render settlement pause after heading becomes visible

After a page heading becomes visible following a WebSocket state update, sibling
elements rendered by the same state delta may not yet be registered as visible.
Add a brief stabilization pause before asserting on those sibling elements:

```python
expect(page.get_by_role("heading", name="My Leave")).to_be_visible(timeout=15_000)
page.wait_for_timeout(800)   # let React re-render settle
apply_btn = page.locator("button").filter(has_text="Apply for Leave")
expect(apply_btn).to_be_visible(timeout=10_000)
```

This is a one-time settlement pause after confirmed heading visibility — NOT a retry
loop. Do not use this as a substitute for proper `to_be_attached` waits on
async-loaded content. 800ms was verified sufficient in practice.

### Seed-after-permission-change discipline

After any commit that adds new `(resource, action, scope)` permission triples to
`scripts/seed.py`, run `uv run python scripts/seed.py` against the dev DB BEFORE the
manual walkthrough. Missing this step causes `PermissionDenied` for every user for the
new resource, even when the code and seed content are syntactically correct.

```
uv run python scripts/seed.py   ← must run before next walkthrough step
```

Discovered at M8.1 Phase 8 when `leave_request_admin:write:*` was added in a commit
but not re-seeded before walkthrough.

### Inline-table column headers and checkbox labels

Every `rx.foreach`-based data list that does NOT use `data_table()` from
`durgam/pages/shared/data_table.py` must include:

1. An explicit `rx.hstack` column header row above the `rx.foreach` loop, with the
   same `min_width` / `gap` values as the data rows so columns align.
2. Every checkbox input must have an inline `rx.text` label AND a one-line helper text
   below it explaining what the checkbox controls.

`data_table()` renders column headers automatically from `TableColumn.label`. For
hand-rolled lists, add the header row explicitly:

```python
rx.hstack(
    rx.text("Leave Type", font_weight="600", font_size="0.8rem",
            color="var(--color-muted)", min_width="6rem"),
    rx.text("Entitlement (days)", font_weight="600", font_size="0.8rem",
            color="var(--color-muted)", min_width="10rem"),
    gap="1.5rem", align="center", padding="0.4rem 0.75rem", width="100%",
),
```

For checkboxes:

```python
rx.vstack(
    rx.hstack(
        rx.checkbox(checked=State.form_enabled, on_change=State.set_form_enabled),
        rx.text("Enable annual credit run for this leave type", font_size="0.9rem"),
        align="center", gap="0.5rem",
    ),
    rx.text(
        "When disabled, the annual credit job will skip this leave type.",
        font_size="0.75rem", color="var(--color-muted)",
    ),
    align="start", gap="0.25rem", margin_y="0.5rem", width="100%",
),
```

Discovered at M8.1 Phase 9.2 on `/admin/leave/credit-policy`.

## Patterns established at M9

### Decorator action must match seeded Permission row exactly (TD-053 / Phase 8b.1)

Every `@require_role(action="X", resource="Y", scope="Z")` decorator must have a
corresponding `(Y, X, Z)` triple in `scripts/seed.py`. The CI meta-test
`tests/integration/test_announcement_decorator_actions.py` enforces this for M9
state classes. New modules must extend the meta-test or add a module-specific equivalent.

**Common failure mode**: `action="write"` on the decorator when the seeded triple uses
`action="soft_delete"`. The seeded action vocabulary is the canonical source — always
grep `scripts/seed.py` for the resource before choosing the decorator action.

### `can()` bypass semantics for non-structural scope types (TD-052 / Phase 7.1 + 8b.2)

Two scope values bypass the `UserRole.scope_type` filter in `durgam/auth/permissions.py`:

- **`scope_type="*"`** — caller requests any-scope access; a scoped UserRole (e.g., campus-scoped DIRECTOR) can satisfy this.
- **`scope_type="own"`** — per-instance ownership; the UserRole's structural scope is irrelevant. The handler body enforces ownership at runtime via `ann.composer_user_id == actor_id`.

The invariant in `can()` at line 67:
```python
if user_role.scope_type is not None and scope_type is not None and scope_type not in ("*", "own"):
```

**Do not revert or weaken this condition.** Adding new non-structural scope semantics requires updating both the condition AND the docstring's item list.

**Regression tests** (must stay green):
- `test_can_scope_wildcard_request_accepts_scoped_user_role` (Phase 7.1)
- `test_can_scope_own_request_accepts_scoped_user_role` (Phase 8b.2)

### Service-layer direct audit for methods called outside page-state handlers

Announcement service methods (`create_announcement`, `withdraw_announcement`, `attach_file_to_announcement`, `create_auto_announcement`) emit audit via `write_audit_row` directly — not via the `@audit_action` state decorator. This follows the M7 approval-engine pattern.

**Why**: These methods are called from both page-state handlers (which have `@audit_action`) AND from background hooks (`_run_post_approval`). If audit were delegated to the decorator, the background-hook call path would silently produce no audit row. The service-level call is the only path guaranteed to run in all invocation contexts.

**Pattern**: emit `write_audit_row` inside the `with open_session()` block, AFTER the DB write succeeds, with `before_snap` captured before the write and `after_snap = audit_snapshot(entity)` called while the entity is still attached.

### Publish-delay window semantics (Phase 8c)

`AnnouncementCategory.publish_delay_seconds` (0–86400) controls a pending window:
- **`scheduled_at`** is set to `now + timedelta(seconds=category.publish_delay_seconds)` by `create_announcement`.
- During the window (`scheduled_at > now`): announcement invisible to recipients, withdrawable by composer.
- After the window (`scheduled_at ≤ now`): visible to recipients, withdraw blocked.
- **Auto-announcements bypass the delay**: `create_auto_announcement` always sets `scheduled_at = now`.

This is NOT a cron-based scheduler. The "publish" boundary is enforced lazily at query time by the `scheduled_at ≤ now` filter in `AnnouncementRepository.list_visible_to_user`. No background job is needed.

### Seed re-run after adding new permission triples

After any commit that adds new `(resource, action, scope)` triples to `scripts/seed.py`,
run `uv run python scripts/seed.py` against the dev DB BEFORE the next manual walkthrough.
Skipping this step causes `PermissionDenied` for every user for the new resource even when
the code and seed content are syntactically correct. This is the third occurrence of this
bug class: M3 (course:delete:*), M8.1 Phase 8 (leave_request_admin:write:*), and M9 Phase 5 (announcement permissions).

## Current milestone
**M10 (Faculty Module) — in progress on branch `m10-faculty`. M9 (Announcement Module) closed 2026-06-14, merged as 2d819c4, tag m9-close on afc1f4b. Post-merge docs commit `7842eb9`. Phase P1 shipped (`27d323a`) + P1.1 fix (`f2b671b`) + P2 photo upload (TBD); Phase P3 next.**

**Previous milestone:** M9 closed 2026-06-14, merged as 2d819c4, tag m9-close on afc1f4b.

This line is the source of truth for "where are we." Before opening a milestone-completing PR, Claude Code MUST:
1. Grep this file for "Current milestone" and update both occurrences (the top status line and this section).
2. Verify the update is part of the same commit as the gate-passing work — never a separate PR.
3. Confirm the update matches the milestone numbering in §12 of the RFP, not a guess.

See **Milestone discipline** above for the full closing checklist.