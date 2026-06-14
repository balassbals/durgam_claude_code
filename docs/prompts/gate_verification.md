# Milestone Gate Verification Ritual

Use this checklist at every milestone gate, in order. Do not skip
steps. The cost is roughly 30–45 minutes per milestone. The benefit
is that no milestone ships with a hidden gap.

## Before you start

The agent has reported "milestone complete." You have NOT yet
approved the gate. The work below is what turns the agent's claim
into a verified close-out.

## Step 0: Confirm everything is pushed

In your working directory:

```bash
git status
```

Should report "nothing to commit, working tree clean."

```bash
git log origin/<branch>..HEAD --oneline
```

Should be empty (all local commits pushed).

If either shows pending work, the agent has uncommitted or unpushed
changes. Resolve before continuing.

Then free Docker ports for the clone:

```bash
docker compose down
```

Confirm no DURGAM containers are running:

```bash
docker ps
```

Should show none.

## Step 1: Fresh clone

Clone to a temporary location you don't normally use:

```bash
cd /tmp
rm -rf durgam-m<N>-verify
git clone <repo-url> durgam-m<N>-verify
cd durgam-m<N>-verify
git checkout m<N>-<branch-name>
uv sync
docker compose up -d db redis mailpit minio
uv run alembic upgrade head
uv run python scripts/seed.py
```

In a second terminal, in the same clone directory:

```bash
uv run reflex run
```

Wait for "App running at http://localhost:3000".

## Step 2: Run the test suite three times

```bash
DURGAM_E2E=1 uv run pytest tests/e2e/ -q --no-cov
DURGAM_E2E=1 uv run pytest tests/e2e/ -q --no-cov
DURGAM_E2E=1 uv run pytest tests/e2e/ -q --no-cov
```

All three must pass with the same count. If any run fails or shows
a different count, stop and report — the suite is non-deterministic
and the gate is not passed.

## Step 3: Seeded-user pristine check

After the three runs:

```bash
docker compose exec db psql -U durgam -d durgam -c \
  "SELECT username, must_change_password, failed_login_count,
   locked_until, is_deleted FROM users
   WHERE username IN ('sys_admin', 'dean_sci', 'firstlogin_user',
                       'inactive_user', 'student_001',
                       'registrar_user', 'hod_dmacs',
                       'iqac_user', 'director_psn', 'dean_sw')
   ORDER BY username;"
```

For each row verify:
- `failed_login_count` is 0
- `locked_until` is NULL
- `is_deleted` is false
- `must_change_password` matches the seed (true only for
  firstlogin_user; false for others).

If any seeded user is mutated, a test is using a seeded user where
it should use an ephemeral one. Gate not passed.

## Step 4: Manual use as each affected role (15 minutes)

This is the step most often skipped and the one that catches the
most real issues. Do not skip it.

Open `http://localhost:3000/login` in your browser.

