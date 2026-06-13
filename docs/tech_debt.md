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




### TD-052 (RESOLVED in M9 Phase 7.1)

**Bug:** `can()` filtered out scoped `UserRole` rows even when the request passed
`scope_type='*'` (meaning "accept a grant for any scope"). The outer condition:

```python
if user_role.scope_type is not None and scope_type is not None:
    if user_role.scope_type != scope_type:
        continue
```

evaluated `"*" != scope_type` as `True` for any scoped role (e.g. campus-scoped
`DIRECTOR`), skipping the role before its permissions were examined.

**Impact:** Every user holding a scoped composer role (DIRECTOR, HOD, DEAN,
CENTRE_COORDINATOR) was denied `announcement:create:*` even though the permission
grant's scope is `"*"` (wildcard). Scoped composers could not post announcements.

**Fix:** Added `and scope_type != "*"` to the outer condition in
`durgam/auth/permissions.py`. When the caller passes `scope_type='*'`, the user
role's own `scope_type` is not used to filter it out.

**Regression test:** `tests/integration/test_auth.py::TestCan::test_can_scope_wildcard_request_accepts_scoped_user_role`

**Resolved:** commit on m9-announcements, Phase 7.1.
