# §9.3 Configuration Module — Traceability Matrix

This matrix tracks coverage of RFP §9.3 (Configuration Module) across
milestones M3-M7 and parts of M14-M15. The §9.3 spec is the largest single
module specification in the RFP. This matrix ensures no requirement is
silently dropped between milestones.

**Updated at every milestone gate.** For in-flight milestones, rows whose
status is "In flight at M{N}" reflect the current implementation state.

**M3 gate passed: 2026-05-21.** All M3 rows verified via fresh-clone ritual.

**M4 gate passed: 2026-05-23.** All M4 rows verified via fresh-clone ritual.

**M5a gate passed: 2026-05-24.** All M5a rows verified.

Errata bindings: E-001 (vision/mission) extends the M3 row. E-003 (VisitingFaculty) → M5b; E-004 (RoleEmail divergence) → M5a.

**M5 split (2026-05-24):** Milestone M5 (Configuration — Identity
Attachments) is split into **M5a** (File Infrastructure & Identity Assets:
FileAsset + storage layer, RoleEmail remediation + UI, LetterheadAsset,
TemplateAsset, DOCX-merge docgen primitive) and **M5b** (Assignments &
Approval Config: MentalHealthCounsellor, FacultyMentor/ClassTeacher/
ClassCoordinator assignments, VisitingFaculty [E-003], NonOwnedCourse,
UGTimetable, ApprovalProcess + CPC + PurchaseProcedureRule config, bulk
import). M5a depends on nothing from M5b; M5b depends on M5a's file
infrastructure and docgen primitive. Errata E-003 (VisitingFaculty) and
E-004 (RoleEmail) bind to this split.

---

## Key

| Status | Meaning |
|---|---|
| Shipped at M{N} | Feature verified at the M{N} gate. |
| In flight at M{N} | Currently being built; gate not yet passed. |
| Planned for M{N} | Not started; assigned to milestone per §12. |
| Not yet assigned | §9.3 mentions this but §12 doesn't name a milestone. |

---

## Entities

