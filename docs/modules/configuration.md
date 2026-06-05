# Configuration Module

**RFP reference:** §9.3  
**Milestones:** M3, M4, M5a, M5b  
**Gate clause:** "All four campuses, four schools, ten departments, sub-departments, centres seeded; one program seeded with full PEO/PO/PSO/regulation/scheme/exit-level data."  
**Extended by E-001:** University and department vision/mission management; viewable by all authenticated users.

---

## Overview

The Configuration module manages the organisational core of SSSIHL: campuses, schools, departments, centres, programs, courses, vision/mission, singleton operational settings (class timings, working days), personnel assignments (counsellors, mentors, class teachers/coordinators, visiting faculty), timetables, approval processes, purchase policy rules, and bulk data import. It is split into:

- **Admin config pages** (`/admin/config/*`) — write/configure access; gated by role.
- **About pages** (`/about/*`) — read-only; accessible to all authenticated users.

---

## Entities

| Entity | Table | Key constraints |
|---|---|---|
| Campus | `campuses` | Unique `code`; soft-delete only |
| School | `schools` | Unique `code`; `dean_role_code` is a plain string (not a FK) |
| Department | `departments` | Unique `code`; FK `school_id`; multi-campus via `department_campuses` join |
| DepartmentCampus | `department_campuses` | Join table; created automatically on dept create |
| SubDepartment | `subdepartments` | FK `department_id`; read-only at M3 (no write UI) |
| SubDepartmentCampus | `subdepartment_campuses` | Join table |
| CentreOfExcellence | `centres_of_excellence` | Unique `code`; soft-delete only |
| Program | `programs` | FK `department_id`; read-only detail at M3; rich edit defers to M13 |
| ProgramOutcome | `program_outcomes` | Types: PEO / PO / PSO |
| ProgramRegulation | `program_regulations` | Year-based regulation periods |
| ProgramSchemeOfInstruction | `program_schemes_of_instruction` | Per regulation, per semester |
| ProgramSchemeCourse | `program_scheme_courses` | Courses in a scheme |
| ProgramSpecialisation | `program_specialisations` | Optional specialisation tracks |
| ProgramExitLevel | `program_exit_levels` | B.Sc., M.Sc., etc. |
| Course | `courses` | Unique `code`; FK `program_id` + `department_id`; credits auto-derived |
| UniversityVisionMission | `university_vision_missions` | Singleton; update-only (E-001) |
| UniversityMission | `university_missions` | Ordered per `display_order`; FK to singleton |
| DepartmentVisionMission | `department_vision_missions` | One per department; unique on `department_id` |
| DepartmentMission | `department_missions` | Ordered; FK to dept VM row |
| ClassTimingsConfig | `class_timings_configs` | Singleton; `configure` action only |
| WorkingDaysConfig | `working_days_configs` | Singleton; `configure` action only |

| AcademicYear | `academic_years` | Unique `code`; `is_locked`, `master_calendar_locked`, `iqac_confirmed` flags |
| Holiday | `holidays` | AY-scoped; unique `(holiday_date, academic_year_id)` |
| StudentCategoryCount | `student_category_counts` | AY-scoped singleton; unique `academic_year_id` |
| CalendarEntry | `calendar_entries` | AY-scoped; `entry_type` from 18 fixed types; `owner_user_id`, `owner_role_code` |
| RoleEmail | `role_emails` | Unique `(role_code, scope_type, scope_id)` via partial unique indexes; UUID PK (re-keyed at M5a E-004) |
| FileAsset | `file_assets` | Cross-cutting; `storage_key` + `purpose` field for permission escalation |
| LetterheadAsset | `letterhead_assets` | Partial unique indexes: global `(role_code)` + scoped `(role_code, scope_type, scope_id)` WHERE `is_deleted=false` |
| TemplateAsset | `template_assets` | Partial unique index on `template_type` WHERE `is_deleted=false`; types: `bos`, `mom`, `vac` |
| DocumentTemplate | `document_templates` | E-005 unification of LetterheadAsset + TemplateAsset; one letterhead per `(purpose, role_code)` |
| MentalHealthCounsellor | `mental_health_counsellors` | AY-scoped; unique `(academic_year_id, name)` WHERE `is_deleted=false` |
| FacultyMentorAssignment | `faculty_mentor_assignments` | AY-scoped; FK `department_id`; thin UI at M5b, rich UI at M14 |
| ClassTeacherAssignment | `class_teacher_assignments` | AY-scoped; FK `department_id`; unique `(academic_year_id, department_id, year_of_study, section)` |
| ClassCoordinatorAssignment | `class_coordinator_assignments` | AY-scoped; FK `department_id`; unique `(academic_year_id, department_id, year_of_study)` |
| VisitingFaculty | `visiting_faculty` | FK `department_id`; unique `(department_id, name)` WHERE `is_deleted=false` |
| NonOwnedCourse | `non_owned_courses` | FK `course_id`, `owning_department_id`, `teaching_department_id`; unique on `(course_id, teaching_department_id)` |
| UGTimetable | `ug_timetables` | AY-scoped; `year_of_study` (1 or 2); Director's office |
| ApprovalProcess | `approval_processes` | Unique `process_type` WHERE `is_deleted=false`; `ordered_steps` JSONB |
| PurchaseProcedureRule | `purchase_procedure_rules` | Unique `(fund_source, tier)` WHERE `is_deleted=false`; `amount_floor`/`amount_ceiling` with overlap validation |
| PurchaseCommitteeTemplate | `purchase_committee_templates` | Unique `committee_type` WHERE `is_deleted=false`; `eligible_designations` ordered JSONB |
| Designation | `designations` | Extensible faculty designation config; unique `code`; ordered by `rank` |