For each role the milestone touches (per the milestone's RFP entry):

1. Log in as a seeded user holding that role.
2. Complete each flow the milestone says is now possible, using
   ONLY UI navigation — no typing URLs. If you can't find a way
   to reach a flow through the UI, that's a gap.
3. Log out.

Examples:

- **M1**: log in as sys_admin (reach logout, change-password); log
  in as firstlogin_user (verify forced redirect); navigate to /
  unauthenticated (verify redirect to /login).
- **M2**: log in as sys_admin (create user, assign role, soft-delete
  user, verify the new user can log in).
- **M3**: log in as Registrar (browse departments, schools, programs).
- **M5a**: log in as Registrar (upload letterhead, download it);
  log in as student and confirm the download endpoint denies access.
  **Important:** the download endpoint is on the backend
  (`localhost:8000/api/files/<id>` in dev). In production the
  frontend and backend share one origin, but in dev they run on
  separate ports. Download links rendered by the app use
  `DOWNLOAD_PREFIX` to target the correct origin automatically.
  When testing download denial manually (e.g. pasting a URL into a
  browser), use the backend port (`:8000`), not the frontend
  (`:3000`) — the frontend dev server does not forward
  manually-typed API paths. Expect 403 (not 404) for
  purpose-restricted files the student lacks permission for.
- **M8**: log in as faculty (apply for CL, view balance); log in as
  director (see pending approvals, approve one).

Note any issue. Write them down. The agent will need them if there
are gaps.

## Step 5: Three-width responsiveness check (5 minutes)

> **NOTE (M3+):** Three-width responsiveness verification is deferred
> to the UI Polish milestone per `docs/ui_polish_backlog.md` and
> `tech_debt.md` TD-007. For M3 onward, this step is reduced to:
> confirm the desktop layout (1280px) works correctly for all
> milestone-introduced pages. Mobile (360px) and tablet (768px)
> verification will be performed at the UI Polish milestone across
> all accumulated modules.

Open browser DevTools (F12). Click the device-toolbar icon.

For each viewport in turn — 360px, 768px, 1280px:
- Open the home page (`/`).
- Walk through one main flow of the milestone.
- Check: nothing overlaps; no horizontal scroll; no text cut off;
  navigation reachable (drawer below 768px).

## Step 6: Mailpit check (if milestone involves email)

Open `http://localhost:8025`. Trigger any email-sending action from
the manual flow. Refresh Mailpit. Confirm the email arrived and
looks correct.

## Step 7: UX Charter walk-through (5 minutes)

Open `docs/ux_charter.md`. For each section that applies to this
milestone, confirm satisfaction:

- §1 Application shell: header, logout, account link, footer
  present?
- §2 Navigation: every page in the milestone reachable from the
  home page by clicking?
- §3 Forced flows: any required forced state correctly handled?
- §4 Confirmation patterns: destructive actions confirm; saves
  don't.
- §5 Loading/empty/error states present where lists or async data
  appear?
- §6 Responsiveness: passed in Step 5 above.
- §7 Theme: no hard-coded colors in new components.
- §8 Accessibility: keyboard-navigable; focus visible; labels
  present.

Refer to UX Charter §12 for what is explicitly NOT required at
this milestone.

## Step 7a: Errata coverage (1 minute)

Open `docs/rfp_errata.md`. For each erratum that names this
milestone as the "Disposition" milestone, confirm the disposition
has been implemented and verified. The errata sit alongside the
RFP as binding requirements; a milestone closing without addressing
its named errata is incomplete, even if the RFP gate clause passes.

## Step 8: Decision

If Steps 2–7 all passed without gaps:
- The gate is verified.
- Proceed to merge (see milestone close-out procedure below).

If anything failed or you noted gaps:
- The gate is NOT passed.
- Report findings to the agent. Do not merge.
- After the agent's fix, repeat Steps 1–7 in full. Do not partial-
  verify.

## Step 9: Cleanup (after gate is verified)

```bash
cd /tmp/durgam-m<N>-verify
docker compose down -v
cd /tmp
rm -rf durgam-m<N>-verify

cd <your-normal-project-dir>
docker compose up -d db redis mailpit minio
```

## Step 10: Merge to main, tag, open next milestone

In your normal working directory:

```bash
git checkout main
git pull
git merge --no-ff m<N>-<branch-name> -m "Merge M<N>: <milestone-name>"
git tag -a M<N>-<short-name> -m "M<N> gate passed"
git push origin main
git push origin --tags
```

Open the next milestone branch with the milestone-line update as
the first commit:

```bash
git checkout -b m<N+1>-<short-name>
```

Edit `CLAUDE.md`: change both occurrences of "Current milestone" to
the next milestone. Then:

```bash
git add CLAUDE.md
git commit -m "chore(M<N+1>): open milestone"
git push -u origin m<N+1>-<short-name>
```

Take a break. Do not start the next milestone's planning in the
same session.

## Lessons from M5b — what the ritual taught

M5b required six gate-fix rounds after the initial "ready to ship" report. Each round caught real bugs that the unit/integration suite did not catch. These patterns are the institutional memory worth keeping for M6 and beyond.

### 1. The manual ritual is non-negotiable and catches a specific class of bugs

Tests pass on every metric the agent measures (count, determinism, no crashes), yet the page can still be broken at the user-visible layer. Every round, the manual ritual found things tests missed:
- Pages that crashed on load for one role family (Round 3: UserRole.is_deleted)
- Save flows that silently dropped file persistence (Round 5: FF1 — file_ids NULL on create path)
- Permission gates that worked in isolation but had an upstream guard blocking the user before reaching them (Round 4: CC3 — _admin_guard rejecting non-sysadmins before per-resource gates ran)
- URLs that were structurally correct but failed at the framework layer (Round 6: rx.download URL validation)
- Notification recipients that resolved to the wrong set (Round 2 + Round 3 Z1: RoleEmail config vs. User+UserRole join; phase-3 role list expanded)
- Features the spec described but the build silently substituted with a simpler equivalent (Round 5 FF4: CSV download instead of DOCX-on-letterhead)

These can only be caught by a human clicking through with domain knowledge against fresh seeded state.

### 2. PASS claims require evidence, not assertion

The Round 4 "Pre-existing test isolation issue" claim was technically true but obscured a real regression that pushback exposed. The "not reproducible" finding for H1 in Round 2 was wrong and caused U1 in Round 3. The CC1 download bug was claimed PASS twice (Rounds 3 and 4) before Round 5's root-cause investigation found the real fault.

For M6 onward: every PASS claim in a build report must be backed by either (a) file:line evidence showing the actual change, or (b) a test that exercises the user-visible path (state handler → DB row → loaded row dict → rendered output) — not just a single isolated layer.

When a manual verification finding conflicts with a build report, the build report is wrong by default. The remediation is to require the agent to produce concrete evidence (file:line + DB query + state inspection + execution trace) BEFORE planning any fix.

### 3. Multi-step user flows need end-to-end tests

Tests that exercise a single layer (just the service, just the state handler, just the page) can all pass while the integrated flow is broken. Counsellor save → load → render hid a file-id-dropping bug across multiple rounds because no test exercised the full path.

For M6 onward: any feature involving save-then-display, create-then-approve, upload-then-confirm, or schedule-then-notify needs at least one integration test that runs through the state-handler layer end-to-end and inspects the resulting DB row + the loaded row dict + the rendered UI condition. The Round 5 test pattern (tests/integration/test_m5b_counsellor_file_ids.py) is the template.

### 4. "Pre-existing" requires a true baseline

"This failure was pre-existing" claims require demonstrating the failure on truly clean baseline — both code AND schema matching the prior commit. `git stash` doesn't unwind migrations; comparing stashed code against current schema is not a valid baseline.

For M6 onward: any "pre-existing failure" diagnostic must include `alembic downgrade` to the prior schema head before the comparison run, OR a fresh DB with only the baseline migrations applied. State this explicitly in the report.

### 5. Specs imply features the agent may silently substitute

Round 5's FF4 found the faculty mentor download had been built as CSV when the Y1 spec called for DOCX-on-letterhead. The agent's Round 3 report marked Y1 PASS because download_roster existed and produced a file; it didn't verify the file type matched the spec. Similar pattern: agent's initial dean-role design ignored the M5a decision that letterhead is per-role no scope.

For M6 onward: spec divergences — where the agent picks a simpler-or-different implementation than the spec asked — must be flagged in the build report ("I built X but the spec said Y; here's why"). Silent substitution is the failure mode to watch for.

### 6. Decisions live in authority files, not chat

Round 2 found M5a UI decisions (role_code dropdown, letterhead per-role, etc.) that were made in conversation but never written to an authority doc. The build correctly forgot them. Conversations have no persistence; only the errata, the milestone docs, and the configuration doc do.

For M6 onward: every binding decision goes into an authority file (errata, milestone doc, or configuration doc) AT THE TIME OF THE DECISION. "We discussed it in chat" is not record-keeping.

---

## Lessons from M6a — audit emission hardening

M6a hardened 82 `@audit_action`-decorated handlers across 28 state files so every
state-changing operation produces a complete audit row with `resource_id`,
`diff_json` (before/after diffs), `actor_roles_json` (full role snapshot at action
time), and sensitive-field redaction. Standard ritual results:

- **Unit tests**: 511 passed (including 31 new audit unit tests) ✓
- **M6a-specific integration tests**: 82 passed (70 emissions + 5 scope + 6 redaction + 1 check_permission) ✓
- **Full integration suite**: 325 passed, 0 failed ✓
- **Migration forward/reverse/forward**: clean ✓
- **E2E 3× green**: ✓
- **Manual UI walkthrough**: ✓
- **DB spot-checks**: zero empty diffs for state-changing actions, schema columns and GIN index verified ✓

### 1. Build the census from grep, not from memory

`check_permission|user` (the permission check widget in
`durgam/pages/shared/permission_check_widget.py`) was missed in the initial census of
68 action/resource pairs. It was caught only by the post-walkthrough SQL spot-check
query (`SELECT count(*) ... WHERE diff_json IS NULL`), not by any test — because no
test existed for a pair that wasn't in the census.

**Pattern for future milestones**: build the emission census from a fresh
`grep -r "@audit_action" durgam/` enumeration of all decorated handlers, not from
memory or from the plan's initial list. Cross-reference the grep output against the
test file's test names before declaring coverage complete.

### 2. GIN containment query psycopg3 syntax collision

The SQL `WHERE actor_roles_json @> :pattern::jsonb` fails with psycopg3 because
`::` in `::jsonb` collides with the `:pattern` named-parameter prefix. The fix is
`cast(:pattern AS jsonb)` — standard SQL cast syntax that avoids the PostgreSQL
shorthand entirely. Caught at gate step 7 (M6a-specific tests).

**Rule**: in any `text()` query that uses psycopg3 named parameters, never use
PostgreSQL `::type` cast syntax. Use `cast(:param AS type)` instead.

### 3. Per-pair test scope, not per-category

The initial plan called for ~40 per-category emission tests. RFP §13.2 requires
per-operation audit coverage, not per-category. Caught at plan review and corrected
before build — the final suite has one test per (action, resource) pair (71 tests
covering 68 emitting pairs plus 4 login_failed reason codes).

### 4. docker-compose app container conflicts with host-Reflex workflow

`docker-compose.yml` includes a `web` service that runs the Reflex app in a
container. Its `uv run reflex run` creates `.venv/` on the shared host-mount volume
as root, conflicting with the host-Reflex fresh-clone workflow. Worked around by
starting only dependency services (`docker compose up -d db redis mailpit minio`).
Captured as E-011 in `docs/rfp_errata.md` and TD-018 in `docs/tech_debt.md`.

### 5. No-op saves produce legitimately empty diffs

When a user opens an edit form and saves without changing any value, `before == after`
and the diff function produces `{}`. This is correct behavior — the audit row records
that the action was attempted and authorized; the empty diff correctly communicates
"no fields changed." Gate criterion clarified: "Zero empty diffs for state-changing
actions, excluding no-op saves where before == after." Documented as Risk Register
item (i) in the plan doc.

### 6. Verify claims by naming each artifact

The agent initially claimed "all 4 login_failed reason-code tests exist." Asking
"name each test" revealed only 1 existed (`invalid_credentials`); the other 3
(`not_found`, `inactive`, `locked`) were added in response. The discipline of
requiring the agent to enumerate each artifact by name — not just assert a count —
catches gaps that aggregate claims hide.

---

## Lessons from M6b — audit log read UI

M6b built the admin-only audit log viewer (filter strip, paginated table, detail
drawer, CSV export) plus the resource label resolver. The gate ritual required
five hotfix rounds after the initial "ready to ship" report. Each hotfix exposed
a pattern worth institutionalising.

### 1. Agent silent corrective commits

During M6b hotfix prompts, the agent made two undocumented commits in adjacent
areas (058fca8 — explicit setters for AuditLogState filter vars; 51ee852 — Reflex
component build errors including padding conflict, foreach typing, and drawer handler
naming). Neither commit appeared in the agent's post-fix report. They were discovered
only by scanning `git log` after the round.

**Discipline**: after every agent fix prompt, run `git log --oneline -5` and compare
against the agent's report. Silent corrective commits during Reflex compile-pressure
are common — the agent fixes one error, encounters cascading errors, and commits
additional fixes without reporting them.

### 2. Reflex hot-reload misses JSX-level changes

Adding `aria_label` attributes to icon-only buttons did not reach the running app via
Reflex's hot reload during M6b gate ritual. The old rendered DOM persisted until the
dev server was restarted.

**Discipline**: after any UI prop change (aria, role, data-testid, style-only props on
existing components), Ctrl+C the Reflex dev server and restart. Do not trust hot reload
for prop-level changes. This applies to all future milestones.

### 3. Test selectors written without rendered-DOM grounding fail strict mode

The agent's `get_by_text("Audit Log")` collided with the new nav link because both
the sidebar nav entry and the page heading rendered the same string. Playwright's
strict mode rejected the ambiguous match. Similarly, `get_by_text("OCCURRED AT")`
failed because the DOM text is "Occurred at" — CSS `text_transform: uppercase` is
visual only and does not affect the DOM text node that Playwright matches against.

**Discipline**: when adding nav entries that duplicate a page heading's text, test
selectors must qualify by role (`get_by_role("heading", ...)`) or by element scoping.
Column headers and field labels that use CSS text-transform render original-case in
the DOM. Always verify selectors against the source code's literal strings, not
against the visual appearance of the rendered page.

### 4. Radix Select.Item forbids empty-string values

`rx.select.item("...", value="")` crashes the page with a Radix UI runtime error.
Radix reserves empty string as the "clear selection" sentinel internally; passing it
as an explicit item value triggers a validation exception at compile time.

**Discipline**: use a non-empty sentinel (`"all"`) for "no filter selected" items in
`rx.select`. All filter state vars that feed a `rx.select` must default to `"all"`,
not `""`. The query layer treats the sentinel as "skip this filter". This pattern is
also documented in CLAUDE.md under "Patterns established at M6b."

---

## Lessons from M7 — approval requests

### 1. "Deviations: None" on expanded scope is itself a deviation

During M7 Phase 3 grant fix, the agent surveyed 4 channel role codes and then granted
the permission to 7 roles, declaring "Deviations: None." The expansion (adding
REGISTRAR_OFFICE / VC_OFFICE / DEPUTY_REGISTRAR beyond the surveyed set) was
judgment-call scope creep that should have been flagged.

**Discipline**: any output set larger or smaller than the spec'd input set is a
deviation, regardless of whether the expansion is "obviously right" — it requires
explicit disclosure and product-owner sign-off.

### 2. Reflex auto-setters throw runtime errors; always define explicit manual setters

Reflex's implicit auto-setter mechanism (`set_<var>` generated from state var
declarations) is unreliable in this stack — relying on it produces runtime errors
when forms try to bind via `on_change`.

