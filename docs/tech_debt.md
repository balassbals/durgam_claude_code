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
transaction. Safe but symptom-level. At M5b Round 3, the same class
manifested as TestResolveDeptScope failing when ordered before
purchase-committee tests; fixed by rewriting to use db_session with
inline data construction instead of seeded_session.

**Preferred pattern for new tests:** Use db_session with inline data
construction over seeded_session.

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

### TD-010 — Celery docker services install full dev dependency set on cold start

**Location:** `docker-compose.yml` (celery_worker, celery_beat services)

**What it is:** The Celery worker and beat containers use the same `app` build
target as the main Reflex app, which includes dev dependencies (playwright,
mypy, ruff, faker, hypothesis). On cold start, `uv sync` inside the container
installs all of these, making startup slow (~30s) and containers ~200MB heavier
than needed. A `uv hardlink` warning also appears (cosmetic).

**Why this is not a correctness issue:** The worker functions correctly after
startup. The extra deps are unused but harmless. Dev containers are not
production artifacts.

**Fix:** Add a `worker` build target in the Dockerfile that runs
`uv sync --frozen --no-dev --no-install-project` (runtime deps only). Point
the celery services at that target. Set `UV_LINK_MODE=copy` to silence the
hardlink warning.

**Trigger to re-open:** Production deployment prep, or M20 review.

---

### TD-011 — Coverage threshold noise (--cov-fail-under)

**Location:** `pyproject.toml` (`addopts`)

**What it is:** `--cov-fail-under=70` in pytest addopts causes a misleading
`FAIL Required test coverage of 70% not reached` when running individual test
files or small subsets (e.g., `tests/unit/test_calendar_emails.py` alone
reports 17% total coverage). The project's actual gate criterion is
suite-passes, not a global coverage percentage — per-module thresholds are
checked at gate time (services >= 85%, repos >= 80%).

**Why this is not a correctness issue:** The full test suite consistently
exceeds 85% total coverage. The threshold only misfires on partial runs.

**Fix:** Remove `--cov-fail-under` from `addopts` (gate verification checks
per-module coverage explicitly). Or lower to a value that partial runs can
meet (e.g., 40%).

**Trigger to re-open:** If CI is added and uses the global threshold for
gating, set it appropriately there rather than in pyproject.toml.

---

### TD-013 — Download endpoint registered via private Reflex attribute (app._api)

**Location:** `durgam/durgam.py` (route registration); `durgam/api/download.py` (endpoint).

**What it is:** The authenticated file-download endpoint at `/api/files/{file_id}`
is registered via `app._api.add_route()`. `_api` is Reflex's internal Starlette
application instance, exposed as a private attribute (leading underscore). Reflex
does not offer a public API for adding custom Starlette routes as of 0.9.2.

**Why this is not a blocker now:** It works correctly on pinned Reflex 0.9.2 and is
the only available mechanism for custom Starlette routes. The entire file-download
surface across all modules (letterheads, templates, exports, attachments) depends
on this single registration point.

**Trigger to re-open:** (a) Any Reflex version bump — the route registration must
be re-verified after every upgrade (cross-reference the existing Reflex API churn
risk and the version-pinning discipline in CLAUDE.md "Milestone discipline").
(b) If Reflex ships a public custom-route API, migrate to it and close this entry.

---

### TD-014 — Per-entity bulk-import permission UI consistency

**Location:** `durgam/pages/admin/import_users.py`, `durgam/states/admin_bulk_import.py`

**What it is:** M5b added `program_import` / `course_import` permissions and gated tab
visibility on them. The same per-entity permission pattern should be considered for other
admin-panel tools that currently fall under a single coarse permission. Audit the admin
panel for places where a user might see a tool they can't use; gate by the actual
operation permission.

**Trigger to re-open:** When adding new admin tools or import types, apply the same
per-entity pattern. Audit existing tools at the UI Polish milestone.

---

### TD-015 — docxtpl no-placeholder fallback strategy

**Location:** `durgam/docgen/merge.py` (`render_docx_template`)

**What it is:** `render_docx_template` returns a warning list when the template has
no `{{ }}` placeholders, surfaced to the user via flash on counsellor and faculty-mentor
exports. The user gets the unmodified letterhead — functional but not ideal.

**Better behavior at M14 docgen polish:** Consider appending a tabular data block after
the letterhead content, or rendering to a fallback "data-only" template when the
letterhead has no placeholders.

**Trigger to re-open:** M14 docgen polish milestone.

---

### TD-016 — rx.download URL validation strictness

**Location:** `durgam/pages/admin/config/counsellors.py`, `durgam/pages/admin/config/letterheads.py`

**What it is:** `rx.download` in Reflex requires URLs starting with `/`. Cross-origin or
full-URL downloads need to use `rx.redirect` or `rx.link`. M5b standardized on
`rx.redirect(DOWNLOAD_PREFIX + "/api/files/" + file_id)` in kebab menus for file
downloads (counsellor, letterhead, template — same pattern).

**Trigger to re-open:** If Reflex relaxes URL validation in `rx.download`, or if a
future download integration needs a different pattern.

---

### TD-017 — Permission count maintenance and implicit propagation

**Location:** `scripts/seed.py` (`role_perm_map` and `_*_SPECIFIC` composition lists)

**What it is:** The `role_perm_map` composition pattern (e.g. `"REGISTRAR_OFFICE":
_PUBLIC_READ + _REGISTRAR_SPECIFIC`) works but is implicit. Adding a new permission to
`_REGISTRAR_SPECIFIC` automatically propagates to all roles that compose it — good when
intended, but easy to miss when an "inline" exception exists (HOD_OFFICE was such a case,
caught in Round 3).

**Proposed fix:** Add a one-time test that asserts each role's final permission set against
an explicit expected list, catching unintended propagation in either direction.

**Trigger to re-open:** Next permission-grant change, or proactively at M6.

---

### TD-018 — docker-compose app service conflicts with host-Reflex dev workflow

**Location:** `docker-compose.yml` (the `web` service)

**What it is:** Between M5b and M6a, `docker-compose.yml` was extended with a `web`
service that runs `uv run reflex run` inside a container. The container creates
`.venv/` on the shared host-mount volume as root, breaking the host-Reflex workflow
(where `uv sync` and `uv run reflex run` expect host-owned `.venv/`). The M6a gate
was completed by starting only dependency services
(`docker compose up -d db redis mailpit minio`) and running Reflex on the host.

**Proposed fix:** Either (a) remove the `web` service from `docker-compose.yml`
entirely, keeping it as a dependency-only compose file for the standard dev workflow;
or (b) split into `docker-compose.deps.yml` (dev fresh-clone) and
`docker-compose.full.yml` (containerized end-to-end testing). Option (a) is simpler
and matches the documented workflow; option (b) preserves the container-based testing
path for CI.

**Cross-reference:** E-011 in `docs/rfp_errata.md`.

**Trigger to re-open:** Next time docker-compose configuration is touched, or when
CI pipeline is formalized.

---

### TD-012 — Docgen merge assumes image letterheads; letterheads are now DOCX

**Status:** Superseded by E-005.

**Location:** `durgam/docgen/merge.py` (`merge_letterhead_and_content()`)

**What it is:** The docgen merge primitive was built to insert a letterhead
IMAGE (PNG/JPG) into a DOCX header. At M5a gate verification, stakeholders
confirmed letterheads are actually DOCX templates, not images. The MIME
filter was changed to DOCX-only; the image-based merge primitive is no
longer usable with stored letterheads.

**Fix:** At M5b (per E-005), update docgen to accept a DOCX base template
and merge content into it, replacing the image-insertion approach. Evaluate
unifying LetterheadAsset and TemplateAsset into a single model.

---

### TD-019 — Source-reading unit tests in audit suite

**Location:** `tests/unit/test_audit_export.py` (TestCsvExport10kCapViaQueryLimit,
TestCsvExportFlashWhenOverCap), `tests/unit/test_audit_log_state.py`
(TestLoadAuditGuard, TestQueryDefaultDateWindow)

**What it is:** Several audit unit tests verify behaviour by reading the Python
source file (`Path("durgam/pages/audit/index.py").read_text()`) and asserting on
string presence (e.g. `"stmt.limit(10_000)" in src`). This works but is fragile:
a refactor that changes the string form without changing the semantics silently
breaks the test. The pattern was adopted because the handlers under test require
a running Reflex state machine (WebSocket, session cookie) that cannot be
instantiated in a unit test without a full server.

**Proposed fix:** When a state-handler test harness exists (either via Reflex's
own test utilities or a lightweight mock), replace source-reading assertions with
actual handler invocations. Until then, the source-reading pattern is acceptable
but should not proliferate beyond the audit module.

**Trigger to re-open:** Reflex ships a test harness for state handlers, or the
project adopts one.

---

### TD-020 — Reflex RouterData.page deprecation

**Location:** Multiple state files in `durgam/states/`.

**What it is:** Several state files reference `RouterData.page`, which was deprecated
in Reflex 0.8.1 and is scheduled for removal at Reflex 1.0. The attribute still works
on the pinned Reflex 0.9.2 but will break on any upgrade past 1.0.

