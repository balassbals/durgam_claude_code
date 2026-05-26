# §9.3 Configuration Module — Traceability Matrix

This matrix tracks coverage of RFP §9.3 (Configuration Module) across
milestones M3-M7 and parts of M14-M15. The §9.3 spec is the largest single
module specification in the RFP. This matrix ensures no requirement is
silently dropped between milestones.

**Updated at every milestone gate.** For in-flight milestones, rows whose
status is "In flight at M{N}" reflect the current implementation state.

**M3 gate passed: 2026-05-21.** All M3 rows verified via fresh-clone ritual.

**M4 gate passed: 2026-05-23.** All M4 rows verified via fresh-clone ritual.

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
| LetterheadAsset (file per role/scope) | §9.3 | M5a | Shipped at M5a | Upload/replace/deactivate/download; partial unique indexes (global + scoped); MIME filter (PDF/PNG/JPG); max 5 MB; `/admin/config/letterheads` |
| ApprovalProcess (workflow config — schema + CPC config) | §9.3, §8.4 | M5b | In flight at M5b | Schema exists in crosscutting.py; M5b adds config UI + service + seeds CPC_FUND_RELEASE process. Runtime execution stays M7. |
| ApprovalProcess (runtime execution) | §9.5 | M7 | Planned for M7 | Generic approval engine consumes M5b config; CPC fund-release fully wired. |
| PurchaseProcedureRule (spend-tier config, Finance-owned) | Purchase Procedures doc, §9.5, E-007 | M5b | In flight at M5b | 5 tiers × 2 fund sources (institute_budgeted / projects-ugc); floor/ceiling, min-quotes, comparative-statement, committee_level per tier. committee_level implies topology (none→sequential, committee→concurrent per E-007). Owned by Finance Officer/Office; editable config. |
| PurchaseCommitteeTemplate (committee composition policy, Finance-owned) | E-007 | M5b | In flight at M5b | Per committee type: member-role set, escalation designate, external_expert_mode, no-committee route options. Editable so procedure changes need no code change. Per-purchase assembly is M7 runtime. |
| StudentCategoryCount (SC/ST/OBC/EWS/General per AY) | §9.3 | M4 | Shipped at M4 | AY-scoped singleton edit; Registrar-managed; blocked when AY locked |
| MentalHealthCounsellor (AY-scoped roster, Director's letterhead) | §9.3 | M5b | Planned for M5b | Configuration — Identity Attachments |
| FacultyMentorAssignment | §9.3 | M5b | Planned for M5b | Requires Faculty (M10) model — see M5 inheritance note; Option A confirmed (model + thin UI at M5b, rich UI at M14) |
| ClassTeacherAssignment | §9.3 | M5b | Planned for M5b | Requires Faculty (M10) + Student (M12) — see M5 note; Option A confirmed |
| ClassCoordinatorAssignment | §9.3 | M5b | Planned for M5b | Same dependency as ClassTeacher; Option A confirmed |
| NonOwnedCourse | §9.3 | M5b | Planned for M5b | Course shared across departments |
| UGTimetable (first/second year, Director's office) | §9.3 | M5b | Planned for M5b | Auto-projects into dept timetables |
| TemplateAsset (BoS, MoM, VAC certificate) | §9.3 | M5a | Shipped at M5a | IQAC-managed; types: bos/mom=DOCX, vac=PPTX; partial unique index on type; max 2 MB; `/admin/config/templates` |
| VisitingFaculty (external personnel per department) | E-003, informal req | M5b | Planned for M5b | HoD-managed; inline external-personnel details; date-windowed availability; feeds M13 course allocation; does not depend on M10 Faculty |
| FileAsset + StorageBackend (file storage foundation) | §8.4, §4.1, §6.1 | M5a | Shipped at M5a | Local-fs dev / MinIO prod; UploadService orchestrates validate→store→record; UUID storage keys; purpose-based permission escalation on download endpoint |

---

## Behaviours

| Requirement | Source | Milestone | Status | Notes |
|---|---|---|---|---|
| Schools seeded once; departments declare school | §9.3 | M3 | Shipped at M3 | Seed script; school_id FK enforced |
| Bulk-add by CSV/Excel (users, faculty, students, courses, programs) | §9.3, §16 | M5b | Planned for M5b | Explicitly out of scope at M3 (Refinement 7) |
| AY-scoped configs immutable on rollover (is_locked=true) | §9.3 | M4 | Shipped at M4 | AcademicYearLockedError in repos; lock_for_rollover service method; Celery nightly task |
| Calendar collaboration chain (Registrar → IQAC → others) | §9.3 | M4 | Shipped at M4 | Three-phase sequential chain; 18 fixed entry types; ENTRY_TYPE_ROLE_MAP + phase gates; sports/cultural: DIRECTOR (campus) + DEAN_SW (institution) ownership split |
| Holiday management | §9.3 | M4 | Shipped at M4 | AY-scoped CRUD; separate Holiday model (not CalendarEntry type) |
| Calendar exports (CSV/Excel/PDF/DOCX) | §9.3 | M4 | Shipped at M4 | CalendarExportService + rx.download via bytes data |
| Phase-transition email notifications | §9.3 | M4 | Shipped at M4 | Registrar confirm → IQAC notified; IQAC confirm → Phase 3 roles notified; reads RoleEmail bootstrap placeholders; fire-and-forget via asyncio.create_task |
| Letterheads / templates used for docgen (not directly visible to other roles) | §9.3 | M5a | Shipped at M5a | Letterheads are DOCX templates (E-005); image-based merge primitive exists but not used with DOCX letterheads (TD-012 superseded by E-005); purpose-based download permission escalation |
| Mental-health counsellor roster downloadable as DOCX (Director letterhead, AY-scoped) | §9.3 | M5b | Planned for M5b | Immutable on AY rollover |
| Class teacher assignments auto-flow into faculty workload | §9.3 | M5b | Planned for M5b | Requires Faculty (M10) model |
| UG timetable configured by Director, auto-projected to dept timetables | §9.3 | M5b | Planned for M5b | Requires Student (M12) model |
| Student category counts managed by Registrar/office per AY; read-only for non-Student roles | §9.3 | M4 | Shipped at M4 | AY-scoped singleton edit; immutable on rollover |
| Vision/mission: update-only, no delete (university + department) | E-001 | M3 | Shipped at M3 | NotDeletableError in VisionMissionService |
| Vision/mission: viewable by all authenticated users | E-001 | M3 | Shipped at M3 | /about/university + /about/departments + /about/departments/[code] — Session 7 |
| Class timings and working-days config: singleton, configure action | §9.3, §12 M3 | M3 | Shipped at M3 | Singleton edit forms; configure-action guard; Session 7 |
| "System admin will only deal with basic information of academic departments when adding, editing" | §9.3 | M3 | Shipped at M3 | department:write:* granted only to SYSTEM_ADMIN (fixed M3 Session 5c — Registrar had it incorrectly) |
| Dean role bound to school via dean_role_code string reference | §8.2 | M3 | Shipped at M3 | OQ-M3-6 confirmed: plain string, no FK |

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

## M13 Inheritance Note

Rich management UI for Program sub-entities (PEO/PO/PSO editing forms, regulation
editors, scheme builder, specialisation editor, exit-level editor) defers to M13
(Program & Course Management). The M3 gate clause is met by the seed alone; the data
model exists and is verified by integration tests.