**Convention going forward**: every state var that participates in a form binding
(`on_change`, `value` binding for inputs/selects/textareas) must have an explicit
`def set_<var>(self, value): self.<var> = value` method on its State class. Caught
and fixed in M7 across `SubmitRequestState` NRF fields and previously in M6b for
`AuditLogState` filter vars.

---

## Why this ritual exists

Tests verify what is tested. Manual use verifies what users actually
experience. Past milestones in this project shipped passing tests
with real UX gaps because no human used the application as a normal
user before the gate was closed. This ritual prevents that pattern
from recurring.

At every milestone gate from M1 onward, the administrator personally
performs this ritual. It is not optional and not delegable to the
agent — only a human can judge whether the result is genuinely
usable.

---

## M8 lessons

### 1. Always run pytest with scoped paths, not bare `pytest`

Running bare `pytest` (no path argument) triggers alphabetical discovery:
`e2e/ → integration/ → property/ → unit/`. The `seeded_db_engine` session fixture
is initialized when integration tests run, populating `durgam_test` with seed data.
Unit tests that run after (e.g., `test_leave_sanction_rule.py`) assert a clean DB and
fail on the pre-existing seed rows. Running `pytest tests/ --ignore=tests/e2e/`
avoids the cross-contamination. See TD-034.