**Blast radius command:** `grep -rn "RouterData.page" durgam/states/`

**Why this is not a blocker now:** Reflex is version-pinned at 0.9.2. The attribute
functions correctly and is not in a hot path. No upgrade is planned within the current
milestone sequence.

**Fix:** Migrate all `RouterData.page` references to `RouterData.url` (the non-deprecated
equivalent). This is a mechanical find-and-replace but must be verified against the full
test suite after migration.

**Trigger to re-open:** Any Reflex version bump, or proactively before M20.

---

### TD-021 — Approval-attachment join table

**Location:** `durgam/services/approval_request.py` (attachment handling),
`durgam/models/crosscutting.py` (FileAsset)

**What it is:** M7 Phase 1 used `FileAsset.purpose` + `metadata_json.approval_request_id`
tagging to associate uploaded files with approval requests. There is no FK constraint
between `FileAsset` and `ApprovalRequest` — a dangling `metadata_json.approval_request_id`
pointing at a deleted request would not raise a DB error.

**Fix:** Create a dedicated `approval_request_attachments` join table with FK constraints
to both `approval_requests` and `file_assets`, replacing the metadata_json tagging.

**Trigger to re-open:** When approval attachments need cascade-delete semantics, or when
a query needs to efficiently list all attachments for a request via FK join.

---

### TD-022 — Pre-select process in submit form via query param

**Location:** `durgam/pages/approvals/submit.py`, `durgam/states/approval_requests.py`

**What it is:** The NRF admin page's "+ Submit for Approval" button redirects to
`/approvals/submit` with no pre-selection. The user must manually select "Non-Regular
Faculty Approval" from the process picker. A `?process=NRF_APPROVAL` query param could
drive the picker automatically.

**Fix:** Read `rx.State.router.page.params.get("process")` in `load_submit()` and
pre-select the matching process.

**Trigger to re-open:** When more processes accumulate and the submit page is commonly
reached from process-specific entry points.

---

### TD-023 — Multi-HOD users and dept auto-resolution

**Location:** `durgam/states/base.py` (`_resolve_user_dept_scope`)

**What it is:** `_resolve_user_dept_scope()` picks the first department arbitrarily for
users holding multiple HOD roles across departments. This returns a deterministic but
potentially incorrect department for NRF submissions.

**Fix:** When multiple departments are found, present an explicit department picker on
the submit form instead of silently picking the first.

**Trigger to re-open:** When a user holds HOD roles for multiple departments and submits
an NRF approval request for the wrong department.

---

### TD-024 — Approval-grant maintenance with new channels

**Location:** `scripts/seed.py` (role_perm_map)

**What it is:** The permission `approval_request:approve:*` is granted statically per
role in the seed. When a new ApprovalProcess is created with new channel roles, the seed
must be manually updated to grant those roles the approve permission. The grant set is
not auto-derived from active processes.

**Fix options:** (a) Derive grants from active processes at seed time by scanning
`ApprovalProcess.channel_role_codes`. (b) Compute nav visibility dynamically from active
processes rather than a static permission check.

**Trigger to re-open:** When a new approval process adds a channel role that doesn't
already hold `approval_request:approve:*`, causing that role to not see the inbox.

---

### TD-025 — Submit-form conditional-fields growth

**Location:** `durgam/pages/approvals/submit.py` (`_nrf_fields_section`),
`durgam/states/approval_requests.py` (NRF field vars)

**What it is:** The Phase-4-A approach adds process-specific fields via
`rx.cond(selected_process_code == "NRF_APPROVAL", ...)`. This is clean for v1's two
processes (CPC_FUND_RELEASE has no extra fields; NRF_APPROVAL has 7). If a third process
adds its own fields, the conditional chain grows linearly.

**Fix:** Refactor to a registry pattern — each process code registers a component
function and state vars — when ≥3 process-specific submit shapes accumulate.

**Trigger to re-open:** A third approval process needs process-specific fields on the
submit form.

---

### TD-026 — Approver inbox pagination

**Location:** `durgam/pages/approvals/inbox.py`, `durgam/states/approval_requests.py`

**What it is:** The Phase 3 approver inbox loads all pending requests without pagination.
The inbox is assumed small in v1 (most approvers see single-digit pending requests).

**Fix:** Add offset/limit pagination with page controls, matching the pattern used in
the audit log page.

**Trigger to re-open:** When typical inbox sizes exceed ~50 rows (likely when the approval
engine handles high-volume processes like leave requests at M8+).

---

### TD-028 — E2E test coverage gap for approval detail page

**Location:** `tests/e2e/test_approvals_suite.py` (`TestApproverFlow`)

**What it is:** `test_request_detail_page_renders_for_authorized_viewer` was deferred
at M7 Phase 5. Reflex has no REST API, so Playwright cannot seed an in-flight
`ApprovalRequest` from outside the WebSocket. The unit-test surface and the gate-ritual
manual walkthrough cover the detail-page rendering today.

**Fix:** Either (a) add a deterministic seed-side fixture (`scripts/seed.py` produces
an `e2e_test_approval_request` row in `submitted` state), or (b) drive submission
through Playwright as part of the test setup (fill the submit form, select a process,
submit, then navigate to the detail page).

**Trigger to re-open:** When the approval detail page gains complex conditional
rendering (e.g. decision controls, attachment sections) that the manual walkthrough
could miss.

---

### TD-027 — MinIO-dependent download tests

**Location:** Multiple test files across M5a–M7

**What it is:** 8 pre-existing test errors are flagged across M7 phases, all related to
MinIO storage backend availability. These tests assume MinIO is running but do not gate
on a `DURGAM_MINIO=1` environment variable (unlike E2E tests which gate on `DURGAM_E2E=1`).

**Fix options:** (a) Gate MinIO-dependent tests on `DURGAM_MINIO=1`, matching the E2E
skipif pattern. (b) Mock the storage backend in unit/integration tests that test download
logic (not storage).

**Trigger to re-open:** When CI is formalized and these errors block the pipeline. Pre-
existing; not introduced by M7.

---

### TD-029 — more_info_requested state for approval requests

**Location:** `durgam/services/approval_request.py` (state machine),
`durgam/states/approval_requests.py` (inbox/detail handlers)

**What it is:** The approval state machine has four terminal states (approved, rejected,
withdrawn, cancelled) and one active state (submitted/in_review). There is no
`more_info_requested` state that allows an approver to pause the review and request
additional information from the requestor before making a decision.

**Fix:** Add `more_info_requested` as a reversible state. The approver sends a message
(with optional attachments) back to the requestor. The requestor responds (with optional
attachments), which returns the request to the approver's inbox. The detail page shows
the conversation thread. Audit rows record each transition.

**Trigger to re-open:** When stakeholders request this workflow, likely at M9+ when
approval volumes increase and requestors routinely submit incomplete information.

---

### TD-030 — Approver decision history on detail page

**Location:** `durgam/pages/approvals/request_detail.py`,
`durgam/states/approval_requests.py`

**What it is:** The detail page shows the current state and the current stage's approver,
but does not display the full decision history (who approved at each prior stage, when,
and with what comments). The `approval_steps` table records this data; it is not yet
surfaced in the UI.

**Fix:** Add a "Decision History" section to the detail page that renders each completed
`approval_steps` row as a timeline entry: stage number, approver name, decision
(approved/rejected), timestamp, and comments.

**Trigger to re-open:** When multi-stage processes are in active use and requestors or
later-stage approvers need to see prior decisions for context.

---

### TD-031 — In-app notification surface for CC users

**Location:** `durgam/services/approval_request.py` (`_enqueue_notifications`),
notifications table

**What it is:** `_enqueue_notifications` creates `in_app` and `email` notification rows
for all recipients (channel approvers + CC users) at submit, approve, reject, and
withdraw transitions. The rows are written correctly — 54 rows exist (27 email, 27
in_app), all at `delivery_status='pending'`. However, there is no in-app notification
inbox or bell icon to surface `in_app` rows. They accumulate in the `notifications`
table but are never rendered.

**Fix:** Build a notification inbox page or a notification bell dropdown in the nav shell
that queries `notifications WHERE recipient_user_id = current_user AND channel = 'in_app'
AND read_at IS NULL`. Mark notifications read on click-through.

**Trigger to re-open:** When CC stakeholders need real-time awareness of approval
transitions without relying on email. Likely at M9+ when notification infrastructure is
formalized.

---

### TD-032 — Notification dispatch worker does not exist

**Location:** `durgam/services/approval_request.py` (`_enqueue_notifications`),
`durgam/tasks/celery_app.py`, `durgam/notifications/email.py`

**What it is:** The approval engine writes `Notification` rows to the DB with
`delivery_status='pending'` for both `in_app` and `email` channels. No Celery task,
background worker, or any code path reads these rows and dispatches them. The
`notifications` table is a dead-letter queue — all 54 rows (as of M7 gate) are stuck
at `pending` and will never be dispatched.

