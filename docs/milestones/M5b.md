# M5b — Configuration — Assignments & Approval Config

**RFP reference:** §9.3, §12 M5
**Branch:** `m5b-config-assignments`
**Parent milestone:** M5 — Configuration — Identity Attachments
**Predecessor:** M5a (File Infrastructure & Identity Assets) — gate passed 2026-05-24

---

## Scope

1. DocumentTemplate unification (E-005): merge LetterheadAsset + TemplateAsset
2. Scope-type registry (E-006): extensible scope resolution
3. MentalHealthCounsellor roster (AY-scoped, DOCX export)
4. FacultyMentorAssignment (model + thin UI; rich UI at M14)
5. ClassTeacherAssignment (model + thin UI; rich UI at M14)
6. ClassCoordinatorAssignment (model + thin UI; rich UI at M14)
7. VisitingFaculty (E-003: external personnel per department)
8. NonOwnedCourse (course shared across departments)
9. UGTimetable (first/second year, Director's office)
10. ApprovalProcess + PurchaseProcedureRule + PurchaseCommitteeTemplate config (E-007)
11. Designation vocabulary (extensible faculty designation config)
12. Bulk import for courses and programs (users already at M2)

## Sessions

| Session | Commit | What shipped |
|---|---|---|
| 1 | `f1545b2` (combined) | E-005: DocumentTemplate unification (model + repo + service + state + migration) |
| 2 | `f1545b2` (combined) | E-006: Scope-type registry (durgam/scopes/) |
| 3 | `f1545b2` (combined) | MentalHealthCounsellor, ClassTeacher, ClassCoordinator, FacultyMentor models + repos + services + migration |
| 4 | `f1545b2` (combined) | Counsellor + faculty-mentor config UI/states/pages + DOCX download |
| 5 | `f1545b2` (combined) | Class-teacher/coordinator config UI + VisitingFaculty full stack (model→page) |
| 6 | `f1545b2` (combined) | NonOwnedCourse + UGTimetable full stack; 666 tests |
| 7 | `ea72684` | ApprovalProcess + PurchaseProcedureRule + PurchaseCommitteeTemplate + Designation; 724 tests |
| 8 | (this commit) | Bulk import for courses + programs; coverage-matrix close-out; milestone docs |

## Design Decisions

| ID | Decision |
|---|---|
| DD-M5b-1 | Sessions 1-6 squashed into a single commit (f1545b2) for clean revert boundary |
| DD-M5b-2 | PurchaseCommitteeTemplate uses eligible_designations (ordered JSONB) + faculty_member_count + fixed_role_members instead of member_role_codes (fix #2 from Session 7) |
| DD-M5b-3 | Designation is an extensible config table, NOT a hardcoded enum (fix #3) |
| DD-M5b-4 | Overlap validation with self-exclusion on update (fix #1) |
| DD-M5b-5 | BOM stored as literal string in approving_authority_role_codes — offline statutory body; M7 handles as offline approval |
| DD-M5b-6 | Campus purchase committee: director_excluded=True (Director comments+forwards, NOT a member) |
| DD-M5b-7 | Projects/UGC tier-2 floor normalized from PDF's 10,000 to 10,001 to avoid overlap with tier-1 ceiling |
| DD-M5b-8 | Bulk import: @require_role(resource="user") decorator + fine-grained can() check in handler body for course:write / program:write |

## Forward Concerns

- **M7**: Rank-preference enforcement, availability/fatigue check, justification field (all require M10 Faculty model + M7 purchase-request artifact)
- **M10**: Faculty model enables rich assignment UI + committee member selection
- **M11**: Project-fund link to PI's faculty record
- **M12**: Student model enables rich class-teacher/coordinator UI
- **M14**: Rich UI for assignments (FacultyMentor, ClassTeacher, ClassCoordinator)

## Gate Checklist

- [x] Full suite passes 3x with deterministic count
- [x] All M5b coverage-matrix rows → Shipped
- [x] Deferred concerns visible in coverage matrix
- [x] Clean working tree
- [x] Per-session commits visible in git log

---

## Gate Close-out (date: 2026-06-02)

### Final commit
- `9db7d6e` fix(M5b): gate-verification round 6 (counsellor download URL via rx.redirect, hide admin back-link for non-admin importers)

### What shipped
- Mental health counsellors (DSW + Director family ownership, render-after-confirm save with staged uploads persisting correctly, DOCX-on-letterhead export with placeholder warning)
- Faculty mentor assignments (Director-family ownership, DOCX-on-letterhead download with placeholder warning, confirm-roster flow with is_confirmed gating download, button hidden when no entries)
- Class teacher assignments (HoD-owned, AY-locked, dept-auto-scoped for HoD family, max-2-per-class enforced)
- Class coordinator assignments (corrected concept: student assigned by class teacher; viewable-by-all read; placeholder write until M10/M12)
- Non-regular faculty (renamed from VisitingFaculty; type field with visiting/adjunct/guest/contract/honorary; HoD-owned create; Director-or-Registrar approval action; pending → approved transition with approver name and timestamp)
- Non-owned courses (Director/DAA-family ownership; corrected model — no department_id since courses belong to no department)
- UG timetable (Director-family ownership; placeholder for class-label refactor)
- Bulk import (Users / Courses / Programs three tabs; per-resource permissions program_import / course_import; tab visibility gated; admin back-link hidden for non-admin importers)
- Approval process configuration (channel as ordered multi-select with visible order; informational_cc_role_codes field for travel-CC; FACULTY role in requestor dropdown)
- Purchase procedure rules (10 tier rows, Finance-owned, candidate-set semantic for approver field)
- Purchase committee templates (Finance-owned, designation-based eligibility, escalation designate)
- Document template unification (E-005: LetterheadAsset + TemplateAsset → DocumentTemplate; letterhead per-role no scope; live-sourced role picker; Replace File kebab action)
- VAC Certificate label correction
- Designation table with rank ordering
- Calendar email recipients resolved per-user via User+UserRole join (not RoleEmail config)
- Calendar export reformatted: Title / Start / End / Scope columns; em-dash Unicode support via DejaVu Sans
- Dean role collapsed (DEAN_SCI/HSS/LL/MC merged into single DEAN role with school scope via UserRole)

### What was decided (binding)
- E-005: DocumentTemplate unification
- E-006: Scope-type registry pattern for live-sourced dropdowns
- E-007: Purchase committee topology; ownership map (Finance Officer owns); R1 candidate-set semantic ("position 0 = immediate next-step, positions 1+ = unordered candidate pool the position-0 approver picks one of at runtime")
- E-008: Per-entity bulk-import permissions (program_import for Registrar family, course_import for HoD family + AHOD + HOD_OFFICE)
- Role-picker principle: all role-code fields sourced live from roles table, never free text, never hardcoded enum
- Scope-label resolution helper shared across role-email / calendar / role-picker UIs
- Counsellor and faculty mentor download flows produce DOCX rendered into Director letterhead; warning flash when letterhead lacks {{ }} placeholders
- Non-regular faculty direct-approve action is the M5b placeholder; replaced at M7 by the approval-requests module

### Forward concerns (recorded; not built at M5b)
Confirm coverage_matrix.md has all of these; this block is the index, the matrix is the canonical record:
- UGTimetable → ClassTimetable rename + class-label refactor (separate focused pass)
- Faculty/student dropdowns on assignment pages → M10/M12/M14
- Bulk-add and advanced search for campuses/depts/programs → M13
- Viewability-of-basic-info-by-all → dashboard milestone
- Sub-departments management → future
- Class teacher / non-owned-course load → faculty workload at M10
- Course-code dropdown auto-fill on NonOwnedCourse → M14
- Announcement composer roster → M9
- M7 obligations: HoD picks from candidate set; informational_cc_role_codes notification; non-regular faculty approval routing
- Class coordinator student picker → M12
- Older M2/M3/M4 pages audit for hardcoded/free-text role fields → UI polish
- Faculty mentor roster letterhead overlay polish (auto-fill campus/director/designation from login scope) → M14 docgen polish
- Counsellor roster letterhead overlay polish → M14 docgen polish

### Verification record
Six rounds of gate-fix were required after the agent's initial "738 passing, ready to ship" report:
- Round 1 (A1-G2): Select empty-string crash, Director nav, DAA over-grant, HoD dept auto-scope, class-coordinator model correction, live-sourced role picker, letterhead scope removal with E-005-grade migration, label fixes
- Round 2 (H1-T1): Counsellor render-after-confirm rewrite, export-roster rx.download, DEAN role collapse, calendar emails resolve per-user, ordered channel display, informational_cc field, 13 new demo users seeded (offices, AHOD, FACULTY, coordinators)
- Round 3 (U1-BB1): UserRole.is_deleted regression (the agent's "not reproducible" finding had been wrong), PDF Unicode em-dash, permission grants for HoD/AHoD/HoD-Office on courses, per-entity bulk-import permissions, counsellor download kebab, docgen silent-failure warning, faculty mentor confirmation flow, dynamic phase-3 role computation, non-regular faculty rename
- Round 4 (CC1-EE1): Counsellor download URL missing /api/, docgen warning surfaced to user via tuple-return + flash, bulk-import _admin_guard replaced with _config_guard_any, non-regular faculty approve action, mentor confirm button hidden when no entries
- Round 5 (FF1-FF4): Counsellor save flow was silently dropping file_ids on create path (root-cause; previous URL fixes had been correct but the path never had file_ids to render), bulk-import tab visibility, NRF approve grant broadened to Registrar family, faculty mentor download CSV → DOCX-on-letterhead
- Round 6 (GG1-GG2): Counsellor download rx.download URL validation rejected DOWNLOAD_PREFIX'd string — replaced with rx.redirect pattern matching letterheads, admin back-link hidden for non-admin importers

### Test count progression
- M5b initial commit (Session 8 close): 738 passing
- Round 5 final: 734 passing (some tests refactored across rounds, net stable)
- Final close-out: 734 passing, 3x deterministic against fresh DB

### Seed counts at close
- 27 roles, 25 demo users, ~100 permission triples, ~100+ role-permission bindings