**Lesson**: always invoke as `uv run pytest tests/ --ignore=tests/e2e/ -q --no-cov`
for the gate-passing run. Never rely on bare `pytest` output as gate evidence.

**Coverage**: this command runs unit, property, and integration tests. As of M9 Phase 2.1, 22 pre-existing unit test failures are documented in TD-044 (see `docs/tech_debt.md`). They are known and tracked — they do not block the gate, but the failure count must not increase. Compare each run's failure list against TD-044's enumeration; any new failure is a regression.

### 2. Detached-HEAD risk on fresh-clone gate ritual

The fresh-clone gate ritual (`git clone <repo>`) puts git in a detached-HEAD state
if the clone target is a branch not yet pushed to remote. Alembic migrations discovered
via `--autogenerate` against a detached HEAD will not include the M8 migration files
if the branch was checked out incorrectly.

**Lesson**: after fresh clone, always run `git checkout <branch>` explicitly before
`uv run alembic upgrade head`. Verify `alembic current` shows the expected M8 head
revision, not an earlier head.

### 3. `docker compose down -v` between walkthroughs

Running multiple gate walkthroughs in the same day without `docker compose down -v`
between them leaves the seed data in the DB. Re-running `scripts/seed.py` is idempotent
for most entities, but some leave balance rows (e.g., CL opening balance after a
walkthrough debit) may show a non-initial state on the second walkthrough. Symptom:
"CL balance is 7 instead of 8" on the second run.