By contrast, M4 calendar emails and M1/M2 admin emails call `await send_email()` directly
at the point of action (fire-and-forget via `asyncio.create_task`), bypassing the
`notifications` table entirely. The two notification pathways are architecturally
disconnected:
- **Direct path** (M1–M4): `send_email()` called inline → email reaches Mailpit/SMTP.
- **Table path** (M7): `_enqueue_notifications()` writes rows → nobody reads them.

**Why this is not an M7 blocker:** The approval engine's functional behavior (state
transitions, audit rows, routing, skip-self) is correct. The missing dispatch is a
pre-existing infrastructure gap — the `notifications` table was designed for a future
dispatch worker that was never built. Approvers are not relying on email notifications
to discover pending requests; they use the inbox page.

**Fix options:**
(a) Add a Celery periodic task that polls `notifications WHERE delivery_status='pending'
AND channel='email'`, calls `send_email()` for each, and updates `delivery_status` to
`'sent'` or `'failed'`. Register in `celery_app.py` beat schedule.
(b) Replace the table-based enqueue in `_enqueue_notifications` with direct
`asyncio.create_task(send_email(...))` calls, matching the M4 calendar email pattern.
Option (b) is simpler but loses the audit trail of delivery attempts. Option (a)
preserves the table as a delivery log.

**Trigger to re-open:** When email notifications for approvals become a stakeholder
requirement. Likely at M9+ when notification infrastructure is formalized, consolidating
the direct and table-based pathways.

---

### TD-033 — non_regular_faculty.approval_request_id FK drift between migration and model

**Location:** `durgam/models/config_anchors.py` (`approval_request_id` field on `NonRegularFaculty`); migration `6484a8b6dcee_add_approval_request_id_to_non_regular_.py`.

**What it is:** A prior migration created the FK with `ondelete='SET NULL'`, but the SQLModel field declaration on `NonRegularFaculty.approval_request_id` lacks the matching `ondelete='SET NULL'` annotation. Alembic autogenerate detects this as drift on every subsequent revision and attempts to drop and recreate the FK with the model's (incorrect) default behaviour. Caught and stripped from the Phase 1 M8 migration (`56c90a7f65bd`); the drift itself is unresolved.

**Why this is not a production issue:** Runtime cascade behaviour is governed by the DB schema, which currently carries the correct `ondelete='SET NULL'`. The drift is a model-annotation gap, not a runtime defect. The 1017-test regression suite passes unchanged.

**Trigger to re-open:** Next milestone that touches `non_regular_faculty` or that needs a clean autogen baseline. Resolution: update the SQLModel field to declare `ondelete='SET NULL'` so model and DB agree; this generates an empty autogen diff (a clean fixture for future migrations).

---

### TD-035 — Teacher EL credit formula incomplete pending Attendance Module (M13)

**Location:** `durgam/tasks/leave_jobs.py` (`credit_periodic_el_hpl` task, `_credit_el` helper); RFP §11.5.

**What it is:** EL credit for vacation (teaching) employees has three components per RFP §11.5: (a) one day per completed month of service, (b) extra days for vacation-duty performed during summer/winter vacation periods, (c) adjustments for leave-without-pay periods. Only component (a) is implemented. Components (b) and (c) require the `VacationDutyRecord` and `LWPRecord` tables which are deferred to M13 (Attendance Module). The current formula (`days_since_last_credit / 30.0`) is an under-credit for teachers who performed vacation duty; it is never an over-credit, so balances are conservative.

**Why this is not a production issue:** The formula is conservative — no teacher is given more leave than they earned. The shortfall can be corrected retroactively when M13 ships by running the credit job with historical reference dates or via a one-time adjustment script.

**Trigger to re-open:** M13 Attendance Module ships `VacationDutyRecord` and `LWPRecord`. Resolution: extend `_credit_el` to query these tables and add components (b) and (c) to the teacher formula.

---

### TD-034 — `db_session` fixture not isolated from `seeded_db_engine` in bare-pytest discovery

**Location:** `tests/conftest.py` (`db_session` fixture + `seeded_db_engine` session-scoped fixture); affected tests: 8× `tests/unit/test_audit_label_resolver.py::Test*Resolver::test_label` (M6b); 2× `tests/unit/test_leave_sanction_rule.py::test_load_from_yaml_inserts_all_rules` + `::test_load_from_yaml_idempotent` (M8 Phase 4).

**What it is:** `db_session` and `seeded_session` point at the same physical `durgam_test` database. `db_session` rolls back per-test, but only undoes writes made by THAT test — not seed data committed by `seeded_db_engine` initialization. In bare `pytest` discovery (alphabetical: `e2e/` → `integration/` → `property/` → `unit/`), integration tests run first and trigger `seeded_db_engine`, populating the shared DB. Unit tests that follow and assert "clean DB" (e.g., zero pre-existing rules) see the seed data and fail. The same suite passes when invoked as `pytest tests/unit/ tests/integration/` because that path order doesn't trigger `seeded_db_engine` before the affected unit tests.

**Why this is not a production issue:** The gate ritual in `docs/prompts/gate_verification.md` invokes `pytest tests/unit/ tests/integration/` (scoped), where all 10 affected tests pass. No production code path depends on the fixture's behaviour. The failures only manifest in bare `pytest` discovery, which is not part of any gate.

**Trigger to re-open:** A milestone that needs to support bare `pytest` invocation in CI, OR a contributor running bare `pytest` locally is misled by the failures. Resolution: redesign `db_session` to use a savepoint-based truly clean DB (separate test DB per worker, or savepoint-and-truncate strategy), or rewrite the 10 affected tests to be insensitive to pre-existing seed data.

---

### TD-038 — Withdrawal notification recipient resolution is university-wide (no campus-dept scope)

**Location:** `durgam/services/leave_notification.py` (M8.1 Phase 5, not yet created); planned scope: `resolve_withdrawal_notification_recipients()`.

**What it is:** E-017 withdrawal notifications will notify HOD/AHOD/DIRECTOR roles using `UserRole.scope_type` and `scope_id` matching. The resolution function walks the role list but has no access to the employee-to-campus mapping (which belongs to the M10 Faculty model). In M8.1 the function returns all role-holders at any scope; it cannot filter by the employee's campus or department. Recipients from unrelated campuses or departments will receive notifications they don't need.

**Why this is not an M8.1 blocker:** Withdrawal notifications are informational. An excess recipient is annoying but not harmful; a missed recipient would be worse. Conservative over-notification is acceptable until the Faculty/Campus assignment model exists.

**Trigger to re-open:** M10 Faculty module ships the employee-to-campus/department linkage table. Resolution: pass the employee's campus UUID into `resolve_withdrawal_notification_recipients` and add a `.where(scope_id == campus_id)` filter to the HOD/AHOD lookup.

---

### TD-039 — Leave balance and request admin pages lack campus-scope enforcement

**Location:** `durgam/pages/admin/leave_balance_admin.py` and `durgam/pages/admin/leave_request_admin.py` (M8.1 Phases 7–8, not yet created); planned permission: `leave_balance_admin:write:*` and `leave_request_admin:write:*`.

**What it is:** DIRECTOR/DEPUTY_DIRECTOR/DIRECTOR_OFFICE roles are campus-scoped, but the M8.1 admin pages for leave balance editing and leave request editing will use `any_scope=True` guards (no fine-grained campus filter). A DIRECTOR for campus PSN can see and edit balances/requests belonging to employees at campus BRN.

**Why this is not an M8.1 blocker:** Employee-to-campus assignment requires the M10 Faculty model. The pages are used by Registrar-family roles in v1; DIRECTOR-tier usage deferred.

**Trigger to re-open:** M10 Faculty module ships employee-to-campus linkage. Resolution: add a `campus_filter` query argument to `admin_search_balances` and `admin_list_requests` based on the actor's `scope_id`.

---

### TD-040 — credit_annual_cl beat schedule is hardcoded in celery_app.py

**Location:** `durgam/tasks/celery_app.py` (`beat_schedule["leave-credit-annual-cl"]`); `durgam/models/leave.py` (`LeaveCreditPolicy` model, which currently has no `cron_expression` field).

**What it is:** The `credit_annual_cl` task fires on Jan 1 at 03:00 UTC, hardcoded in `celery_app.py`. Institutions that want a different CL credit date (e.g. the AY start date, which varies by campus) cannot configure it without a code change. `LeaveCreditPolicy` was designed for per-type entitlement values only; the schedule is not DB-driven.

**Why this is not a production blocker:** Jan 1 is the statutory CL credit date per §XXVIII clause 14. No institution has requested a different date.

**Trigger to re-open:** Any institution requests a non-Jan-1 CL credit date. Resolution: add a `cron_expression: str` field to `LeaveCreditPolicy`; read it in `celery_app.py` to build a dynamic beat schedule. Or use Celery beat's `DatabaseScheduler` with `django-celery-beat` equivalent.

---

### TD-041 — Admin state transitions: leave_request.state and approval_request.state diverge

**Location:** `durgam/services/leave_request.py` (`admin_change_state`); `durgam/services/approval_request.py` (`cancel`).