All entities inherit `TimestampedSoftDelete` (id UUID v4, created_at, updated_at, is_deleted, etc.).

---

## Services

| Service | Key methods | Notable behaviour |
|---|---|---|
| `CampusService` | `create`, `update`, `soft_delete`, `list` | Hard-delete blocked if departments reference the campus |
| `SchoolService` | same shape | Hard-delete blocked if departments reference the school |
| `DepartmentService` | `create`, `update`, `soft_delete`, `add_campus`, `remove_campus` | `create` auto-creates `DepartmentCampus` join row for `main_campus_id` |
| `CentreService` | same as Campus | Stand-alone; no FK dependencies |
| `ProgramService` | `list_all`, `get_detail` | Read-only at M3 |
| `CourseService` | `create`, `update`, `soft_delete` | Credits auto-derived: `L + T + (P // PRACTICAL_CREDIT_RATIO)` where ratio = 2 |
| `VisionMissionService` | `get_or_create_*_vm`, `update_*_vision`, `add_*_mission`, `update_*_mission`, `move_*_mission`, `remove_*_mission`, `delete_*_vm` (raises NotDeletableError) | Delete stubs always raise `NotDeletableError` (E-001). Individual mission statements can be removed (soft-deleted) |
| `ConfigSingletonService` | `get_class_timings`, `save_class_timings`, `get_working_days`, `save_working_days` | Both configs are singletons; `get_or_create` handles first-run |
| `AcademicYearService` | `create`, `update`, `soft_delete`, `list_all`, `lock_master_calendar`, `confirm_iqac`, `lock_for_rollover` | `lock_master_calendar` and `confirm_iqac` are irreversible; `lock_for_rollover` sets `is_locked=True` |
| `CalendarEntryService` | `create`, `update`, `soft_delete`, `list_by_ay` | Three-phase gate in `create()`; ownership enforcement in `update`/`soft_delete`; 18 fixed entry types via `ENTRY_TYPE_ROLE_MAP` |
| `HolidayService` | `create`, `update`, `soft_delete`, `list_by_ay` | AY-scoped; date validation; blocked when AY locked |
| `StudentCategoryCountService` | `get_or_create`, `update` | AY-scoped singleton; blocked when AY locked |
| `CalendarExportService` | `export_csv`, `export_excel`, `export_pdf`, `export_docx` | Takes list of entries; returns bytes |
| `RoleEmailService` | `list_all`, `create`, `update`, `soft_delete` | Role-code + email; scope validation; Registrar family only |
| `UploadService` | `upload(data, name, mime, actor, purpose)` | Validates, hashes, stores via backend; returns FileAsset |
| `LetterheadAssetService` | `upload_letterhead`, `soft_delete`, `list_all` | MIME filter (PDF/PNG/JPG); max 5 MB; replace = soft-delete old + upload new |
| `TemplateAssetService` | `upload_template`, `soft_delete`, `list_all` | Type-specific MIME (bos/mom=DOCX, vac=PPTX); max 2 MB; replace = soft-delete old + upload new |
| `DocumentTemplateService` | `upload`, `soft_delete`, `list_all`, `get_for_scope` | E-005 unified template management; scope-aware |
| `MentalHealthCounsellorService` | `create`, `update`, `soft_delete`, `list_by_ay`, `export_docx` | AY-scoped; DOCX export with Director letterhead |
| `FacultyMentorAssignmentService` | `create`, `update`, `soft_delete`, `list_by_ay` | AY-scoped; thin management (rich UI at M14) |
| `ClassTeacherAssignmentService` | `create`, `update`, `soft_delete`, `list_by_ay` | AY-scoped; unique per (AY, dept, year, section) |
| `ClassCoordinatorAssignmentService` | `create`, `update`, `soft_delete`, `list_by_ay` | AY-scoped; unique per (AY, dept, year) |
| `VisitingFacultyService` | `create`, `update`, `soft_delete`, `list_by_department` | Per-department external personnel (E-003) |
| `NonOwnedCourseService` | `create`, `update`, `soft_delete`, `list_all` | Cross-department course sharing |
| `UGTimetableService` | `create`, `update`, `soft_delete`, `list_by_ay` | AY-scoped; year 1/2; Director's office |
| `ApprovalProcessService` | `create`, `update`, `soft_delete`, `list_all` | Ordered approval steps per process type |
| `PurchaseProcedureRuleService` | `create`, `update`, `soft_delete`, `list_all` | Overlap validation with self-exclusion on update (DD-M5b-4) |
| `PurchaseCommitteeTemplateService` | `create`, `update`, `soft_delete`, `list_all` | `eligible_designations` ordered JSONB + `faculty_member_count` (DD-M5b-2) |
| `DesignationService` | `create`, `update`, `soft_delete`, `list_all` | Ordered by rank; extensible config (DD-M5b-3) |
| `BulkImportService` | `validate_user_csv`, `commit_user_import`, `validate_course_csv`, `commit_course_import`, `validate_program_csv`, `commit_program_import` | Two-stage validate→commit; users (M2), courses + programs (M5b); faculty/student deferred to M10/M12 |