**Lesson**: between full gate walkthroughs, run `docker compose down -v && docker compose up -d`
to get a clean volume, then re-apply migrations and seed. This also validates the
migration from-scratch path as a bonus.

### 4. Notification smoke check — `SELECT COUNT(*) FROM notifications`

After completing the submit → approve cycle in a walkthrough, run
`SELECT COUNT(*) FROM notifications;` in psql. At M8 close this returns 0 due to TD-037.
Before TD-032 (notification dispatch worker) lands, add this check to gate verification
so the defect is caught immediately if it regresses to producing rows or advances.

---

## M8.1 Gate Lessons

### TD-034 full-suite false failures

Full-suite `pytest` invocations produce 56 consistent false failures in `tests/integration/test_m5b_purchase_rules.py` due to `seeded_session`/`db_session` fixture-pool interaction. The failures are pre-existing (filed at M8) and unrelated to M8.1 changes.

**Workaround for M8.1 gate:** Use scoped invocations only:
```bash
uv run pytest tests/unit/ -q --no-cov
uv run pytest tests/integration/test_leave_credit_policy.py \
    tests/integration/test_leave_balance_import_integration.py \
    tests/integration/test_leave_balance_import_fixture.py \
    tests/integration/test_leave_withdrawal_integration.py \
    tests/integration/test_leave_notifications.py \
    tests/integration/test_leave_balance_admin_integration.py \
    tests/integration/test_leave_request_admin_integration.py -q --no-cov
```