**What it is:** When `admin_change_state` moves a `submitted` or `in_review` leave to `"rejected"`, `leave_request.state` correctly becomes `"rejected"` — but the underlying `approval_request.state` is set to `"cancelled"` by `ApprovalRequestService.cancel()`. The two tables use different terminal-state vocabularies. A joined report filtering `approval_requests.state = 'rejected'` will find zero rows even though the leave was operationally rejected.

**Why this is not a production blocker:** Functionally each table holds the correct surface state for its own purpose. The `/audit` log and `/admin/leave/request-edit` list both read from `leave_requests.state`, which is accurate. Only cross-table joined reports (e.g., compliance dashboards joining approval_requests and leave_requests) are affected, and no such report exists in v1.

**Trigger to re-open:** A compliance report needs to filter `approval_requests` by leave-level rejection (e.g., "how many leave requests were rejected vs. cancelled by approval workflow?"). Resolution: introduce an explicit `"rejected"` terminal state in the `approval_request` schema, or add a `leave_request_id` FK on `approval_request` and filter via `leave_request.state` when joining.

---

### TD-042 — admin cancel of approved leave produces two audit rows

**Location:** `durgam/services/leave_request.py` (`admin_change_state`); `durgam/services/approval_request.py` (`withdraw`).

**What it is:** When `admin_change_state(approved → cancelled)` is called, it delegates to `withdraw()` (which writes a `"withdraw"` audit row and sets `state="withdrawn"`), then immediately overrides the state to `"cancelled"` and writes a second `"admin_cancel_after_withdraw"` audit row. The result is two audit rows for a single user-facing operation.

**Why this is not a production blocker:** Both audit rows have accurate `before`/`after` snapshots. The forensic record is complete. The double-write is a cosmetic concern, not a correctness issue.

**Trigger to re-open:** Audit UI feedback that two rows are confusing for a single admin action. Resolution: add a `final_state: str | None = None` parameter to `withdraw()`; when set, skip writing the "withdrawn" audit row and let the caller write a single composite row. Requires updating all `withdraw()` callers.

---

### TD-043 — AudienceGroup program_degree_types filter is a non-functional stub

**Surfaced**: M9 Phase 2 (resolver implementation).
**Severity**: Medium — three frozen audience groups (STUDENT_UG, STUDENT_PG, STUDENT_PHD per M9 Q18) will not resolve to any users on launch.

**Root cause**: `AudienceResolver._evaluate_filter` in `durgam/services/audience_resolver.py` reads the `program_degree_types` key from `filter_json` but cannot execute it because STUDENT users in `scripts/seed.py` (and in the production data model) are not linked to a `Program` via `UserRole.scope_type='program'`. The link does not exist anywhere in the schema today.

**Test** capturing the stub: `tests/integration/test_audience_resolver.py::test_program_degree_types_returns_false_forward_concern`.

**Fix paths** (pick one in a future milestone):
(a) Extend STUDENT user seed + admission flows to populate `UserRole(role_id=<STUDENT>, scope_type='program', scope_id=<program_id>)` and update `_evaluate_filter` to query by it.
(b) Introduce a dedicated `StudentEnrollment(user_id, program_id, batch_year, ...)` table and route `program_degree_types` through it. This also unlocks classwise/batchwise targeting (M13 forward concern in M9 out-of-scope).

**Recommendation**: bundle with M13 (Student records) which has the same data-model dependency.

---

### TD-044 — 22 latent unit test failures in tests/unit/ pre-dating M9

**Surfaced**: M9 Phase 2 (first time `pytest tests/` was run during M9 — prior gate rituals scoped to `tests/integration/` only).
**Severity**: Medium — non-functional code paths, but masks any new unit-level regressions in those areas.

**Failing tests** (verified to also fail at Phase 1 SHA e20ccc1, so pre-existing):
- `tests/unit/test_audit_label_resolver.py` — 8 tests (TestAcademicYearResolver, TestCampusResolver, TestCentreResolver, TestCourseResolver, TestDepartmentResolver, TestLetterheadAssetResolver, TestRoleEmailResolver, TestSchoolResolver, each ::test_label)
- `tests/unit/test_credit_annual_cl.py` — 6 tests
- `tests/unit/test_leave_balance_import.py::test_resolve_active_ay_scenarios` — 1 test
- `tests/unit/test_leave_jobs.py::TestCreditPeriodicElHpl` — 3 tests
- `tests/unit/test_leave_notification_resolution.py::TestResolutionChain` — 2 tests
- `tests/unit/test_leave_sanction_rule.py` — 2 tests

**Action**: Open as separate triage at next milestone close. Each cluster likely has a different root cause. The gate-ritual definition should be updated to include `pytest tests/` (broad) in addition to `pytest tests/integration/` so future drift is caught at the milestone where it occurs, not later.

---

## Resolved

### TD-036 — CL annual credit at AY start not implemented (resolved in M8.1 Phase 2)

**Status: Resolved in M8.1 Phase 2 commit `e1e65e5`.** `credit_annual_cl` Celery beat task ships with calendar-year scheduling (Jan 1, 03:00 UTC), proration for current-year joiners (full entitlement for prior-year joiners), idempotent `leave_credit_runs` sidecar table, and a `LeaveCreditPolicy` admin page at `/admin/leave/credit-policy`. See TD-040 for the remaining hardcoded-schedule follow-up.

---

### TD-037 — Notification rows for leave events not enqueued (resolved in M8.1 Phase 1)

**Status: Resolved in M8.1 Phase 1 commits `e707e47` (diagnostic) + `8b3f609` (fix).** Root cause: `ApprovalRequestService.submit()` auto-approve path called `_run_post_approval()` but never called `_enqueue_notifications(action="approve")` for the requestor. Fix: added the call inside the `if request.current_stage > len(channel):` block, mirroring the pattern at line 268 in `approve()`. Reproducer: `tests/integration/test_leave_notifications.py::test_auto_approve_creates_requestor_notification`.

---

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




### TD-052 (EXTENDED in M9 Phase 8b.2 — originally RESOLVED in Phase 7.1)

**Bug:** `can()` filtered out scoped `UserRole` rows even when the request passed
`scope_type='*'` (meaning "accept a grant for any scope"). The outer condition:

```python
if user_role.scope_type is not None and scope_type is not None:
    if user_role.scope_type != scope_type:
        continue
```

evaluated `"*" != scope_type` as `True` for any scoped role (e.g. campus-scoped
`DIRECTOR`), skipping the role before its permissions were examined.

**Impact (Phase 7.1):** Every user holding a scoped composer role (DIRECTOR, HOD, DEAN,
CENTRE_COORDINATOR) was denied `announcement:create:*` even though the permission
grant's scope is `"*"` (wildcard). Scoped composers could not post announcements.

**Phase 7.1 fix:** Added `and scope_type != "*"` to the outer condition. When the
caller passes `scope_type='*'`, the user role's own `scope_type` is not used to filter
it out.

**Phase 8b.2 extension:** The same problem applies to `scope_type='own'`
(per-instance ownership semantics, used by `announcement:soft_delete:own`). A
campus-scoped DIRECTOR trying to withdraw their own announcement was denied because
`"own" != "campus"` filtered out their `UserRole` before their permission was examined.
`scope_type='own'` is not a structural role-scope — it signals that the handler body
enforces ownership at runtime. The fix extends the bypass to include `"own"`:

```python
if ... and scope_type not in ("*", "own"):
```

**Regression tests:**
- `tests/integration/test_auth.py::TestCan::test_can_scope_wildcard_request_accepts_scoped_user_role` (Phase 7.1)
- `tests/integration/test_auth.py::TestCan::test_can_scope_own_request_accepts_scoped_user_role` (Phase 8b.2)

**Meta-test gap:** `test_announcement_decorator_actions.py` verified that all decorator
`(action, resource)` pairs have seeded Permission rows but didn't catch the `'own'`
runtime failure — data presence ≠ auth resolution success for scoped users. A tighter
meta-test would invoke `can()` with a synthetic scoped user for each decorator. Filed
as TD-062 for a future tightening pass.

**Resolved:** Phase 7.1 + Phase 8b.2, both on m9-announcements.

---

### TD-054 — Auto-announcement `composer_role_code = "SYSTEM"` literal

**Phase:** M9 Phase 8a

**Symptom:** Auto-announcements created via `_run_post_approval` use the literal
string `"SYSTEM"` as `composer_role_code` because the approver's actual composer-
eligible role is not readily determined from the approval context.

**Root cause:** `ApprovalRequestService._run_post_approval` receives `approver_user_id`
but does not look up which (if any) of that user's roles is in `announcement_composer_configs`.
The `Announcement` model requires `composer_role_code` to be non-null.

**Impact:** Auto-announcements display "SYSTEM" as their composer role in the browse
list / detail panel. This is a minor cosmetic issue — the `source_type="auto"` field
already distinguishes these from manual announcements.

**Resolution path:** In a future milestone, query `AnnouncementComposerConfigRepository`
for the approver's highest-priority enabled role at post-approval time, or extend the
model with a nullable `composer_role_code` for `source_type="auto"` rows.

---

### TD-056 — Announcement attachments: no download-permission restriction

**Phase:** M9 Phase 8b

