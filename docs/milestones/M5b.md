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

- [ ] Full suite passes 3× with deterministic count
- [ ] All M5b coverage-matrix rows → Shipped
- [ ] Deferred concerns visible in coverage matrix
- [ ] Clean working tree
- [ ] Per-session commits visible in git log
