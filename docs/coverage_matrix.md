# §9.3 Configuration Module — Traceability Matrix

This matrix tracks coverage of RFP §9.3 (Configuration Module) across
milestones M3-M7 and parts of M14-M15. The §9.3 spec is the largest single
module specification in the RFP. This matrix ensures no requirement is
silently dropped between milestones.

**Updated at every milestone gate.** For in-flight milestones, rows whose
status is "In flight at M{N}" reflect the current implementation state.

**M3 gate passed: 2026-05-21.** All M3 rows verified via fresh-clone ritual.

Errata bindings: E-001 (vision/mission) extends the M3 row.

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
| AcademicYear (code, dates, is_locked) | §8.5, §9.3 | M0/M3 | Shipped at M0 | Locked state management → M4 |
| ClassTimingsConfig (singleton) | §9.3 | M3 | Shipped at M3 | Singleton edit page (Session 7); HH:MM validation; configure action only |
| WorkingDaysConfig (singleton) | §9.3 | M3 | Shipped at M3 | Singleton edit page (Session 7); 5/6-day radio; configure action only |
| Faculty (basic info in config module) | §9.3 | M10 | Planned for M10 | Faculty profile module |
| Student (basic info in config module) | §9.3 | M12 | Planned for M12 | Student profile module |
| RoleEmail (email bound to role/scope) | §9.3 | M2/M5 | Shipped at M2 (model); M5 for UI | M2 seeded; UI for admin in M5 |
| LetterheadAsset (file per role/scope) | §9.3 | M5 | Planned for M5 | Configuration — Identity Attachments |
| ApprovalProcess (workflow config) | §9.3 | M7 | Planned for M7 | Approval Engine |
| StudentCategoryCount (SC/ST/OBC/EWS/General per AY) | §9.3 | M4 | Planned for M4 | AY-scoped, Registrar-managed |
| MentalHealthCounsellor (AY-scoped roster, Director's letterhead) | §9.3 | M5 | Planned for M5 | Configuration — Identity Attachments |
| FacultyMentorAssignment | §9.3 | M5 | Planned for M5 | Requires Faculty (M10) model — see M5 inheritance note |
| ClassTeacherAssignment | §9.3 | M5 | Planned for M5 | Requires Faculty (M10) + Student (M12) — see M5 note |
| ClassCoordinatorAssignment | §9.3 | M5 | Planned for M5 | Same dependency as ClassTeacher |
| NonOwnedCourse | §9.3 | M5 | Planned for M5 | Course shared across departments |
| UGTimetable (first/second year, Director's office) | §9.3 | M5 | Planned for M5 | Auto-projects into dept timetables |
| TemplateAsset (BoS, MoM, VAC certificate) | §9.3 | M5 | Planned for M5 | IQAC-managed; used for docgen |

---

## Behaviours

| Requirement | Source | Milestone | Status | Notes |
|---|---|---|---|---|
| Schools seeded once; departments declare school | §9.3 | M3 | Shipped at M3 | Seed script; school_id FK enforced |
| Bulk-add by CSV/Excel (users, faculty, students, courses, programs) | §9.3, §16 | M5 | Planned for M5 | Explicitly out of scope at M3 (Refinement 7) |
| AY-scoped configs immutable on rollover (is_locked=true) | §9.3 | M4 | Planned for M4 | Nightly lock job; AcademicYearLockedError in repos |
| Calendar collaboration chain (Registrar → IQAC → others) | §9.3 | M4 | Planned for M4 | Precedence chain; each role edits own entries |
| Holiday management | §9.3 | M4 | Planned for M4 | Calendar entries with holiday type |
| Calendar exports (CSV/Excel/PDF/DOCX) | §9.3 | M4 | Planned for M4 | Export service |
| Letterheads / templates used for docgen (not directly visible to other roles) | §9.3 | M5 | Planned for M5 | Internal composition; BoS/MoM/VAC |
| Mental-health counsellor roster downloadable as DOCX (Director letterhead, AY-scoped) | §9.3 | M5 | Planned for M5 | Immutable on AY rollover |
| Class teacher assignments auto-flow into faculty workload | §9.3 | M5 | Planned for M5 | Requires Faculty (M10) model |
| UG timetable configured by Director, auto-projected to dept timetables | §9.3 | M5 | Planned for M5 | Requires Student (M12) model |
| Student category counts managed by Registrar/office per AY; read-only for non-Student roles | §9.3 | M4 | Planned for M4 | AY-scoped; immutable on rollover |
| Vision/mission: update-only, no delete (university + department) | E-001 | M3 | Shipped at M3 | NotDeletableError in VisionMissionService |
| Vision/mission: viewable by all authenticated users | E-001 | M3 | Shipped at M3 | /about/university + /about/departments + /about/departments/[code] — Session 7 |
| Class timings and working-days config: singleton, configure action | §9.3, §12 M3 | M3 | Shipped at M3 | Singleton edit forms; configure-action guard; Session 7 |
| "System admin will only deal with basic information of academic departments when adding, editing" | §9.3 | M3 | Shipped at M3 | department:write:* granted only to SYSTEM_ADMIN (fixed M3 Session 5c — Registrar had it incorrectly) |
| Dean role bound to school via dean_role_code string reference | §8.2 | M3 | Shipped at M3 | OQ-M3-6 confirmed: plain string, no FK |

---

## M5 Inheritance Note (from M3)

ClassTeacher, ClassCoordinator, and FacultyMentor assignments are scheduled for M5
(Configuration — Identity Attachments) per §12. However, these assignments reference
Faculty (M10) and Student (M12), which arrive after M5. M5 planning must decide:

- **Option A (recommended):** Ship the assignment data model + schema at M5; leave UI as
  a placeholder; implement full UI at M14 (Department module) when both Faculty and Student
  exist.
- **Option B:** Fully defer to M14 when all referenced entities are available.

This note was added at M3 close-out. See `docs/milestones/M3.md` Session 5 resume notes.

---

## M13 Inheritance Note

Rich management UI for Program sub-entities (PEO/PO/PSO editing forms, regulation
editors, scheme builder, specialisation editor, exit-level editor) defers to M13
(Program & Course Management). The M3 gate clause is met by the seed alone; the data
model exists and is verified by integration tests.