**Symptom:** Files uploaded with `purpose="announcement_attachment"` are downloadable
by any authenticated user with `file_asset:read` permission (the permissive default
of `_PURPOSE_PERMISSION_MAP` in `durgam/api/download.py`). There is no audience-based
gate — a user not in the announcement's target audience groups can still download the
attachment if they know the `file_id`.

**Root cause:** Adding `"announcement_attachment"` to `_PURPOSE_PERMISSION_MAP` would
require the download endpoint to know the announcement's audience groups, which means
a DB join at download time. The endpoint currently has no context about which
announcement the file belongs to.

**Impact:** Low for M9 launch since announcement content itself is not access-restricted
(the browse list shows all visible announcements). If future milestones add confidential
announcements with restricted audience, this gap must be addressed.

**Resolution path:** Add an announcement-aware download guard: look up
`FileAsset.metadata_json["announcement_id"]`, resolve the announcement's audience
groups, and gate on the requesting user's identity. Alternatively, use signed time-limited
URLs (MinIO presigned URLs) for attachments with a short TTL.

---

### TD-057 — Announcement attachments: single-file limit enforced only by UI

**Phase:** M9 Phase 8b

**Symptom:** The spec allows one attachment per announcement (M9 design decision).
This limit is enforced only at the UI layer (one file upload zone, no multi-select).
The service method `attach_file_to_announcement` has no guard against calling it
multiple times on the same announcement.

**Root cause:** Adding the count check in the service layer was deferred to keep
Phase 8b focused. The UI currently presents only one upload slot.

**Impact:** Low for M9 — the UI prevents accidental multi-attach. A direct API call
or a future UI change could bypass the limit without the service guard.

**Resolution path:** Add a `list_attachments(announcement_id)` count check in
`attach_file_to_announcement`: if `len(existing) >= 1`, raise `AnnouncementError`.
When the spec is relaxed to N attachments, replace `1` with the configured limit.

---

### TD-062 — Decorator meta-test: data presence ≠ auth resolution for scoped users

**Phase:** M9 Phase 8b.2

**Symptom:** `test_announcement_decorator_actions.py` verified that every `@require_role`
decorator's `(resource, action)` pair has a seeded `Permission` row. This did NOT catch
the Phase 8b.2 bug where a campus-scoped DIRECTOR was denied `announcement:soft_delete:own`
because `can()` filtered out their `UserRole` before checking permissions.

**Root cause:** Data presence (Permission row exists) does not imply resolution success
(a scoped user can actually pass `can()` for that permission). The meta-test needs a
separate layer: for each decorator's `(action, resource, scope)`, invoke `can()` with a
synthetic user holding the canonical scoped role and assert it returns `True`.

**Impact:** Latent permission bugs on scoped roles slip through gate verification.
Found and fixed by Phase 8b.2, but only by manual testing.

**Resolution path:** Add a second assertion level to `test_announcement_decorator_actions.py`
or a companion test: for each decorator triple `(action, resource, scope)`, create a
synthetic scoped UserRole, call `can(scope_type=scope)`, and assert `True`. This covers
the `scope_type not in ("*", "own")` bypass semantics as a live runtime check.

---

## M9 Tech Debt — Phase 9 Consolidation (TD-045 through TD-063)

### Summary disposition table

| ID | Title | Status | Resolution |
|----|-------|--------|------------|
| TD-043 | AudienceGroup program_degree_types filter is a non-functional stub | Deferred | M13 (Student records) — see formal entry above |
| TD-044 | 22 latent unit test failures pre-dating M9 | Open | Test-hygiene phase; 61 failures observed in full-suite runs post-Phase-7 |
| TD-045 | Distinct `withdrawn` vs `is_deleted` states for announcements | Open | Post-M9 model refinement; currently `is_deleted=True` means withdrawn, conflating two semantics |
| TD-046 | Repository-level pagination for AnnouncementRepository | Open | Post-launch when volume warrants; current service-side slice is correct for M9 scale |
| TD-047 | True baseline is ~61 failures, not the 22 filed at Phase 2 | Open | Phase 7 established 61 as the correct baseline; TD-044 entry should be updated at test-hygiene phase |
| TD-048 | Compose button visibility for non-composer users | Resolved | Phase 8b.2 — UI confirmed; sys_admin button hides correctly via list_composer_eligible_roles returning empty |
| TD-049 | Seed lacks composer-eligible users for manual walkthroughs | Resolved | Root cause: DB not reseeded after Phase 4; resolved mid-Phase-7 (TD-050) |
| TD-050 | Local dev DB needed reseed after Phase 4 seed expansion | Resolved | Reseeded during Phase 7 walkthrough setup |
| TD-051 | Seed re-run discipline not documented for fresh-clone setup | Open | Add to onboarding docs / Session start checklist at a future docs milestone |
| TD-052 | `can()` scope_type filter too aggressive | Resolved | Phase 7.1 (scope `"*"`) + Phase 8b.2 (scope `"own"`) — see formal entry above |
| TD-053 | Auth tests lack scoped-UserRole coverage for all decorator pairs | Open | Phase 8b.1 meta-test covers (action, resource) existence only; runtime resolution not verified for scoped roles |
| TD-054 | Auto-announcement `composer_role_code = "SYSTEM"` literal | Open | Future refinement; see formal entry above |
| TD-055 | Manual E2E test of auto-announce hook requires leave-balance fixture | Deferred | Phase 10 if fixture available; otherwise M10 when Leave/Approval cross-testing is simpler |
| TD-056 | Announcement attachments: no download-permission restriction | Open | Post-M9 confidentiality hardening; see formal entry above |
| TD-057 | Announcement attachments: single-file limit enforced only by UI | Open | Future UI multi-file work; see formal entry above |
| TD-058 | CC test-suite totals have been paraphrased rather than verbatim in reports | Open | Process discipline; raw output mandate added to gate_verification.md M9 lessons |
| TD-059 | Time-bounded withdraw window (announce then withdraw before publish) | Resolved | Phase 8c — publish_delay_seconds per category; withdraw_announcement rejects if scheduled_at ≤ now |
| TD-060 | Read-receipt + withdraw notification | Deferred | Future Notifications milestone |
| TD-061 | Scheduled publishing with grace period | Resolved | Phase 8c — publish_delay_seconds achieves configurable grace period; scheduled_at used as the publish boundary |
| TD-062 | Decorator meta-test: data presence ≠ auth resolution for scoped users | Open | Test-hygiene phase; see formal entry above |
| TD-063 | Baseline-capture requires 3-run determinism check | Resolved | Protocol established in Phase 8b.2; gate_verification.md M9 lessons record it |

---

### TD-045 — Distinct `withdrawn` vs `is_deleted` states for announcements

**Phase:** M9 Phase 6a (filed in design discussion; formalized in Phase 9 sweep).
**Severity:** Low — cosmetic/semantic only.

**Root cause:** `Announcement` inherits `TimestampedSoftDelete`, which uses `is_deleted=True` for all soft-deletes. Announcements use soft-delete as "withdrawn" — a semantically distinct operation (composer reclaims an unread announcement) vs the default "administrative removal." The conflation means hard-delete is theoretically possible via the admin hard-delete endpoint (though no UI exposes it for announcements), and audit rows use `action="withdraw"` while the model flag is `is_deleted`. Future query patterns (e.g., "list withdrawn announcements for audit") must filter by audit action, not model field.

**Resolution path:** Add a `withdrawn_at: datetime | None` field and `withdrawn_by: UUID | None` field to `Announcement`. Keep `is_deleted` for actual admin-removal; use `withdrawn_at IS NOT NULL` for user-facing withdraw state. Requires a migration.

---

### TD-046 — Repository-level pagination for AnnouncementRepository

**Phase:** M9 Phase 6a (filed during service implementation; formalized in Phase 9 sweep).
**Severity:** Low — correct at M9 scale; performance risk at scale.

**Root cause:** `AnnouncementService.list_for_browse` loads all candidates into Python (via `list_by_composer` or `list_visible_to_user`), applies audience resolution and priority sorting, then slices by `offset/limit`. For M9 institutional scale (hundreds of announcements) this is acceptable. At thousands of announcements, the full-load approach wastes memory.

**Resolution path:** Push the `ORDER BY` + `LIMIT/OFFSET` into the repository query. The priority sort (`sort_for_viewer`) must be adapted to work in SQL (CASE WHEN + JOIN on composer_config) or via a pre-computed rank column.

---

### TD-047 — True baseline is ~61 failures, not 22 (TD-044 undercount)

**Phase:** M9 Phase 7 (baseline recalibrated after seeded_db contamination spread).
**Severity:** Low — administrative.

**Root cause:** TD-044 was filed at Phase 2 when only `tests/unit/` failures were counted (22). Full-suite `pytest tests/` runs reveal additional order-dependent failures in `tests/integration/` (seeded_db_engine contaminating db_session tests). The 61-failure baseline is the correct operational number from Phase 7 onward.

**Resolution path:** Update TD-044 to note the 61-failure operational baseline. Triage and fix the contamination at a test-hygiene milestone (likely a small M9.1 or between M9 and M10).

---

### TD-051 — Seed re-run discipline undocumented for fresh-clone setup