| Requirement | Source | Milestone | Status | Notes |
|---|---|---|---|---|
| Campus (code, name, address) | §8.2, §9.3 | M3 | Shipped at M3 | Model + seed + CRUD admin page |
| School (code, name, dean_role_code) | §8.2, §9.3 | M3 | Shipped at M3 | Model + seed + CRUD admin page |
| Department (with school_id FK) | §8.2, §9.3 | M3 | Shipped at M3 | Session 6: full CRUD page, school FK dropdown, campus link management, sub-dept listing |
| DepartmentCampus join (multi-campus ops) | §8.2 | M3 | Shipped at M3 | Session 6: managed via department detail page; add/remove campus actions |
| SubDepartment + SubDepartmentCampus | §8.2, Appendix A | M3 | Shipped at M3 | Session 6: read-only listing in department detail panel; write UI deferred |
| CentreOfExcellence | §8.2, §9.3 | M3 | Shipped at M3 | Model + seed + CRUD admin page |
| Program (basic) | §8.2, §9.3 | M3 | Shipped at M3 | Session 6: read-only detail page with 6 sub-entity tabs; create/edit defers to M13 |
| ProgramOutcome (PEO/PO/PSO) | §8.2 | M3 | Shipped at M3 | Session 6: read-only Outcomes tab on program detail page (PEO/PO/PSO grouped); rich edit UI → M13 |
| ProgramRegulation | §8.2 | M3 | Shipped at M3 | Session 6: read-only Regulations tab on program detail page; rich edit UI → M13 |
| ProgramSchemeOfInstruction | §8.2 | M3 | Shipped at M3 | Session 6: read-only Scheme tab on program detail page; rich edit UI → M13 |
| ProgramSchemeCourse (course in scheme) | §8.2 | M3 | Shipped at M3 | Session 6: course codes shown in Scheme tab; rich edit UI → M13 |
| ProgramSpecialisation | §8.2 | M3 | Shipped at M3 | Session 6: read-only Specialisations tab on program detail page; rich edit UI → M13 |
| ProgramExitLevel | §8.2 | M3 | Shipped at M3 | Session 6: read-only Exit Levels tab on program detail page; rich edit UI → M13 |
| Course (basic — code, name, credits, lecture, tutorial, practical, evaluation) | §8.2, §9.3 | M3 | Shipped at M3 | Session 6: CRUD page; credits auto-derived from L+T+P/2 (global 2:1 practical ratio); M13 moves ratio to ProgramRegulation |
| Course (extended — course_type, delivery_mode, mooc_agency, IKS flags) | §8.3 | M13 | Planned for M13 | Refinement 3: defers to Program & Course module. M13 must also implement course_type-based department dropdown filtering: DSC/DSE/MDC restricts to departments running the program (auto-lock if single dept); AEC/SEC/VAC/Internship/Research/Minor allows all departments. Source: informal requirements doc, Course Module section. |
| University vision/mission | E-001, §9.3 | M3 | Shipped at M3 | Model + seed + edit page (Session 7); update-only enforced via NotDeletableError; /about/university displays read-only |
| Department vision/mission | E-001, §9.3 | M3 | Shipped at M3 | Model + seed + edit page (Session 7); scope-restricted to HoD's own dept; update-only; /about/departments/{code} displays read-only |
| AcademicYear (code, dates, is_locked, master_calendar_locked, iqac_confirmed) | §8.5, §9.3 | M4 | Shipped at M4 | CRUD + lock master calendar + IQAC confirm + AY lock enforcement; Celery task locks expired AYs nightly |
| ClassTimingsConfig (singleton) | §9.3 | M3 | Shipped at M3 | Singleton edit page (Session 7); HH:MM validation; configure action only |
| WorkingDaysConfig (singleton) | §9.3 | M3 | Shipped at M3 | Singleton edit page (Session 7); 5/6-day radio; configure action only |
| Faculty (basic info in config module) | §9.3 | M10 | Planned for M10 | Faculty profile module |
| Student (basic info in config module) | §9.3 | M12 | Planned for M12 | Student profile module |
| RoleEmail (email bound to role/scope) | §9.3 | M2/M5a | Shipped at M5a | M2 seeded; M4 reads for calendar phase-transition emails; E-004 remediation at M5a (re-key to UUID PK + TimestampedSoftDelete + partial unique indexes); management UI at `/admin/config/role-emails` (Registrar family + SysAdmin) |
| LetterheadAsset (file per role) | §9.3 | M5a | Shipped at M5a | Upload/replace/deactivate/download; partial unique index on `(purpose, role_code)`; MIME filter (DOCX); max 5 MB; scope columns removed at M5b gate (one letterhead per role is sufficient) |
| ApprovalProcess (workflow config — schema + CPC config) | §9.3, §8.4 | M5b | Shipped at M5b | Config UI + service + seeds CPC_FUND_RELEASE process (is_finance=True). Runtime execution stays M7. |
| ApprovalProcess (runtime execution) | §9.5 | M7 | Shipped at M7 | Generic approval engine with state machine, scope-chain routing, requestor + approver UI, NRF post-approval callback. CPC concurrent-committee topology deferred (requires M10 Faculty). |
| PurchaseProcedureRule (spend-tier config, Finance-owned) | Purchase Procedures doc, §9.5, E-007 | M5b | Shipped at M5b | 10 rows (5 tiers × 2 fund sources) seeded. Overlap validation with self-exclusion on update. Floor/ceiling normalization (Projects/UGC tier-2: 10,001). BOM as literal string in approving_authority_role_codes. Finance Officer only (NOT _PUBLIC_READ). |
| PurchaseCommitteeTemplate (committee composition policy, Finance-owned) | E-007 | M5b | Shipped at M5b | 2 rows seeded: campus (director_excluded=True, faculty by designation rank) + central (escalation_designate=REGISTRAR). eligible_designations + faculty_member_count + fixed_role_members model. Rank-preference enforcement → M7 runtime (requires M10 Faculty). |
| Designation (extensible faculty designation vocabulary) | E-007 | M5b | Shipped at M5b | 4 rows seeded (senior_professor through assistant_professor). Finance Officer owns. Referenced by PurchaseCommitteeTemplate.eligible_designations. |
| StudentCategoryCount (SC/ST/OBC/EWS/General per AY) | §9.3 | M4 | Shipped at M4 | AY-scoped singleton edit; Registrar-managed; blocked when AY locked |
| MentalHealthCounsellor (AY-scoped roster, Director's letterhead) | §9.3 | M5b | Shipped at M5b | Model + repo + service + config UI + DOCX roster download |
| FacultyMentorAssignment | §9.3 | M5b | Shipped at M5b | Model + thin UI (Option A). Rich UI at M14 when Faculty (M10) exists |
| ClassTeacherAssignment | §9.3 | M5b | Shipped at M5b | Model + thin UI (Option A). Rich UI at M14 when Faculty (M10) + Student (M12) exist |
| ClassCoordinatorAssignment | §9.3 | M5b | Shipped at M5b | Model + thin UI (Option A). Rich UI at M14 |
| NonOwnedCourse | §9.3 | M5b | Shipped at M5b | AY-scoped course shared across departments; Director + DAA family access |
| UGTimetable (first/second year, Director's office) | §9.3 | M5b | Shipped at M5b | AY-scoped; unique constraint on (AY, semester, year, day, period); Director family access |
| TemplateAsset (BoS, MoM, VAC certificate) | §9.3 | M5a | Shipped at M5a | IQAC-managed; types: bos/mom=DOCX, vac=PPTX; partial unique index on type; max 2 MB; `/admin/config/templates` |
| VisitingFaculty (external personnel per department) | E-003, informal req | M5b | Shipped at M5b | HoD-managed; inline external-personnel details; NOT AY-locked; feeds M13 course allocation |
| FileAsset + StorageBackend (file storage foundation) | §8.4, §4.1, §6.1 | M5a | Shipped at M5a | Local-fs dev / MinIO prod; UploadService orchestrates validate→store→record; UUID storage keys; purpose-based permission escalation on download endpoint |

---

## Behaviours

| Requirement | Source | Milestone | Status | Notes |
|---|---|---|---|---|
| Schools seeded once; departments declare school | §9.3 | M3 | Shipped at M3 | Seed script; school_id FK enforced |
| Bulk-add by CSV/Excel (users, courses, programs) | §9.3, §16 | M5b | Shipped at M5b | Two-stage validate→commit; users (M2), courses + programs (M5b Session 8). Faculty bulk import → M10 (requires Faculty model). Student bulk import → M12 (requires Student model). |
| AY-scoped configs immutable on rollover (is_locked=true) | §9.3 | M4 | Shipped at M4 | AcademicYearLockedError in repos; lock_for_rollover service method; Celery nightly task |
| Calendar collaboration chain (Registrar → IQAC → others) | §9.3 | M4 | Shipped at M4 | Three-phase sequential chain; 18 fixed entry types; ENTRY_TYPE_ROLE_MAP + phase gates; sports/cultural: DIRECTOR (campus) + DEAN_SW (institution) ownership split |
| Holiday management | §9.3 | M4 | Shipped at M4 | AY-scoped CRUD; separate Holiday model (not CalendarEntry type) |
| Calendar exports (CSV/Excel/PDF/DOCX) | §9.3 | M4 | Shipped at M4 | CalendarExportService + rx.download via bytes data |
| Phase-transition email notifications | §9.3 | M4 | Shipped at M4 | Registrar confirm → IQAC notified; IQAC confirm → Phase 3 roles notified; reads RoleEmail bootstrap placeholders; fire-and-forget via asyncio.create_task |
| Letterheads / templates used for docgen (not directly visible to other roles) | §9.3 | M5a | Shipped at M5a | Letterheads are DOCX templates (E-005); image-based merge primitive exists but not used with DOCX letterheads (TD-012 superseded by E-005); purpose-based download permission escalation |
| Mental-health counsellor roster downloadable as DOCX (Director letterhead, AY-scoped) | §9.3 | M5b | Shipped at M5b | AY-scoped; immutable on rollover; DOCX download with purpose-map gating |
| Class teacher assignments auto-flow into faculty workload | §9.3 | M14 | Planned for M14 | Model at M5b (Option A); workload auto-flow requires Faculty (M10) model; rich UI at M14 |
| UG timetable configured by Director, auto-projected to dept timetables | §9.3 | M5b | Shipped at M5b | Config UI shipped; auto-projection to dept timetables requires Student (M12) model → M14 |
| Student category counts managed by Registrar/office per AY; read-only for non-Student roles | §9.3 | M4 | Shipped at M4 | AY-scoped singleton edit; immutable on rollover |
| Vision/mission: update-only, no delete (university + department) | E-001 | M3 | Shipped at M3 | NotDeletableError in VisionMissionService |
| Vision/mission: viewable by all authenticated users | E-001 | M3 | Shipped at M3 | /about/university + /about/departments + /about/departments/[code] — Session 7 |
| Class timings and working-days config: singleton, configure action | §9.3, §12 M3 | M3 | Shipped at M3 | Singleton edit forms; configure-action guard; Session 7 |
| "System admin will only deal with basic information of academic departments when adding, editing" | §9.3 | M3 | Shipped at M3 | department:write:* granted only to SYSTEM_ADMIN (fixed M3 Session 5c — Registrar had it incorrectly) |
| Dean role bound to school via dean_role_code string reference | §8.2 | M3 | Shipped at M3 | OQ-M3-6 confirmed: plain string, no FK |
| Audit log read UI (sys-admin-only viewer with filters, pagination, detail drawer, CSV export) | §8.4, §12 M6 | M6b | Shipped at M6b | Resource label resolver; JSONB scope filter; 10K-row CSV cap; diff table with FK-label resolution |

---

## Deferred Forward-Concerns (from M5b)

| Concern | Source | Deferred to | Notes |
|---|---|---|---|
| UGTimetable rename + class-label refactor | §9.3 | Separate focused pass | Currently handles UG year 1/2 only |
| Faculty dropdowns on assignment pages | §9.3 | M10 + M14 | Depends on Faculty model |
| Student dropdowns on assignment pages | §9.3 | M12 + M14 | Depends on Student model |
| Course dropdown on NonOwnedCourse | §9.3 | M14 | |
| Faculty bulk import (CSV) | §9.3, §16 | M10 | Requires Faculty model |
| Student bulk import (CSV) | §9.3, §16 | M12 | Requires Student model |
| Bulk-add for campuses/depts/programs | §9.3 | M13 | |
| Cross-entity search + filtering | §9.3 | M13 / dashboard | |
| Viewability of basic info by all | §9.3 | Dashboard milestone | |
| Sub-departments management | §8.2 | Future | |
| Class teacher load → faculty workload | §9.3 | M10 | |
| Non-owned-course faculty workload contribution | §9.3 | M10 | |
| Class coordinator student picker | §9.3 | M12 | Needs Student model |
| Course-code dropdown auto-fill | §9.3 | M14 | |
| Announcement composer roster | §9.3 | M9 (RFP §12) | |
| HoD picks next-level approver from candidate set | E-007 | M10/M14 | Deferred from M7 — requires purchase-request artifact + M10 Faculty model. E-007 R1 semantic. |
| Informational CC notification on approval | E-007 | M7 | Shipped at M7 | CC recipients resolved from `informational_cc_role_codes` and notified on terminal decision. |
| Non-regular faculty approval routing per case | E-003, E-007 | M7 | Shipped at M7 | NRF_APPROVAL process with DEAN→REGISTRAR channel; post-approval auto-creates NRF record. E-014 records channel-customization concern. |
| Approval-process SLA enforcement | §9.5 | Future | Deferred from M7 — tracking step-level time limits not needed for v1 processes. |
| Purchase committee rank-preference enforcement | E-007 | M10/M14 | Deferred from M7 — highest-rank-first selection from eligible_designations requires M10 Faculty model for who-exists/availability |
| Purchase committee availability/fatigue check | E-007 | M10/M14 | Deferred from M7 — reject faculty serving on too many concurrent committees; requires M10 Faculty model |
| Purchase committee justification field | E-007 | M10/M14 | Deferred from M7 — text justification when lower-ranked faculty selected; requires M10 Faculty model |
| Project-fund link to PI | E-007 | M11 | Runtime concern: link project fund source to PI's faculty record; requires M10 Faculty + M11 Research |
| ClassCoordinatorAssignment ownership transfer to class-teacher role | §9.3 | M14 | Requires M10 Faculty identity + M12 Student model for student-picker |
| Committee member selection (rank-preference, availability) | E-007 | M10/M14 | Requires M10 Faculty model for who-exists/who's-available lookup |
| Retrofit older config pages (M3/M4) with live-sourced role picker | UI Polish | UI Polish | M5b established `role_multi_select()` and `_load_role_options()` patterns |
| Counsellor roster letterhead overlay polish | M5b | M14 docgen | Auto-fill campus/director/designation |
| Faculty mentor roster letterhead overlay polish | M5b | M14 docgen | Auto-fill campus/director/designation |
| Calendar entry conflict detection | M5b | M6 | |
| Calendar email per-user notification preferences | M5b | Future M-Notifications (per M9 Q15 freeze) | |
| Visiting/non-regular faculty contract term tracking | E-003 | M10 | |
| Role-based dashboard widgets | §9.3 | M15 | |
| Bulk assignment import (class teachers, coordinators) | §9.3 | M14 | |
| Designation-based committee eligibility verification | E-007 | M10 | |
| Test fixture isolation (db_session vs seeded_session) | TD-008 | Test infra | |

---

## M5 Inheritance Note (from M3)

ClassTeacher, ClassCoordinator, and FacultyMentor assignments are scheduled for M5b
(Assignments & Approval Config) per §12 and the M5 split (2026-05-24). These
assignments reference Faculty (M10) and Student (M12), which arrive after M5b.

**Option A confirmed:** Ship the assignment data model + schema at M5b; leave UI as
a thin management scaffold; implement full UI at M14 (Department module) when both
Faculty and Student exist.

This note was added at M3 close-out. See `docs/milestones/M3.md` Session 5 resume notes.
Option A confirmed at M5 split (2026-05-24).

---

## M10 Forward Concern — Dual-Role Calendar Ownership

At M4 Session 5, the calendar entry page uses auto-detect to determine the creating
user's `owner_role_code` from `ENTRY_TYPE_ROLE_MAP`. This works because no M4 user
holds two calendar-owning roles for different entry types.

**Trigger to revisit**: any user holds 2+ roles that appear in `ENTRY_TYPE_ROLE_MAP`.
At that point, the calendar page will need a "Creating as" role selector dropdown.

**Related institutional fact**: a Dean of Student Welfare or campus Director is
typically also a faculty member (Professor in a department) — holding both an
administrative role and a faculty appointment simultaneously. Faculty is not modeled
until M10. When Faculty (M10) arrives, people holding both a faculty appointment and
an administrative role (Dean/Director/HOD) create cross-cutting design questions for
workload, leave sanctioning, and scope resolution. M10 and M14 planning must address
how one person's two appointments interact.

---

## UI Polish Backlog — Visual Calendar (from M4)

The M4 Calendar page uses a filtered list/table view. A richer visual calendar
(month/week grid view, drag-and-drop, colour-coded entry types) is a separate,
larger feature not part of M4. If a future milestone requests a visual calendar,
scope it as a distinct UI task — the data model, service, and filter logic from M4
are reusable; the work is purely frontend.

Calendar clash detection is deliberately NOT implemented — see `docs/milestones/M4.md`
Session 5 design decision for rationale.

---

## M5b Forward-Concerns (from gate verification round 2)

The following items were identified during M5b gate verification as requiring
work in later milestones. They are not bugs or gaps — they are intentional
deferred scope.

1. **Committee member selection requires M10 Faculty model** — the purchase
   committee assembly UI needs to know which faculty exist and their
   designations. → M10/M14.
2. **Rank-preference, availability/fatigue check, justification field** — M7
   runtime purchase committee constraints that depend on M10 Faculty. → M7/M10.
3. **Calendar email recipients: individual notification preferences** — currently
   all users with the target role receive the email; per-user opt-out deferred to future M-Notifications milestone (per M9 Q15 freeze). → Future M-Notifications.
4. **Counsellor document generation with letterhead overlay** — the roster
   export uses the Director letterhead as a DOCX template; generating formal
   appointment letters with letterhead merge is M14 scope. → M14.
5. **Purchase committee member identity verification** — verifying that the
   named committee members actually hold the required designation at the time
   of committee formation. → M10.
6. **Approval process SLA enforcement** — tracking and enforcing time limits on
   each step of an approval process. → M7.
7. **Class coordinator student picker** — currently a text placeholder; needs
   the Student model from M12 for a real student selector. → M12.
8. **Non-regular faculty contract term tracking** — tracking formal contract dates,
   renewal, and integration with HR. → M10.
9. **Role-based dashboard widgets** — per-role landing page with relevant
   quick-access panels. → M15.
10. **Calendar entry conflict detection** — warning when a new entry overlaps
    with existing entries in the same scope. → M6.
11. **Bulk assignment import (class teachers, coordinators)** — CSV/Excel upload
    for batch assignment of class teachers and coordinators. → M14.
12. **Designation-based committee eligibility verification** — verifying
    designation rank at committee-formation time requires the Faculty model. → M10.
13. **Full routing customization for approval processes** — the current
    channel_role_codes + informational_cc_role_codes cover the common case;
    conditional branching (if amount > X, route to Y) is M7 runtime. → M7.
14. **Counsellor roster letterhead-overlay rendering** — Jinja2 placeholders in
    letterhead template for counsellor roster export. → M14.
15. **Faculty mentor confirmation notification emails** — email notifications
    when Director confirms a campus mentor roster. → Future M-Notifications (per M9 Q15 freeze).
16. **Faculty mentor roster letterhead overlay** — basic DOCX-on-letterhead
    (render_docx_template with Director letterhead) works at M5b. Rich auto-fill
    polish (campus/director-name/designation from login scope) remains. → M14.
17. **Non-regular faculty approval-request workflow** — **Resolved at M7.** M5b's
    direct-approve placeholder replaced by NRF_APPROVAL process with DEAN→REGISTRAR
    channel. Post-approval callback auto-creates the NRF record. Direct-approve toggle
    retained for historical rows. See E-014 for channel-customization concern.

---

## M13 Inheritance Note

Rich management UI for Program sub-entities (PEO/PO/PSO editing forms, regulation
editors, scheme builder, specialisation editor, exit-level editor) defers to M13
(Program & Course Management). The M3 gate clause is met by the seed alone; the data
model exists and is verified by integration tests.

---

## M8 — Leave Rules (§11)

**Gate passed: 2026-06-09.** All rows verified via fresh-clone ritual.

| Feature | RFP §§ | Target | Status | Notes |
|---------|--------|--------|--------|-------|
| User employment fields (gender, joined_on, employee_type) | §11 | M8 | Shipped at M8 | Required for leave eligibility (ML gender check, service-duration check). |
| New roles: CONTROLLER_OF_EXAMINATIONS, HR_HEAD, HR_OFFICE, PROFESSOR, ASSOC_PROFESSOR, FACULTY + VC seeded user | §11 | M8 | Shipped at M8 | 6 new roles + designation roles for leave sanctioning hierarchy. |
| LeaveRequest model + LeaveBalance model | §11 | M8 | Shipped at M8 | Full TimestampedSoftDelete; AY-scoped; approval_request_id FK links to approval engine. |
| LateAttendanceMarker model | §11 | M8 | Shipped at M8 | HR-entered markers feed CL monthly-forfeit Celery job. |
| LeaveSanctionAuthorityRule (sanctioning matrix) | §11.10 | M8 | Shipped at M8 | 73 rules from YAML seed; applicant_role_code + leave_type + scope_type + recommend_via_role_code + sanctioner_role_code; priority-based resolution. |
| Leave rules engine (eligibility, accrual, balance, channel resolution) | §11 | M8 | Shipped at M8 | LeaveRulesEngine: check_eligibility, check_balance, compute_chargeable_days (half-day, CML=HPL, holiday exclusion), resolve_sanctioning_channel. Property tests with hypothesis. |
| LEAVE_APPROVAL ApprovalProcess seeded + per-request channel override | §11 | M8 | Shipped at M8 | resolved_channel_json on ApprovalRequest stores per-request channel derived at submit time; fallback to process.channel_role_codes for non-leave processes. |
| Celery leave jobs (forfeit late-CL, lapse unavailed CL, credit EL/HPL, overstay check) | §11 | M8 | Shipped at M8 | 5 beat schedule entries. TD-036: CL annual credit at AY start not yet scheduled. |
| Requestor UI: /leave (balance cards, in-flight, history, Apply modal, preview) | §11 | M8 | Shipped at M8 | balance cards hide numeric fields for SCL/EOL/SL ("As per approval"). Progress row always visible on in-flight + history. |
| Approver UI: leave detail section in /approvals/request/{id}, Recommend button | §11 | M8 | Shipped at M8 | Shows leave type, dates, days, requestor balance (hidden for SCL/EOL/SL), uploaded docs. |
| Leave Sanction Matrix admin (/admin/config/leave-sanction-matrix) | §11.15 | M8 | Shipped at M8 | Registrar tier; CRUD for LeaveSanctionAuthorityRule rows. |
| Late Attendance admin (/admin/leave/late-attendance) | §11 | M8 | Shipped at M8 | Director tier; HR adds late-attendance markers by employee username. |
| HoD/AhoD recommend-via stage for FACULTY leave | §11.10 | M10 | Deferred — E-021 | Requires M10 Faculty/Department assignment model for department-scoped HoD resolution. |
| Campus-scoped Director routing | §11.10 | M10 | Deferred — E-019 | Engine routes any DIRECTOR; campus-scoped filter deferred to M10. |
| ApprovalProcess-driven SCL auto-credit | §11.4 | Future | Deferred — E-020 | requires_scl flag + post-approval auto-LeaveRequest creation. |
| Withdraw leave after approval | §11 | Future | Deferred — E-017 | Balance reversal + notification re-fan; shares scope with E-022. |
| Admin manual edit of leave records | §11 | Future | Deferred — E-022 | Balance-edit page + retroactive entry; Director/Registrar tier; shares scope with E-016/E-017. |
| Legacy balance import for live deployment | §11 | Future | Deferred — E-016 | Bulk-import flow for existing balances at go-live; requires E-022 admin UI. |
| Notification dispatch for leave events | §11 | Future | TD-037 | Row enqueue appears to be a silent no-op for the leave subsystem (0 rows observed during full gate walkthrough); investigate before TD-032 dispatch worker lands. |

---

## M8.1 — Leave Module Follow-ups

**Gate passed: 2026-06-11. Merged to main as `c8962fd`; tag: `m8.1-close`.** See `docs/milestones/M8.1.md` for gate details.

| Feature | Errata/TD | Target | Status | Notes |
|---------|-----------|--------|--------|-------|
| CL annual credit Celery task (`credit_annual_cl`) | TD-036 | M8.1 | Shipped at M8.1 | `LeaveCreditPolicy` model + `leave_credit_runs` sidecar + admin config page. Idempotent. Jan 1, 03:00 UTC. |
| Notification enqueue on auto-approve path | TD-037 | M8.1 | Shipped at M8.1 | Root cause: `submit()` auto-approve branch missing `_enqueue_notifications` call. Fixed in `8b3f609`. |
| Legacy balance import (`/admin/leave/balance-import`) | E-016 | M8.1 | Shipped at M8.1 | Two-stage CSV import + per-employee form. 7-column format. AY-locked guard. Audit per row. |
| Withdraw approved leave with balance reversal | E-017 | M8.1 | Shipped at M8.1 | `withdraw()` extended for approved state. Unused-tail formula. HoD/AhoD/Director notifications. `withdrawal_reason` migration. |
| LeaveBalance admin edit (`/admin/leave/balance-edit`) | E-022 | M8.1 | Shipped at M8.1 | Per-row edit. `closing_balance` auto-recomputed. Audit on every save. |
| LeaveRequest admin edit (`/admin/leave/request-edit`) | E-022 | M8.1 | Shipped at M8.1 | Allowed state transitions per DD-M8.1-P8-5. Approved→cancelled/withdrawn delegates to `withdraw()`. Window-elapsed guard blocks transitions after `ends_on`. |
| Post-facto leave application (`is_post_facto` flag) | E-022 | M8.1 | Shipped at M8.1 | Set at submit time if `starts_on < today`. Amber badge on Apply modal. CL forfeit reversal on approval. |
| Withdrawal notification campus-dept scope | TD-038 | M11 | Deferred | Faculty model shipped at M10 (Phase 1A) satisfying the linkage dependency; the campus/dept filter itself + fixture-isolation infrastructure retargeted to M11 at the M10 close docs sweep. |
| Leave admin pages campus-scope enforcement | TD-039 | M11 | Deferred | Same Faculty-linkage dependency, now satisfied; retargeted to M11 at the M10 close docs sweep. |
| credit_annual_cl beat schedule DB-driven | TD-040 | Future | Deferred | Hardcoded Jan 1 is statutory; non-Jan-1 deferred. |

---

## M9 — Announcement Module

**Gate pending (Phase 10).** Branch: `m9-announcements`. See `docs/milestones/M9.md`.

| Resource | Actions permitted | Scope | Audit | Notes |
|----------|-------------------|-------|-------|-------|
| `announcement` | create, read, update, soft_delete (own) | `*` (create/read/update); `own` (soft_delete) | ✓ direct write_audit_row in service | Composer roster gated by AnnouncementComposerConfig; received tab hides pending (scheduled_at > now) |
| `announcement_composer_config` | read, configure | `*` | ✓ @audit_action on state handlers | SYS_ADMIN-tier. Manages which roles can compose and at what priority. |
| `announcement_category` | read, configure | `*` | ✓ @audit_action on state handlers | Registrar-tier. 9 default seed rows. publish_delay_seconds controls pending window (0–86400s). |
| `audience_group` | read, configure | `*` | ✓ @audit_action on state handlers | Registrar-tier. 23+ seed rows. filter_json validated at save time. program_degree_types axis = stub (TD-043). |
| Attachment download (`/api/files/{id}`) | read (permissive default) | authenticated | ✓ (FileAsset row) | TD-056: no audience gate on attachment download — deferred post-M9. |

**Auto-announce hook** (`ApprovalProcess.auto_announce_on_approve`): triggers `create_auto_announcement` on terminal approval, bypasses composer eligibility and publish delay. audit row written inside service. TD-054: composer_role_code = "SYSTEM" literal for auto-announcements.

**Deferred M9 forward concerns:**

| Feature | M9 status | Target |
|---------|-----------|--------|
| Per-user email opt-out for calendar delivery (coverage_matrix line 147/215) | Out of scope | Future Notifications milestone |
| Faculty mentor confirmation email (coverage_matrix line 243) | Out of scope | M14 (Director workflow) |
| Per-module announcement surfacing (§10.1 beyond dashboard widget) | Out of scope | M15 (Role-based dashboards) |
| Clubs/Meetings auto-announce hooks | Out of scope | M15 |

---

## M10 — Faculty Module

**Gate passed: 2026-08-20.** Fresh-clone verification: 61-failure deterministic baseline
(diff-empty vs. main) + 118 E2E passed + 8 skipped. Tag: `m10-close` at `476e334`. See
`docs/milestones/M10.md` for full phase-by-phase gate details and `docs/modules/faculty.md`
for the module reference.

| Feature | RFP §§ / Errata-TD | Target | Status | Notes |
|---------|---------------------|--------|--------|-------|
| Faculty self-service profile (contact, external IDs, PhD, photo) | §9.7 | M10 | Shipped | `durgam/pages/faculty/profile.py`; `test_faculty_profile_state.py` (16), `test_faculty_service.py` (80 unit, incl. photo handling). |
| Faculty education / experience / expertise / documents CRUD | §9.7 | M10 | Shipped | `profile_education.py` / `profile_experience.py` / `profile_expertise.py` / `profile_documents.py`; 8+8+7+8 integration tests respectively. |
| Faculty directory (peer card grid + detail) | §8.3 | M10 | Shipped | `pages/faculty/directory.py` (`/faculty`) + `detail.py` (`/faculty/[fid]`); `test_faculty_directory_state.py` (6), `test_faculty_detail_state.py` (5). |
| Admin faculty directory (read-only, no PII) | §9.7 | M10 | Shipped | `pages/admin/faculty_list.py` (`/admin/faculty`); `test_faculty_admin_state.py` (11). |
| Faculty requests overlay (deep-link `?type=faculty` into `/approvals`) | §9.7 | M10 | Shipped | `pages/faculty/requests_overlay.py` (`/faculty/requests`). |
| Faculty request types (submit/approve/reject/withdraw/attachments) | §9.7 | M10 | Shipped | `services/faculty_request.py`; `test_faculty_request_submit.py` (12), `_approve.py` (11), `_reject_withdraw.py` (15), `_attachments.py` (18), `_service.py` (5), `_repository.py` (8), `_service_validation.py` (11 unit). |
| Non-Regular Faculty contract-term + renewal | §9.10 / E-003 | M10 | Shipped | `pages/admin/config/non_regular_faculty.py`; `test_non_regular_faculty_service.py` (21 unit), `test_m5b_non_regular_faculty.py` (11), `test_nrf_contract_term.py` (3), `test_nrf_approve_flow.py` (2), `test_faculty_noc_seed.py` (15). |
| Faculty picker (shared component + `/api/faculty/picker` + 4-form rollout) | Q-P11.4 | M10 | Shipped | `pages/shared/faculty_picker.py`, `api/faculty_picker.py`; `test_faculty_picker_service.py` (14), `_endpoint.py` (11), `_rollout.py` (4). |
| M5b assignment-table `faculty_id` backfill (mentor / class-teacher / non-owned-course / ug-timetable) | Q-P11.4 / D-020 | M10 | Shipped | `test_assignment_faculty_backfill.py` (6), `test_non_owned_course_service.py` (9 unit) + `test_m5b_non_owned_course.py` (6), `test_ug_timetable_service.py` (12 unit) + `test_m5b_ug_timetable.py` (9). |
| Faculty mentor confirmation (invalidate-on-edit + re-confirm banner) | Q-P11E | M10 | Shipped | `states/config_faculty_mentor.py`; `test_faculty_mentor_confirmation.py` (12). |
| Faculty bulk CSV import (upload → preview → commit, auto-creates User) | Q-P12 | M10 | Shipped | `pages/admin/faculty_import.py`, `states/faculty_bulk_import.py`; `test_faculty_bulk_import.py` (33). |
| HoD recommend-via leave matrix (designation/employee-type-keyed) | E-021 | M10 | Shipped | `services/leave_rules.py`, `config_leave_matrix.py`; `test_leave_hod_recommend_10a.py` (4), `_10b.py` (5). |
| Campus-scoped Director routing | E-019 | M10 | Shipped | Absorbed via `Faculty.campus_id` in the approval/leave engines. |
| Audit label readability for faculty FK fields | TD-087 | M10 | Shipped (Phase 13) | `durgam/audit/labels.py` `faculty` resolver + `FK_FIELDS` for 4 tables. |
| Faculty model/repository/seed backfill | — | M10 | Shipped | `test_faculty_repository.py` (14), `test_faculty_models.py` (7), `test_faculty_seed_backfill.py` (3), `test_faculty_permission_catalog_phase2.py` (16). |
| PAN/Aadhaar encryption-at-rest + sensitive-section UI (Phase P5) | TD-084 | M11 | Deferred | Blocked on an explicit encryption design phase (key storage, rotation, audit-on-decrypt, fixture key). |
| NRF extension workflow (HoD-initiated, university-admin-approved) | TD-085 | M11 | Deferred | Phase 9A shipped only the sys_admin direct-renewal override. |
| Withdrawal notification campus-dept scope | TD-038 | M11 | Deferred | See M8.1 section row above — retargeted from M10 Phase 13 sweep. |
| Leave admin pages campus-scope enforcement | TD-039 | M11 | Deferred | See M8.1 section row above — retargeted from M10 Phase 13 sweep. |
| Leave-balance seed gap (blocks manual leave-flow walkthroughs) | TD-086 | M11 | Deferred | `scripts/seed.py` seeds no `leave_balances` for faculty users. |
| Class coordinator re-introduction (student-bound) | TD-088 | M13 | Deferred | Removed at M10 Phase 11D (Q-P11D.1) pending the student domain; explicitly out of M11 scope. |