---

## Pages and Routes

### Admin config pages

| Route | Guard | State | Owner roles |
|---|---|---|---|
| `/admin/config` | `_config_guard_any(all write/configure gates)` | `ConfigLandingState` | All with any config permission |
| `/admin/config/campuses` | `campus:write:*` | `CampusConfigState` | SYSTEM_ADMIN |
| `/admin/config/schools` | `school:write:*` | `SchoolConfigState` | SYSTEM_ADMIN |
| `/admin/config/departments` | `department:write:*` | `DepartmentConfigState` | SYSTEM_ADMIN |
| `/admin/config/centres` | `centre:write:*` | `CentreConfigState` | SYSTEM_ADMIN |
| `/admin/config/programs` | `program:write:*` | `ProgramConfigState` | SYSTEM_ADMIN (read-only detail) |
| `/admin/config/courses` | `course:write:*` | `CourseConfigState` | SYSTEM_ADMIN |
| `/admin/config/vision-mission` | `_config_guard_any([univ_vm:write, dept_vm:write:dept])` | `VisionMissionConfigState` | SYSTEM_ADMIN, Registrar family, HoD family |
| `/admin/config/vision-mission/departments/[code]` | Scope-specific `dept_vm:write:department` for exact dept | `DeptVMConfigState` | HoD/AHoD/HoDOffice scoped to that dept |
| `/admin/config/class-timings` | `class_timings_config:configure:*` | `ClassTimingsConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/working-days` | `working_days_config:configure:*` | `WorkingDaysConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/academic-years` | `academic_year:write:*` | `AcademicYearConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/holidays` | `holiday:write:*` | `HolidayConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/student-categories` | `student_category_count:write:*` | `StudentCategoryConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/calendar` | `calendar_entry:write:*` | `CalendarEntryConfigState` | All calendar-owning roles (phase-gated) |
| `/admin/config/role-emails` | `role_email:write:*` | `RoleEmailConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/letterheads` | `letterhead_asset:write:*` | `LetterheadConfigState` | SYSTEM_ADMIN, Registrar family |
| `/admin/config/templates` | `template_asset:write:*` | `TemplateConfigState` | SYSTEM_ADMIN, IQAC_COORDINATOR |
| `/admin/config/counsellors` | `mental_health_counsellor:write:*` | `CounsellorConfigState` | SYSTEM_ADMIN, DIRECTOR |
| `/admin/config/faculty-mentors` | `faculty_mentor_assignment:write:*` | `FacultyMentorConfigState` | SYSTEM_ADMIN, DIRECTOR |
| `/admin/config/class-teachers` | `class_teacher_assignment:write:*` | `ClassTeacherConfigState` | SYSTEM_ADMIN |
| `/admin/config/class-coordinators` | `class_coordinator_assignment:write:*` | `ClassCoordinatorConfigState` | SYSTEM_ADMIN |
| `/admin/config/visiting-faculty` | `visiting_faculty:write:*` | `VisitingFacultyConfigState` | SYSTEM_ADMIN |
| `/admin/config/non-owned-courses` | `non_owned_course:write:*` | `NonOwnedCourseConfigState` | SYSTEM_ADMIN |
| `/admin/config/ug-timetable` | `ug_timetable:write:*` | `UGTimetableConfigState` | SYSTEM_ADMIN, DIRECTOR |
| `/admin/config/approval-processes` | `approval_process:write:*` | `ApprovalProcessConfigState` | SYSTEM_ADMIN |
| `/admin/config/purchase-rules` | `purchase_procedure_rule:write:*` | `PurchaseRuleConfigState` | SYSTEM_ADMIN |
| `/admin/config/purchase-committees` | `purchase_committee_template:write:*` | `PurchaseCommitteeConfigState` | SYSTEM_ADMIN |
| `/admin/config/designations` | `designation:write:*` | `DesignationConfigState` | SYSTEM_ADMIN |
| `/admin/import` | `user:write:*` + fine-grained `can()` for `course:write` / `program:write` | `BulkImportState` | SYSTEM_ADMIN |