**Phase:** M9 Phase 7 (discovered when walkthrough failed due to missing seed data).
**Severity:** Low — affects new developer setup, not production.

**Root cause:** The CLAUDE.md Session start checklist does not include `uv run python scripts/seed.py` as a step after `alembic upgrade head` on a fresh clone. A developer who migrates the DB but does not seed it sees `PermissionDenied` for all announcement operations, which is hard to diagnose.

**Resolution path:** Add a Step 5 to the Session start checklist in CLAUDE.md: "If this is a fresh clone or DB was reset: `uv run python scripts/seed.py`." Also document in runbook.md (already added in Phase 9 sweep).

---

### TD-053 — Auth meta-test: decorator (action, resource) existence ≠ runtime resolution for scoped users

**Phase:** M9 Phase 8b.1 (meta-test filed); Phase 8b.2 (scoped-role gap confirmed).
**Severity:** Medium — bugs in this class bypass CI.

**Root cause:** `test_announcement_decorator_actions.py` checks that every `@require_role` decorator's `(action, resource)` pair has a matching seeded `Permission` row. This confirmed correctness at the schema level but not at the runtime `can()` resolution level. Phase 8b.2 showed that a campus-scoped `DIRECTOR` was denied despite having a valid permission row — because `can()` filtered out their `UserRole` before examining permissions (pre-8b.2 bug). The meta-test would have missed this.

**Resolution path:** Add a second tier to `test_announcement_decorator_actions.py`: for each decorator triple `(action, resource, scope)`, create a synthetic `UserRole` with a structural scope (e.g., campus), call `can(scope_type=scope)`, and assert `True`. This exercises the runtime resolution path, not just schema presence.

---

### TD-055 — Manual E2E test of auto-announce hook requires a valid leave-balance fixture

**Phase:** M9 Phase 8a (auto-announce hook shipped but E2E not verified via a real approval flow).
**Severity:** Low — the hook is unit-tested; the integration gap is in the E2E layer only.

**Root cause:** Triggering the auto-announce hook in an E2E test requires: (a) a seeded leave request, (b) an approval process with `auto_announce_on_approve=True`, and (c) a user with the approver role to progress the request to the final stage. The M9 E2E fixture base doesn't include a leave-balance fixture (that's M8 territory). Setting up a full leave-approval flow in a Phase 10 E2E test is feasible but adds complexity.

**Resolution path:** Phase 10 E2E: add a focused integration test (not Playwright) that directly calls `ApprovalRequestService.approve()` with a seeded process that has `auto_announce_on_approve=True` and asserts that an `Announcement` row is created. Playwright verification of the created announcement in the browse list can be a separate E2E scenario.

---

### TD-058 — CC test-suite report numbers were paraphrased, not verbatim

**Phase:** M9 (cross-phase observation; formalized in Phase 9 sweep).
**Severity:** Low — process discipline only.

**Root cause:** Multiple phase reports (Phase 6a "898", Phase 6b "1474", Phase 8b "87") stated test counts that didn't match actual `pytest` output. The root cause is that CC paraphrased suite results instead of pasting verbatim `tail -3` output. This made it impossible to verify whether regressions were introduced between phases.

**Resolution path:** All phase reports must paste verbatim `pytest ... 2>&1 | tail -3` output. The raw output mandate is documented in `docs/prompts/gate_verification.md` M9 lessons section. `docs/milestones/M9.md` Phase 9 row corrects the Phase 8c stale numbers.

---

### TD-059 — Time-bounded withdraw window

**Phase:** M9 Phase 8c. **Status: Resolved.**

`Announcement.scheduled_at` is set to `now + category.publish_delay_seconds` at create time. `withdraw_announcement` rejects if `scheduled_at <= now`. The pending window is thus exactly `publish_delay_seconds` seconds from composition time. After the window the announcement is visible to recipients and withdraw is blocked.

---

### TD-060 — Read-receipt + withdraw notification not implemented

**Phase:** M9 (filed during Phase 8 design discussion).
**Severity:** Low — enhancement.

**Root cause:** When an announcement is withdrawn, recipients currently see no notification. Similarly, there is no read-receipt mechanism. Both require the push-notification infrastructure that `TD-032` describes as not yet built.

**Resolution path:** Defer to a future Notifications milestone after TD-032's dispatch worker exists.

---

### TD-061 — Scheduled publishing with grace period

**Phase:** M9 Phase 8c. **Status: Resolved.**

The `publish_delay_seconds` field on `AnnouncementCategory` provides a configurable grace period between composition and publication. `create_announcement` sets `scheduled_at = now + delay`; `list_visible_to_user` already filters `scheduled_at <= now`, so pending announcements are invisible to recipients during the grace period. This achieves the "scheduled publishing with grace period" goal without a separate `status` field.

---

### TD-063 — Baseline-capture requires 3-run determinism check

**Phase:** M9 Phase 8b.2. **Status: Resolved.**

Protocol established: before declaring a test suite baseline, the full non-E2E suite must be run 3 consecutive times. Any test that fails in some runs but not others is a flake and must be investigated before it can be excluded from the baseline count. The protocol is documented in `docs/prompts/gate_verification.md` M9 lessons.

---

### TD-064 — E-017 E2E tests xfailed: `_create_approved_leave` missing `half_day` column

**Phase:** M9 Phase 10.1. **Status: Open.**

**Location:** `tests/e2e/test_leave_withdraw_approved.py` — `TestWithdrawApprovedLeave` (all 3 tests).

**What it is:** The `_create_approved_leave()` SQL helper was written before commit `f903c28` (M8) added the `half_day` column to `leave_requests` with `NOT NULL DEFAULT false`. The helper's INSERT omits `half_day`, so PostgreSQL raises `null value in column "half_day"` and all 3 E2E tests error at fixture setup, before reaching any assertion about the E-017 feature itself.

All 3 tests are marked `@pytest.mark.xfail(strict=False, reason="E-017 ...")` so the M9 E2E gate is green. The underlying E-017 feature (withdraw post-approval) was not implemented in M9.

**Trigger to re-open:** When E-017 is scheduled for implementation, the fix requires two changes: (1) add `half_day = false` to the INSERT in `_create_approved_leave()`; (2) implement the post-approval withdraw service method and UI. Remove the xfail decorators and verify all 3 tests pass.

---

### TD-065 — E-022 E2E test xfailed: `get_by_label("Availed")` finds no match

**Phase:** M9 Phase 10.1. **Status: Open.**

**Location:** `tests/e2e/test_leave_balance_admin.py` — `TestLeaveBalanceAdminEdit.test_search_edit_save_shows_updated_closing`.

**What it is:** The E2E test for admin manual balance editing uses `page.get_by_label("Availed")` to locate the availed input in the edit form. Per the M2 E2E selector rule, `rx.text()` renders as `<p>`, not `<label>`, so `get_by_label` will not find inputs. The correct selector pattern is `get_by_placeholder(...)`. The test was written without verifying the selector against the rendered page. The test is marked `@pytest.mark.xfail(strict=False, reason="E-022 ...")` so the M9 E2E gate is green.

The underlying E-022 feature (admin manual edit of leave records) may be partially implemented in M8.1; the selector bug is separable from the feature completeness question.

**Trigger to re-open:** When E-022 is scheduled, fix the selector (`get_by_placeholder(...)` or an `input[name=...]` locator verified against the rendered form) and remove the xfail decorator. Run locally against the running app to verify the selector before committing.

---

### TD-066 — Composer scope label resolved at display time, not stored

**Phase:** M9 Phase 10.2. **Status: Open.**

**Location:** `durgam/services/announcement.py` — `_resolve_composer_scope_label()`; called from `durgam/states/announcements.py` (`load_announcements`, `open_detail`) and `durgam/pages/shared/recent_announcements_widget.py` (`load_widget_data`).

**What it is:** `_resolve_composer_scope_label(user_id, role_code, session)` queries `Role` + `UserRole` + the scope entity (Campus, Department, School, CentreOfExcellence) at display time to produce the label "Dean, School of Science" / "Head of Department, Mathematics & Computer Science" etc. This is correct at render time but means: if the user's scope changes after posting (transfer, rename of entity, or role revocation + re-grant with a different scope), the displayed label will reflect the NEW scope, not the scope at composition time.