Never count or compare a bare full-suite run for M8.1 gate evidence. The 56 false failures inflate the failure count and can mask real regressions.

### Seed-after-permission-change

Every milestone that adds new permission triples to `scripts/seed.py` must run `uv run python scripts/seed.py` against the dev DB **before the manual walkthrough**. Missing this step produces `PermissionDenied` for every user for the new resource even when the code is correct. Surfaced at M8.1 Phase 8 when `leave_request_admin:write:*` was seeded in the commit but not re-applied to the running dev DB.

**Checklist addition from M8.1:** After any commit that touches `scripts/seed.py`, run `uv run python scripts/seed.py` before the next walkthrough step.

### Reflex API hotfix patterns (M8.1 Phase 4)

Three Reflex 0.9.x idioms that produced failures invisible to pytest:

1. `nav_shell()` takes **no positional arguments**. Wrong: `nav_shell(content)`. Correct: `rx.vstack(nav_shell(), content, ...)`.
2. `rx.select.root` uses **`on_change`**, not `on_value_change`. `on_value_change` fires on internal Radix events and does not pass the selected value to the handler.
3. **`rx.input(type="hidden")` renders visibly** in Reflex 0.9.x. Carry IDs in explicit state vars, not hidden form inputs.

When a Reflex callback "doesn't fire" or a form field "sends the wrong value," check the prop name against the Reflex 0.9.x changelog before investigating the state/service layer.

