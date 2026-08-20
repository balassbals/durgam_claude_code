# Faculty Module (M10)

**RFP reference:** §9.7 (Faculty Module spec), §8.3 (Faculty Listing), §10.2 (Faculty
dashboard). Informal requirements: `docs/durgam_informal_requirements.docx` — Faculty Module
section (profile + 11 request types).
**Shipped:** M10, gate passed 2026-08-20, tag `m10-close` at `476e334`. See
`docs/milestones/M10.md` for the full phase-by-phase build history.

`Faculty` is 1:1 with `User` and represents regular-teaching staff
(`employee_type='regular_teaching'`). `NonRegularFaculty` (E-003 / M5b) is a separate,
inline-stored model for external personnel without `User` accounts — the two coexist; course
allocation (M13) will pull from both pools.

---

## 1. Self-service faculty profile

Route group `/faculty/profile/*`, nav-registered in `durgam/pages/faculty/__init__.py`.

| Page | Route | File | Covers |
|------|-------|------|--------|
| Profile | `/faculty/profile` | `durgam/pages/faculty/profile.py` | Identity (read-only), contact fields, external IDs (ORCID/LinkedIn/Google Scholar/ResearchGate), PhD toggle + fields, **and** photo upload/removal — all on one page (there is no separate contact or photo page; the photo card is built by `_photo_card()`). |
| Education | `/faculty/profile/education` | `durgam/pages/faculty/profile_education.py` | Education records (Tier-2 horizontal-scroll table per CLAUDE.md's responsive-table convention). |
| Experience | `/faculty/profile/experience` | `durgam/pages/faculty/profile_experience.py` | Prior organization, designation, date range, responsibilities. |
| Expertise | `/faculty/profile/expertise` | `durgam/pages/faculty/profile_expertise.py` | Area + proficiency level. |
| Documents | `/faculty/profile/documents` | `durgam/pages/faculty/profile_documents.py` | PDF upload; the file itself is immutable after upload — "Edit" only changes metadata (title, description), never the underlying file. |

**Service:** `durgam/services/faculty.py` (`FacultyService`) — profile-edit rules, photo
validation, and the education/experience/expertise/document CRUD rules, plus module error
classes (`FacultyNotRegularTeachingError`, `EmployeeIdConflictError`, `PhotoTooLargeError`,
etc.).

**Models:** `durgam/models/faculty.py` — `Faculty`, `FacultyEducation`, `FacultyExperience`,
`FacultyExpertise`, `FacultyDocument`, `FacultyWorkload`.

**Field ownership** (see CLAUDE.md-style governance table, restated here for the module):

| Surface | Configured by |
|---------|---------------|
| Self-edit fields | The faculty member themselves (owner) |
| Admin-locked fields (employee_id, designation, joining_date, dept/campus, employee_type) | REGISTRAR + REGISTRAR_OFFICE + HR_HEAD |
| Sensitive read (Aadhaar, PAN, uploaded documents) | REGISTRAR + REGISTRAR_OFFICE + IQAC_COORDINATOR + IQAC_OFFICE |

PAN/Aadhaar fields exist on `User` (`pan_enc`/`aadhaar_enc`) but have no encryption layer yet
and no UI — deferred as Phase P5, blocked on TD-084 (M11 design phase). See
`docs/security_decisions.md` SD-006.

---

## 2. Faculty directory

| Purpose | Route | File |
|---------|-------|------|
| Peer-view card grid | `/faculty` | `durgam/pages/faculty/directory.py`, `on_load=FacultyDirectoryState.load_records` |
| Peer-view detail | `/faculty/[fid]` | `durgam/pages/faculty/detail.py`, `on_load=FacultyDetailState.load_detail` |

The dynamic route segment is named `fid`, not `faculty_id` — deliberately, to avoid a Reflex
state-var collision with the `faculty_id` vars already present on `FacultyProfileState` and
friends (see comment in `durgam/durgam.py` at the route registration).

---

## 3. Faculty requests overlay

`/faculty/requests` (`durgam/pages/faculty/requests_overlay.py`) is a thin, purely-presentational
page: two `rx.link` tiles that deep-link into the general approvals module with a `?type=faculty`
query filter —

- "My Requests" → `/approvals/my-requests?type=faculty`
- "For my decision" → `/approvals/inbox?type=faculty`

There is no duplicate state on this page; the `?type` filtering logic lives in
`MyRequestsState` / `ApproverInboxState` on the approvals side. The `FacultyRequest` model
(`durgam/models/faculty_request.py`) is a single parametric table for all faculty-initiated
request types, with a `request_type` discriminator, a `payload_json` column, and an optional
FK to `ApprovalRequest`. Business rules live in `durgam/services/faculty_request.py`
(`FacultyRequestService`).

---

## 4. Admin faculty directory

`/admin/faculty` (`durgam/pages/admin/faculty_list.py`, `on_load=FacultyAdminListState.load_records`)
— a read-only list for admin/HR use, gated by `faculty:read:*`. Search + department/campus/
designation filters + pagination. Deliberately carries **no PII fields** (per the page's own
docstring).

---

## 5. Non-Regular Faculty (NRF)

`/admin/config/non-regular-faculty` — page `durgam/pages/admin/config/non_regular_faculty.py`,
state `durgam/states/config_non_regular_faculty.py`, service
`durgam/services/non_regular_faculty.py` (`NonRegularFacultyService`, plus
`RenewalDateInvalidError`), model `NonRegularFaculty` in `durgam/models/config_anchors.py`
(§9.10, E-003 — "visiting, adjunct, guest, contract, honorary"; date-windowed, not AY-locked).

Contract-term expansion (M10 Phase 9A) added `renewal_count` and
`latest_contract_file_id` to the model. Renewal is a direct sys_admin override — a "Renew
contract" kebab action opens a modal (new end date), calling `NonRegularFacultyService.renew`,
which increments `renewal_count` and extends `available_to`
(`RenewalDateInvalidError` if the new end date is ≤ the current one). The proper HoD-initiated →
university-admin-approved extension workflow is not yet built — tracked as TD-085, deferred to
M11.

---

## 6. Faculty picker component

A shared, searchable-dropdown replacement for free-text `employee_id` inputs, built at M10
Phase 11C (Q-P11.4).

- **Shared UI component:** `durgam/pages/shared/faculty_picker.py` — render-only; all behavior
  lives in the calling page's State.
- **API endpoint:** `durgam/api/faculty_picker.py` — `GET /api/faculty/picker`, registered in
  `durgam/durgam.py` via `app._api.add_route(...)`. Authorizes the caller if they hold `write`
  on ANY of the 5 assignment-style resources; returns ≤ 50 active faculty rows with picker
  fields only (`id`, `employee_id`, `title`, `first_name`, `last_name`, `display`) — zero PII.
- **Service:** `durgam/services/faculty_picker.py` (`FacultyPickerService`).
- **Consumers (4 admin forms):** `durgam/pages/admin/config/faculty_mentors.py`,
  `class_teachers.py`, `ug_timetable.py`, `non_owned_courses.py` (with matching states
  `config_faculty_mentor.py`, `config_class_teacher.py`, `config_ug_timetable.py`,
  `config_non_owned_course.py`).

Per CLAUDE.md's "Reflex State is the source of truth" rule, the in-app picker uses a State
handler calling the shared service server-side (not a client-side `fetch()` against the
endpoint) — the endpoint exists independently for its documented contract and for programmatic
callers, sharing the same service so behaviour is identical either way.

---

## 7. Faculty bulk CSV import

`/admin/faculty/import` — page `durgam/pages/admin/faculty_import.py`
(`admin_faculty_import_page`), state `durgam/states/faculty_bulk_import.py`
(`FacultyBulkImportState`), service logic in the shared `durgam/services/bulk_import.py`
(`validate_faculty_csv()` / `commit_faculty_import()` — there is no separate
`faculty_bulk_import.py` service file; faculty import shares the generic bulk-import module
used for users/courses/programs).

Three-stage flow: **upload** (`upload_csv`, `@audit_action(action="upload_csv")`) →
**preview** (per-row valid/invalid split, `preview_ready=True`) → **commit** (`commit_import`,
`@audit_action(action="commit_import")`, calls `commit_faculty_import(...)`).

If a CSV row's username doesn't match an existing account, an `email` column is required and
a new `User` is auto-created with `must_change_password=True` (and `employee_type` forced to
`regular_teaching`) before the `Faculty` FK resolves.

---

## 8. Faculty mentor confirmation

Page `durgam/pages/admin/config/faculty_mentors.py`, state
`durgam/states/config_faculty_mentor.py`, models `FacultyMentorAssignment` +
`FacultyMentorConfirmation` (`durgam/models/config_anchors.py`), shared invalidation helper
`invalidate_confirmation(ay_id, campus_id, actor_id, session)` in `durgam/services/assignment.py`
(`AssignmentService`).

A confirmed roster (an active `FacultyMentorConfirmation` row for the AY+campus pair) is
invalidated — soft-deleted, triggering a re-confirm banner — whenever a **material** field on
any mentor assignment in that roster changes, or an assignment is removed. Cosmetic edits leave
the confirmation intact. The banner ("Roster has changed since last confirmation — please
re-confirm when ready") only shows when the roster is both stale AND non-empty (M10 Phase
11E.2 fix, to avoid a confusing banner on an empty list).

---

## 9. HoD recommend-via leave matrix

Extends the M8 leave sanctioning matrix (`LeaveSanctionAuthorityRule`) with a designation/
employee-type-keyed HoD recommend stage (M10 Phase 10B, Q-P10).

- **Model fields** (`durgam/models/leave.py`): `recommend_via_role_code` (a fixed role that is
  a recommend-only stage preceding the sanctioner — e.g. Director recommends → VC approves for
  SCL) and `recommend_via_resolver` (mutually exclusive with the role-code field; names a
  resolver function for designation/employee-type-keyed HoD resolution).
- **Engine:** `durgam/services/leave_rules.py` — if `recommend_via_resolver` is set, prepends a
  recommend-only resolver stage to the channel; else if `recommend_via_role_code` is set,
  prepends a recommend-only role stage. The returned channel carries `recommend_only: bool`.
- **Rule construction:** `durgam/services/leave_sanction_rule.py` threads both fields through
  create/update.
- **Admin UI:** `/admin/config/leave-sanction-matrix`-adjacent, page
  `durgam/pages/admin/config/leave_matrix.py`, state `durgam/states/config_leave_matrix.py`
  (`form_recommend_via_role_code` field).

This absorbs E-021 (HoD/AhoD recommend-via stage) via `Faculty.campus_id`/`department_id`
providing the department-scoped resolution the M8-era matrix couldn't do on its own; it also
absorbs E-019 (campus-scoped Director routing) the same way.

---

## Test coverage

See `docs/coverage_matrix.md` M10 section for the full feature→test mapping. Summary by area
(unit + integration; no faculty-specific E2E suites exist — faculty flows are covered by
integration tests against real Postgres):

| Area | Key test files |
|------|---------------|
| Self-service profile | `test_faculty_profile_state.py` (16), `test_faculty_detail_state.py` (5), `test_faculty_education_state.py` (8), `test_faculty_experience_state.py` (8), `test_faculty_expertise_state.py` (7), `test_faculty_document_state.py` (8) |
| Core service / admin / repo | `test_faculty_service.py` (80 unit), `test_faculty_service_validation.py` (11 unit), `test_faculty_service.py` (5 integration), `test_faculty_admin_state.py` (11), `test_faculty_repository.py` (14), `test_faculty_models.py` (7), `test_faculty_seed_backfill.py` (3), `test_faculty_permission_catalog_phase2.py` (16) |
| Directory | `test_faculty_directory_state.py` (6) |
| Non-Regular Faculty | `test_non_regular_faculty_service.py` (21 unit), `test_m5b_non_regular_faculty.py` (11), `test_nrf_contract_term.py` (3), `test_nrf_approve_flow.py` (2), `test_faculty_noc_seed.py` (15) |
| Faculty picker | `test_faculty_picker_service.py` (14), `test_faculty_picker_endpoint.py` (11), `test_faculty_picker_rollout.py` (4) |
| M5b assignment backfill | `test_assignment_faculty_backfill.py` (6), `test_non_owned_course_service.py` (9 unit) + `test_m5b_non_owned_course.py` (6), `test_ug_timetable_service.py` (12 unit) + `test_m5b_ug_timetable.py` (9) |
| Bulk CSV import | `test_faculty_bulk_import.py` (33) |
| Mentor confirmation | `test_faculty_mentor_confirmation.py` (12) |
| Faculty requests | `test_faculty_request_service_validation.py` (11 unit), `test_faculty_request_service.py` (5), `test_faculty_request_repository.py` (8), `test_faculty_request_submit.py` (12), `test_faculty_request_approve.py` (11), `test_faculty_request_reject_withdraw.py` (15), `test_faculty_request_attachments.py` (18) |
| HoD recommend-via | `test_leave_hod_recommend_10a.py` (4), `test_leave_hod_recommend_10b.py` (5) |

---

## Known deferrals (see `docs/tech_debt.md` for full detail)

- **TD-084** — PAN/Aadhaar encryption-at-rest. Blocks Phase P5 (sensitive-section UI). Deferred
  to M11 as an explicit design phase.
- **TD-085** — NRF extension workflow (HoD-initiated, university-admin-approved). Deferred to
  M11.
- **TD-088** — Class coordinator re-introduction. Deferred to M13 (student domain), explicitly
  out of M11 scope.
