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
| ApprovalProcess (runtime execution) | §9.5 | M7 | Planned for M7 | Generic approval engine consumes M5b config; CPC fund-release fully wired. |
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

---

## Deferred Forward-Concerns (from M5b)

| Concern | Source | Deferred to | Notes |
|---|---|---|---|
| Faculty bulk import (CSV) | §9.3, §16 | M10 | Requires Faculty model |
| Student bulk import (CSV) | §9.3, §16 | M12 | Requires Student model |
| Purchase committee rank-preference enforcement | E-007 | M7 | Runtime concern: highest-rank-first selection from eligible_designations requires M10 Faculty model for who-exists/availability |
| Purchase committee availability/fatigue check | E-007 | M7 | Runtime concern: reject faculty serving on too many concurrent committees; requires M10 Faculty model |
| Purchase committee justification field | E-007 | M7 | Runtime concern: text justification when lower-ranked faculty selected; requires purchase-request artifact (M7) |
| Project-fund link to PI | E-007 | M11 | Runtime concern: link project fund source to PI's faculty record; requires M10 Faculty + M11 Research |
| ClassCoordinatorAssignment ownership transfer to class-teacher role | §9.3 | M14 | Requires M10 Faculty identity + M12 Student model for student-picker. Current HoD/SysAdmin write access is a placeholder |
| Committee member selection (rank-preference, availability) | E-007 | M10/M14 | Requires M10 Faculty model for who-exists/who's-available lookup |
| Rank-preference enforcement, availability/fatigue check, justification field | E-007 | M7/M10 | Requires M10 Faculty + M7 purchase-request artifact |
| Retrofit older config pages (M3/M4) with live-sourced role picker | UI Polish | UI Polish | M5b established `role_multi_select()` and `_load_role_options()` patterns; older pages not yet retrofitted |

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
   all users with the target role receive the email; per-user opt-out is a M9
   concern. → M9.
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
    when Director confirms a campus mentor roster. → M9.
16. **Faculty mentor roster letterhead overlay** — fitting mentor roster content
    into letterhead template requires docgen polish. → M14.

---

## M13 Inheritance Note

Rich management UI for Program sub-entities (PEO/PO/PSO editing forms, regulation
editors, scheme builder, specialisation editor, exit-level editor) defers to M13
(Program & Course Management). The M3 gate clause is met by the seed alone; the data
model exists and is verified by integration tests.