### CC reporting reliability

Treat CC's test suite totals as approximate claims, not facts. Across M8.1 Phases 4.1–8, CC delivered under-spec reports (missing verbatim outputs). In Phase 8 CC reported "1223 passed" when the actual count was approximately 1167 passed + 56 failed (TD-034 contamination). Bala runs the scoped invocations above himself for ground truth at gate time.

### Manual walkthrough is THE primary quality gate

Across M8.1, the manual walkthrough caught real defects that green test suites did not:

- Phase 4 Reflex API bugs (three hotfixes — `1a6c00f`, `625f584`, `6589fce`)
- Phase 4.1 fixture defect (`leave_balance_import_sample.csv` referenced a seeded username not present in test DB)
- Phase 7 sticky-column non-functionality (two failed implementation approaches)
- Phase 8 Bug A: `cancel()` guard too narrow — `PermissionDenied` for leave_request_admin role
- Phase 8 Bug B: `approved → cancelled` produced `state = "withdrawn"` instead of `"cancelled"`
- Phase 8.3: UI permitted impossible state transitions for elapsed-window approved leaves

The pattern from M5b/M6a/M7/M8/M8.1 is consistent: green pytest is necessary but not sufficient. The walkthrough is the ground-truth quality gate for integrated behavior.

---

## M9 Gate Lessons

### Baseline discipline — 3-run determinism requirement (TD-063)

The "61 failed, 1317 passed" baseline was observed consistently across multiple runs from Phase 7 onward. The ordering-sensitive failures (seeded_db_engine contamination of db_session tests) are pre-existing and stable. Any new failure that appears in some runs but not others is a flake, not a baseline failure — investigate before adding it to the failure allowlist.

**Protocol (Phase 8b.2)**: run `pytest tests/ -q --no-cov --ignore=tests/e2e/` three consecutive times. If pass/fail counts vary, identify the varying tests before proceeding.

### Raw output mandate (TD-058)

Multiple M9 phase reports paraphrased test suite totals rather than pasting verbatim `pytest` output. The correct gate verification command:

```bash
uv run pytest tests/ -q --no-cov --ignore=tests/e2e/ 2>&1 | tail -3
```

Paste the raw output line (e.g., `61 failed, 1317 passed, 72 warnings in 181.42s`). Do not paraphrase or compute from memory. Bala runs this himself at gate time; CC reports serve as the first-pass signal, not the ground truth.

### Decorator action ↔ seeded permission must match (TD-053 / Phase 8b.1)

Every `@require_role(action="X", resource="Y", scope="Z")` must have a matching `(Y, X, Z)` triple in `scripts/seed.py`. The meta-test `test_announcement_decorator_actions.py` checks existence. Run it in isolation before claiming a phase is complete:

```bash
uv run pytest tests/integration/test_announcement_decorator_actions.py -v
```

Also verify that `can()` resolves to `True` for the canonical scoped user for each `scope="own"` or `scope="*"` decorator — data presence ≠ runtime resolution (TD-053).

### Seed re-run after permission changes (Phase 8b.1 / M8.1 Phase 8)

After any commit that adds new permission triples to `scripts/seed.py`, run:

```bash
uv run python scripts/seed.py
```

before the next manual walkthrough. Missing this step causes `PermissionDenied` for every user for the new resource, even with syntactically correct code and seed content.

### `can()` bypass semantics for non-structural scope types

`scope_type="*"` and `scope_type="own"` are **not** structural role-scopes. When a handler is decorated with either, the caller's `UserRole.scope_type` is not used to filter out the role — only the permission grant is checked. This is encoded in `durgam/auth/permissions.py` line 67:

```python
if user_role.scope_type is not None and scope_type is not None and scope_type not in ("*", "own"):
```

Scoped roles (DIRECTOR with scope_type="campus", HOD with scope_type="department") CAN satisfy a `scope="*"` or `scope="own"` permission check. The handler body must separately enforce ownership (for "own") or global applicability (for "*"). This invariant must be preserved when modifying `can()` in future milestones.