### About pages (read-only, all authenticated users)

| Route | State | Content |
|---|---|---|
| `/about/university` | `AboutUniversityState` | University vision + ordered mission statements |
| `/about/departments` | `AboutDeptListState` | All active departments with V&M status |
| `/about/departments/[code]` | `AboutDeptDetailState` | Single dept vision + ordered missions |

About pages use `rx.cond(AuthState.current_user_id != "", content, rx.fragment())` — no admin guard.

---

## Patterns Established at M3

These patterns are canonical (see CLAUDE.md for full examples):

1. **`open_session()` does NOT auto-commit** — every write handler must call `session.commit()` inside the `with open_session() as session:` block.

2. **`rx.form(on_submit=State.handler)` for all forms** — guarantees form data reaches the handler. Handler receives `form_data: dict`.

3. **`_config_guard(resource, action="write")`** — defaults to `write` (not `read`). All config pages guard with write or configure action.

4. **Flash lifecycle in handlers that call `load_*`** — set `self.flash` AFTER `await self.load_*()` (the guard inside `load_*` clears flash).

5. **List page loading state** — every list page has `loading: bool = True`; shows spinner until data is ready.

6. **Modal overlay pattern** — create/edit forms render as fixed-position modals via `form_modal()` from `components.py`.

7. **Config toast** — `config_toast(State.flash, State.flash_type, State.dismiss_flash)` fixed-position, bottom-right, with ✕ close.

8. **Cancel button `type="button"`** — prevents form submit on Cancel.

9. **Pre-populate form fields before `show_form = True`** — prevents stale values in edit mode.

10. **Auto-create join rows on entity create** — e.g., `DepartmentCampus` row created in same transaction as `Department`.

11. **Singleton config pattern** — `get_or_create` on load; save updates the same row; no delete exposed.

12. **Update-only entity UI pattern** — no delete button anywhere on V&M pages; `VisionMissionService.delete_*` always raises `NotDeletableError` (E-001).

13. **About-page read-only pattern** — `rx.cond(AuthState.current_user_id != "", ...)` instead of admin guard; `_resolve_session()` in on_load handler.

14. **`from __future__ import annotations`** — required in all service files to avoid `list` builtin shadowing (see `list` method naming note below).

15. **Never name a service method `list`** — shadows the Python builtin; use `list_all`, `list_campuses`, etc.

---

## UI Principles (from M5b)