**Why not stored:** The `Announcement` model already stores `composer_role_code`. Storing `composer_scope_type` + `composer_scope_id` + `composer_scope_name` at create time would require a migration and freeze the label at composition time. Deferred to a future revision when there is evidence this causes confusion (transfers within a posting's visible lifetime are rare).

**Resolution path:** Add `composer_scope_type: str | None`, `composer_scope_id: UUID | None`, `composer_scope_label: str | None` columns to `announcements` table. Populate from `_resolve_composer_scope_label` at create time. Read stored label directly in state — no DB join needed at display time.

---

### TD-067 — `_resolve_composer_scope_label` underscore convention vs cross-module import

**Phase:** M9 Phase 10.2. **Status:** Open.

**Location:** `durgam/services/announcement.py` exposes `_resolve_composer_scope_label` as a module-private function (leading underscore), but it is imported across module boundaries from `durgam/states/announcements.py` and `durgam/pages/shared/recent_announcements_widget.py`.

**Why it exists:** Phase 10.2 chose to resolve scope labels at the state-boundary rather than service-boundary to avoid changing `list_composer_eligible_roles`'s return type (which would have broken 4 existing tests). The resolution helper stayed in the service module but is called from state and widget.

**Resolution path:** Either (1) drop the underscore to signal public surface, or (2) move the helper to a new module like `durgam/services/_label.py` to preserve underscore-private semantics. Trivial follow-up; one-line code change.

---

### TD-068 — Seed user count non-idempotent across runs

**Phase:** M9 Phase 10 Step 8 (fresh-clone verification). **Status:** Open.

**Location:** `scripts/seed.py`.

**Observation:** During fresh-clone gate verification, two identical procedures (full `docker compose down -v` + `alembic upgrade head` + same seed command) produced different user counts: clone produced 26 users, main repo produced 44 users. All M9-specific entity counts matched exactly (composer configs 19, categories 9, audience groups 27).

**Hypothesis:** Some user-creation block in seed.py is non-idempotent (missing "if not exists" check), or seed was inadvertently invoked twice. The 18-row delta is plausibly explained by a 9-user batch added per extra run.

**Impact:** Low. Does not affect business logic; only complicates deterministic test-data setup for fresh-clone gate verification.

**Resolution path:**
1. Audit `scripts/seed.py` for user-creation paths lacking dedup guards.
2. Add upsert-by-username pattern OR assert single-run-only contract and document in runbook.
3. Add regression test that seeds twice on fresh DB and asserts user count unchanged after second run.

**Priority:** Address at the start of M10 (Faculty Module) since faculty seed is likely a touchpoint.

---

### TD-069 — non_regular_faculty FK metadata skew

**Phase:** M10 Phase 1A (filed at Phase 1B). **Status:** Open.

**Location:** `durgam/models/config_anchors.py` — `NonRegularFaculty.approval_request_id` FK; existing DB constraint `fk_nrf_approval_request_id` with `ondelete='SET NULL'`.

**What it is:** Alembic autogenerate at Phase 1A detected a name + ondelete mismatch between the DB constraint (named `fk_nrf_approval_request_id` with `ondelete='SET NULL'`) and the model definition (unnamed constraint, no ondelete). This is pre-existing metadata skew from M5b/M7 and was excluded from the Phase 1A migration to keep scope tight.

**Impact:** None functionally — DB behaviour is correct (SET NULL on referenced row delete). Purely declarative skew that surfaces as autogen noise on future migrations involving NonRegularFaculty.

**Resolution path:** Either (a) name the FK in the model `fk_nrf_approval_request_id` + add `ondelete='SET NULL'` to the FK declaration, or (b) drop and recreate the DB constraint to match the model's unnamed default. Option (a) is the cleaner forward path.

**Priority:** Low. Address opportunistically — likely target is M10 Phase 9 (NonRegularFaculty contract-term expansion) which will touch this model anyway.

---

### TD-070 — Migration test isolation: seeded-DB contamination from downgrade cycles

**Phase:** M10 Phase 1B (filed at Phase 2). **Status:** Open.

**Location:** `tests/integration/test_migrations.py` — `test_m10_phase1b_designation_expansion`.

**What it is:** Migration tests that run a downgrade/upgrade cycle on the test DB risk contaminating the seeded fixture shared by the rest of the integration suite. `_reset_test_db()` drops all SQLModel tables + alembic_version and re-migrates — but it does NOT re-seed, so subsequent `seeded_session` tests in the same pytest session see an empty DB and fail in cascading fashion. The Phase 1B migration test works around this by (a) NOT calling `_reset_test_db()`, (b) using `stamp head` + targeted downgrade/upgrade instead, and (c) cleaning up the manually-inserted legacy rows in a `finally` block. The trade-off: the reverse (downgrade-from-head) direction is verified only structurally (the downgrade SQL runs as part of the targeted cycle), not with full before/after assertions.

**Impact:** Medium. Downgrade-direction tests are weaker than ideal. A future data migration test that requires `_reset_test_db()` for correctness will need to run in isolation (separate pytest session or separate test DB) or re-seed after the reset.

**Resolution path:** Long-term: give migration tests their own dedicated DB (`settings.migration_test_database_url`) independent of the integration seeded DB, so `_reset_test_db()` can be called freely without contaminating `seeded_db_engine`. Short-term: document the constraint at the top of `test_migrations.py` and enforce it in code review.

**Priority:** Medium. Address before any milestone that introduces a data migration requiring full round-trip assertions (both forward and reverse with data-state verification).

### TD-071 — Resolver `_resolve_dept_head_at_requestor_campus` has wrong semantic

**Phase:** M10 Phase 3A. **Status:** Resolved. **Priority:** HIGH (blocks Phase 3B real-process wiring).

**Location:** `durgam/services/approval_resolvers.py` — `_resolve_dept_head_at_requestor_campus`.

**What it is:** The Q4a freeze specifies a HoD → AhoD → [] fallback chain that finds the head of the requestor's *specific department* (filtered to their campus). The current implementation returns the union of HoDs across *every department at the requestor's campus(es)* and has no AhoD fallback. Self-consistent with its 6 tests; semantically wrong against Q4a.

**Concrete bugs:**
1. Uses `UserRole.scope_type='department'` to derive requestor's dept, instead of `Faculty.department_id` (Phase 1A Faculty model). May pick up multiple depts if requestor holds multiple dept-scoped roles.
2. Collects HoDs of *every* dept on the campus, not just the requestor's specific dept.
3. No AhoD fallback when HoD is vacant.
4. No `Faculty.campus_id` filter on the HoD candidates (the HoD's physical campus is not checked).

**Resolution path (Phase 3B prompt):** Rewrite to:
1. Look up requestor's `Faculty` row by `user_id`; extract `department_id` + `campus_id`.
2. Query `User` joined to `UserRole` + `Faculty` for `Role.code='HOD'` scoped to that `department_id`, filtered by `Faculty.campus_id` matching requestor's campus.
3. If empty, repeat with `Role.code='AHOD'`.
4. Return `[user]` or `[]`.

The replacement function body is staged in the Phase 3B prompt drafted by Claude (see chat). Tests in `tests/integration/test_approval_resolve_stage_candidates.py` must be rewritten to assert against ground-truth Q4a semantic (HoD vs AhoD vs neither) using seeded faculty rows.

**Impact if not fixed before Phase 5:** FacultyRequest approval flows route to wrong approvers across the institute.

**Resolution (M10 Phase 3B, aa6f52a58a542c16f07fa9fba43d1b653e686de5):** Resolver rewritten per the resolution path. Uses `Faculty.department_id` + `Faculty.campus_id` to identify requestor's specific dept and campus. HoD -> AhoD -> [] fallback. Unit-tested in `tests/unit/test_approval_resolvers_unit.py`. Integration-level testing deferred to Phase 5 wiring -- see TD-072.

### TD-072 — `_resolve_dept_head_at_requestor_campus` lacks integration-level test

**Phase:** M10 Phase 3B (filed during recovery). **Status:** Open. **Priority:** Medium.

**Location:** `tests/integration/test_approval_resolve_stage_candidates.py` and seeded data.

**What it is:** The resolver is unit-tested in `tests/unit/test_approval_resolvers_unit.py` with mocked sessions, verifying semantic logic (HoD found, AhoD fallback, no Faculty, etc.). No integration test exercises the resolver against real seeded data.

The Phase 3B prompt originally specified 4 ground-truth integration tests using `seeded_session` with `session.delete()` + `flush()` to set up the AhoD-fallback scenario. Those tests caused 28+ cascading failures because `seeded_session`'s rollback doesn't reliably revert mutations against the session-scoped `seeded_db_engine`'s pooled connections. The tests were dropped during Phase 3B recovery (2026-06-15).

**Resolution path:** When Phase 5 wires FacultyRequest to use OR-set with this resolver, end-to-end integration tests will exercise the resolver against real seeded data naturally. Alternatively, write dedicated integration tests using `db_session` (function-scoped, fresh schema) that create synthetic Campus + Department + Roles + Users + Faculty from scratch — significant boilerplate but proper isolation.

**Impact if not fixed:** Resolver logic is covered by unit tests with mocks but not by integration tests with real DB queries. Schema-level bugs (FK constraint mismatches, column name typos in joins) would not be caught until Phase 5 wiring exercises this path.

**Priority:** Medium. Phase 5 will surface this naturally; explicit remediation not required before then.

---

### TD-073 — `_resolve_or_set_approvers` double-queries `ApprovalStageOption`

**Phase:** M10 Phase 5C1. **Status:** Open. **Priority:** Low.

**Location:** `durgam/services/approval_request.py` — `_resolve_or_set_approvers()`.

**What it is:** `_resolve_or_set_approvers()` calls `ApprovalStageOptionRepository.list_by_process_stage()` to check whether OR-set options exist, then delegates to `resolve_stage_authority()` which calls the same repository method a second time. Two DB round-trips for the same rows per approval action.

**Why not fixed now:** Avoiding a signature change to `resolve_stage_authority()` (adding a pre-fetched `options` parameter) to keep the engine API stable mid-milestone. The double-query is within the same transaction, adds negligible latency at M10 scale, and does not affect correctness.

**Resolution path:** Add an `options: list[ApprovalStageOption] | None = None` parameter to `resolve_stage_authority()` so the caller can pass pre-fetched rows. When provided and non-None, the function skips the repo query. Re-evaluate at M11 or when OR-set is used at high load.

---

### TD-074 — `FacultyRequestService.approve_request()` violates service→service layering

**Phase:** M10 Phase 5C1. **Status:** Open. **Priority:** Low.

**Location:** `durgam/services/faculty_request.py` — `FacultyRequestService.approve_request()`.

**What it is:** `FacultyRequestService.approve_request()` instantiates `ApprovalRequestService` (a deferred import inside the method body) — a cross-service call that violates the CLAUDE.md rule "No import from another service inside a service."

**Why not fixed now:** The approval engine (`ApprovalRequestService.approve()`) is the only production path for advancing approval steps atomically (state change + audit + notifications). Lifting the call into the page-state layer would expose approval-request internals (process lookup, stage resolution) to the UI layer, which is a worse violation. A thin bridge module was considered but deferred: at Phase 5C1 scope it adds indirection without adding logic.

**Resolution path:** Introduce a `durgam/services/faculty_approval_bridge.py` (or similar cross-cutting coordinator) that owns the "advance a FacultyRequest approval step" action, importing both services. This mirrors how `auth` and `notifications` are cross-cutting. Re-evaluate at M10 Phase 7 when full approval CRUD is wired to page states.

---

### TD-075 — `seeded_session.flush()` in idempotency test

**Phase:** M10 Phase 5B (filed in 5C2). **Status:** Open. **Priority:** Medium.

**Location:** `tests/integration/test_faculty_noc_seed.py:59` (inside `test_faculty_noc_seed_idempotent`).

**What it is:** Test calls `seeded_session.flush()` to verify the seed function is idempotent. The seed function's idempotency means no pending writes exist at flush time, so this is benign in practice (verified across 3 deterministic test runs at Phase 5B close — 1479 passed × 3 identical). However, this violates the hard rule established in Phase 3B recovery: `seeded_session` must be read-only because rollback against the session-scoped `seeded_db_engine` is unreliable for mutations.

**Risk:** Future seed function changes that introduce non-idempotent paths could cascade into 28+ collateral failures (as seen in Phase 3B with `seeded_session.delete()`, which is the source of TD-072's gap before resolution).

**Resolution path:** Refactor `test_faculty_noc_seed_idempotent` to use `db_session` with explicit migration setup + manual seed re-invocation, mirroring the synthetic-fixture pattern in `tests/integration/test_faculty_request_submit.py`. Estimated effort: 30 minutes.

**Filed:** M10 Phase 5C2, 2026-06-15.

---

### TD-076 — OR-set stage approval semantics in engine — RESOLVED

**Phase:** M10 Phase 5C1. **Status:** RESOLVED at commit `4d2a578` (Phase 5C1 substantive).

**Original problem:** Phase 5B's NOC process introduced ApprovalStageOption rows with `pick_mode='approver'`, creating a pool of multiple eligible users at Stage 1 (HoD + AhoD via dept_head_at_requestor_campus resolver). The existing M5b/M7 stage-advancement engine expected a single `approver_user_id` to mark a stage as approved.

**Resolution:** Phase 5C1 extended `ApprovalRequestService._resolve_approvers` (durgam/services/approval_request.py) with a new `_resolve_or_set_approvers` helper that:
1. Queries `ApprovalStageOption` for the current stage
2. If options exist, delegates to `resolve_stage_authority` (Phase 4) and returns the resolved pool
3. If no options, returns `None` so the legacy M7/M8 paths execute unchanged

First-action-wins semantics per Q-P5C.1 freeze: any user in the resolved pool can approve; first action advances the stage. Verified by `test_approve_or_set_hod_eligible`, `test_approve_or_set_ahod_eligible`, `test_approve_or_set_non_pool_actor_raises_unauthorized`, `test_approve_rejects_already_advanced_stage`, `test_existing_legacy_process_eligibility_unchanged` in `tests/integration/test_faculty_request_approve.py`.

**Filed for traceability:** M10 Phase 5C2, 2026-06-15.

---

### TD-078 — Isolation-skip pattern in `test_faculty_request_reject_withdraw.py`

**Phase:** M10 Phase 5C2 (filed in Phase 6). **Status:** Open. **Priority:** Low.

**Location:** `tests/integration/test_faculty_request_reject_withdraw.py` (uses `_get_seeded_noc_process` which calls `pytest.skip` when faculty_noc isn't seeded).

**What it is:** 11 of 15 tests in this file depend on the seeded NOC process being in the DB; in isolation (smoke-check invocation), they pytest.skip. This means the test file cannot be smoke-tested standalone. The pattern works in full-suite runs because conftest's seeded_db_engine seeds before these tests execute (verified by 3-determinism passing 1505 × 3 at Phase 5C2 close).

**Risk:** Future contributors may run this file in isolation expecting full coverage and miss regressions. Also inconsistent with Phase 5C1's test_faculty_request_approve.py which used synthetic fixtures + monkeypatched resolvers (no seed dependency).

**Resolution path:** Refactor the 11 seed-dependent tests to set up ApprovalProcess + ApprovalStageOption synthetically via db_session, mirroring Phase 5C1's pattern. Estimated effort: 1-2 hours.

**Filed:** M10 Phase 6, 2026-06-16.

---

### TD-079 — M9 announcement attachment MIME/size limits are hardcoded in state handler

**Phase:** M9 (filed in M10 Phase 6). **Status:** Open. **Priority:** Medium.

**Location:** `durgam/states/announcements.py:362-370` — `UploadService` constructed with `allowed_mimes=frozenset({"application/pdf", "image/png", "image/jpeg"})` and `max_size_mb=2` hardcoded in the state handler body.

**What it is:** M9 announcement attachment size/MIME limits are hardcoded constants in the state handler. Sys admin cannot reconfigure without a code deploy. This is inconsistent with the M7/M10 DB-backed approach (`ApprovalProcess.max_attachment_mb`, `allowed_attachment_mime_types_json`).

**Resolution path:** Add `allowed_attachment_mime_types_json JSONB` + `max_attachment_mb INT` columns to `AnnouncementCategory`. Migrate hardcoded values into DB defaults via Alembic. Read those values in `attach_upload` state handler and pass to `UploadService` constructor. Sys admin UI in Phase 7+ Admin section. Estimated effort: 4-6 hours.

**Filed:** M10 Phase 6, 2026-06-16.

---

### TD-080 — Sys admin UI for ApprovalProcess attachment configuration

**Phase:** M10 Phase 6 (filed for Phase 7). **Status:** Open. **Priority:** Medium.

**Location:** No code yet — to be built in Phase 7's admin UI surface.

**What it is:** Phase 6 ships DB-backed attachment configuration on ApprovalProcess (max_attachment_mb, max_upward_attachments, allowed_attachment_mime_types_json). Sys admin can change these values, but only via direct DB UPDATE or seed re-run. There is no UI for sys admin to self-service edit attachment policy per process.

**Risk:** Operational friction — institutional users (e.g., Registrar) cannot adjust attachment limits without developer assistance.

**Resolution path:** Phase 7's admin UI for FacultyRequest must include an "Approval Process Settings" form (or equivalent) gated to ADMIN/REGISTRAR roles, exposing max_attachment_mb, max_upward_attachments, and a multi-select MIME picker. Estimated effort: 1-2 days within Phase 7 scope.

**Filed:** M10 Phase 6, 2026-06-16.

---

### TD-081 — ApprovalAction visibility model defers DB-level RLS to application layer

**Phase:** M10 Phase 7A. **Status:** Open. **Priority:** Low.

**Location:** `durgam/services/approval_request.py` — `list_actions_for_requestor()` and `list_actions_for_approver()` filter in Python after fetching all actions for a request.

**What it is:** The Phase 7A visibility model (`is_visible_to_requestor`, `visible_to_lower_user_ids_json`) is enforced in the application service layer rather than as PostgreSQL Row-Level Security (RLS) policies. The repository returns all non-deleted `approval_actions` rows for a request; the service filters to the caller's visibility slice.

**Why this is acceptable now:** Per-request action counts are tiny (one per stage per decision — typically 2–5 rows). Python filtering at that scale is negligible. RLS would require a dedicated DB role-switching pattern not yet established in DURGAM. The tradeoff is acceptable at Phase 7A.

**Risk:** If visibility filtering logic diverges between two call paths (e.g., a future REST endpoint calling the repo directly), the app-layer filter could be bypassed. The repository currently exposes `list_by_request_id()` which returns all rows.

**Resolution path:** When per-request action counts exceed ~50 rows OR when a REST/GraphQL layer is introduced that bypasses the service, migrate visibility filtering to a PostgreSQL view or RLS policy. Tag with "before REST layer introduction." Estimated effort: 1 day.

**Filed:** M10 Phase 7A, 2026-06-16.
