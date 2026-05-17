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
                       'inactive_user', 'student_001')
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
- **M8**: log in as faculty (apply for CL, view balance); log in as
  director (see pending approvals, approve one).

Note any issue. Write them down. The agent will need them if there
are gaps.

## Step 5: Three-width responsiveness check (5 minutes)

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