1. **All role-code fields must be sourced from the live roles table** via `BaseState._load_role_options()`. Single-role fields use `rx.select`. Multi-role fields use the `role_multi_select()` checkbox component from `durgam/pages/components.py`. Free-text role code entry is prohibited.

2. **Designation fields use `BaseState._load_designation_options()`** and the same `role_multi_select()` component (it accepts any `options` list with `code`/`label` dicts).

---

## Gate Clause

**From §12 M3 row:** "All four campuses, four schools, ten departments, sub-departments, centres seeded; one program seeded with full PEO/PO/PSO/regulation/scheme/exit-level data."

**Extended by E-001:**
- University vision and at least one mission seeded and editable by Registrar.
- At least one department's (DMACS) vision and at least one mission seeded and editable by its HoD.
- View access works for all authenticated roles via `/about/*` pages.
- Delete attempts at the service layer raise `NotDeletableError`.

---

## Three-Phase Calendar Collaboration Chain (M4)

The calendar uses a sequential three-phase model:

1. **Phase 1 — Registrar framework**: 13 types (sem_begin, sem_end, holiday,
   class_suspension, cie, end_sem_exam, admission_exam, phd_admission,
   winter_vacation, summer_vacation, academic_council_meeting,
   finance_committee_meeting, executive_committee_meeting). Creatable when AY
   is unlocked. Roles: REGISTRAR, DEPUTY_REGISTRAR, REGISTRAR_OFFICE, SYSTEM_ADMIN.

2. **Phase 2 — IQAC**: 1 type (activity). Creatable when
   `master_calendar_locked=True` AND `iqac_confirmed=False`. Role: IQAC_COORDINATOR.

3. **Phase 3 — All others**: sports/cultural (DIRECTOR, DEAN_STUDENT_WELFARE only);
   academic_activity/other_activity (any non-STUDENT/BASIC_USER role). Creatable
   when `iqac_confirmed=True`.

Sequential confirm actions trigger phase-transition email notifications:
Registrar confirms → emails IQAC; IQAC confirms → emails all Phase 3 roles.

---

## AY Rollover (M4)

A Celery beat task (`lock_expired_academic_years`) runs nightly at 01:00 UTC.
It queries `ends_on < today AND is_locked=False AND is_deleted=False` and sets
`is_locked=True`. Repositories on AY-scoped models reject all writes against
locked AYs via `AcademicYearLockedError`.

---

## Authenticated File Download (M5a)

All file downloads go through `/api/files/{file_id}`, a Starlette route registered
on Reflex's ASGI underpinning via `app._api.add_route()`.

Authentication: reads `dsession` cookie → resolves session → requires `file_asset:read:*`.

Purpose-based permission escalation: files with `purpose="letterhead"` require
`letterhead_asset:read:*`; files with `purpose="template"` require
`template_asset:read:*`. This prevents users with only `file_asset:read` from
downloading restricted assets.

## Docgen Merge Primitive (M5a)

`durgam.docgen.merge.merge_letterhead_and_content(letterhead_bytes, content_blocks)`
creates a DOCX with a letterhead image in the document header and content blocks
(heading / paragraph / table) in the body. Accepts PNG/JPG image bytes only.
Letterheads are now stored as DOCX templates (E-005), so this image-based primitive
is not used with stored letterheads. DOCX-to-DOCX merge deferred to M5b (TD-012
superseded by E-005).

---

## Future Work

| Milestone | What it adds to this module |
|---|---|
| **M7** (Approval Requests) | Generic approval engine (shipped); NRF_APPROVAL process with post-approval NRF record creation (shipped). Rank-preference enforcement, availability/fatigue check, justification field deferred to M10/M14 (require M10 Faculty). |
| **M10** (Faculty) | Faculty model enables rich assignment UI + committee member selection; faculty bulk import |
| **M11** (Projects & Research) | Project-fund link to PI's faculty record |
| **M12** (Student) | Student model enables rich class-teacher/coordinator UI; student bulk import |
| **M13** (Program & Course Management) | Rich edit UI for Program sub-entities (PEO/PO/PSO forms, regulation editor, scheme builder, specialisation editor, exit-level editor); Course extended fields (course_type, delivery_mode, IKS flags); credit-hour ratio per ProgramRegulation |
| **M14** (Department) | Rich UI for FacultyMentor, ClassTeacher, ClassCoordinator assignments (thin UI shipped at M5b) |
