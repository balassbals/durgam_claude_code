# Configuration Module

**RFP reference:** §9.3  
**Milestone:** M3  
**Gate clause:** "All four campuses, four schools, ten departments, sub-departments, centres seeded; one program seeded with full PEO/PO/PSO/regulation/scheme/exit-level data."  
**Extended by E-001:** University and department vision/mission management; viewable by all authenticated users.

---

## Overview

The Configuration module manages the organisational core of SSSIHL: campuses, schools, departments, centres, programs, courses, vision/mission, and singleton operational settings (class timings, working days). It is split into:

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

## Gate Clause

**From §12 M3 row:** "All four campuses, four schools, ten departments, sub-departments, centres seeded; one program seeded with full PEO/PO/PSO/regulation/scheme/exit-level data."

**Extended by E-001:**
- University vision and at least one mission seeded and editable by Registrar.
- At least one department's (DMACS) vision and at least one mission seeded and editable by its HoD.
- View access works for all authenticated roles via `/about/*` pages.
- Delete attempts at the service layer raise `NotDeletableError`.

---

## Future Work

| Milestone | What it adds to this module |
|---|---|
| **M4** (Configuration — AY & Calendar) | AcademicYear locking, calendar collaboration chain, holiday management, StudentCategoryCount |
| **M5** (Configuration — Identity Attachments) | LetterheadAsset, MentalHealthCounsellor roster, FacultyMentorAssignment, ClassTeacherAssignment, ClassCoordinatorAssignment, UGTimetable, TemplateAsset, RoleEmail UI |
| **M13** (Program & Course Management) | Rich edit UI for Program sub-entities (PEO/PO/PSO forms, regulation editor, scheme builder, specialisation editor, exit-level editor); Course extended fields (course_type, delivery_mode, IKS flags); credit-hour ratio per ProgramRegulation |
