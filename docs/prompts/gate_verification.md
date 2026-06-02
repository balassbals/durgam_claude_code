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
