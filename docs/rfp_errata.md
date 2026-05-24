# RFP Errata

The DURGAM RFP v3 (`docs/durgam_rfp_v3.pdf`) is the frozen specification. This document captures gaps, ambiguities, and corrections discovered during implementation. Each entry names what the v3 spec missed or got wrong, the source authority (usually the original informal requirements in `docs/durgam_informal_requirements.docx`, or stakeholder confirmations recorded in the milestone planning prompts), and which milestone absorbs the correction.

The RFP itself is NOT re-issued. Single frozen v3 + a growing errata document is cleaner than maintaining v3.1, v3.2, v3.3, etc. Errata are binding alongside the RFP and are read by Claude Code as part of the authority chain in every milestone planning prompt (see CLAUDE.md → Authority files).

Each erratum has a fixed structure:
- **Status** — Acknowledged / In-flight / Resolved-at-M{N}.
- **Source** — where the gap was discovered or what authority documents the missed requirement.
- **Gap in v3 RFP** — what v3 missed or got wrong, with section references.
- **Disposition** — what changes, in which milestone, with enough specificity to drive implementation.

Errata are numbered E-001, E-002, ... in the order discovered. Resolved entries are kept in this file as project history (they explain why decisions were made, for future readers).

---

## E-001 — Vision and mission configuration

**Status**: Acknowledged. M3 in scope.

**Source**: Original informal requirements (`docs/durgam_informal_requirements.docx`), Configuration Module section:

> "Reg, Reg office should be able to configure vision and missions of the university; they should have privilege to update it (no delete allowed here). All should be able to view it."

> "HoD, HoD office (per dept) should be able to configure their dept vision and mission and manage it (no delete allowed here). All others should be able to view vision and mission(s) of any department they want."

Also referenced in the Department Module section of the same document:

> "A department has vision and mission(s) configurable in configuration module by HoD/HoD office."

**Gap in v3 RFP**: §9.3 (Configuration Module) lists "vision and mission" as an example of role-scoped ownership in the Owners line:

> "Owners: System Admin, Registrar / Deputy Registrar / Registrar Office, plus role-scoped owners (HoD for dept vision, Director for campus assets, IQAC for templates, etc.) as listed in the source requirements."

But the v3 RFP does NOT specify:
- A data model entity for university or department vision/mission (no entry in §8).
- The create/update/view behaviour (no module specification in §9.3).
- The "no delete allowed" constraint (an unusual rule worth recording explicitly).
- Inclusion in the M3 milestone gate (§12 M3 row mentions departments and programs but not vision/mission).

This is an omission, not a contradiction. The requirement is real; the RFP just didn't carry it forward into specifications.

**Disposition for M3**:

Add two SQLModel entities (location: `durgam/models/config_anchors.py` or `durgam/models/vision_mission.py`, M3 planning decides):

**UniversityVisionMission** — singleton row holding the university's vision and one or more mission statements.
- Managed by: Registrar, Deputy Registrar, Registrar Office.
- Viewable by: all authenticated users.
- Hard-delete blocked; soft-delete blocked; only update is allowed.
- Fields: `vision: text` (single statement), `missions: list[text]` (one or more mission statements, ordered — stored as a related table `university_mission` keyed on row order, or as JSONB — M3 planning decides the trade-off).
- Standard audit columns from the `TimestampedSoftDelete` mixin apply (created_at, updated_at, created_by, updated_by).

**DepartmentVisionMission** — one row per `Department`.
- Managed by: the department's HoD, AHoD, HoD Office.
- Viewable by: all authenticated users.
- Same delete constraint as UniversityVisionMission.
- Fields: `department_id: UUID` (FK to departments), `vision: text`, `missions: list[text]` (same options as above).
- Standard audit columns apply.

**Permission triples** to add to the M3 seed:
- `university_vision_mission:read:*` — granted to all roles (or rely on the "all authenticated users can view" pattern via BASIC_USER fallback, M3 planning decides which is cleaner).
- `university_vision_mission:write:*` — granted to SYSTEM_ADMIN, REGISTRAR, DEPUTY_REGISTRAR, REGISTRAR_OFFICE.
- `department_vision_mission:read:*` — granted to all roles.
- `department_vision_mission:write:department` — granted to HOD, AHOD, HOD_OFFICE (scope-restricted to their own department).

No delete permission triple is created. Hard-delete and soft-delete are not exposed via UI or service. Repository-level safeguards prevent any delete attempt.

**M3 gate clause is extended to verify**:
- University vision and at least one mission seeded and editable by Registrar.
- At least one department's vision and at least one mission seeded and editable by its HoD.
- View access works for all authenticated roles.
- Delete attempts (via direct service-layer call) raise a clear error: "Vision/mission entries cannot be deleted; only updated."

**M3 planning prompt must address**:
- Whether missions are stored as JSONB list or as a related table (recommend related table with `display_order` column for clean ordering and individual mission editing).
- Whether university and department vision/mission share a common base model or are separate (recommend separate, since the scoping differs).
- Whether the configuration UI uses the same pattern as other config artefacts in M3 (recommend yes — a `/admin/config/vision-mission` page or section within /admin/config).
- Manual gate verification path: log in as Registrar, edit university vision, save, log out, log in as student, navigate to a "About the University" page (or wherever vision is displayed), see updated vision.

This errata is referenced by `docs/milestones/M3.md` as binding alongside §9.3 of the RFP.

---

## E-002 — Three-phase sequential calendar collaboration chain

**Status**: Resolved-at-M4.

**Source**: Original informal requirements (`docs/durgam_informal_requirements.docx`), Calendar paragraph:

> "Registrar/Registrar office/Deputy Registrar prepares master calendar → confirms → IQAC adds activities → confirms → Directors, Deans, HoDs, and other roles add their entries."

**Gap in v3 RFP**: §9.3 describes calendar collaboration as "Registrar → IQAC → others" with arrows, which was initially read at M4 planning as a two-phase concurrent model (Registrar and IQAC contribute simultaneously, then others join). The informal requirements are more specific: a **three-phase sequential chain** with explicit confirm gates between phases.

The three phases are:
1. **Phase 1 — Registrar framework**: 13 entry types (sem_begin, sem_end, holiday, class_suspension, cie, end_sem_exam, admission_exam, phd_admission, winter_vacation, summer_vacation, academic_council_meeting, finance_committee_meeting, executive_committee_meeting). Creatable when AY is unlocked. Registrar confirms → locks master calendar.
2. **Phase 2 — IQAC**: 1 type (activity). Creatable when master_calendar_locked=True AND iqac_confirmed=False. IQAC confirms → opens Phase 3.
3. **Phase 3 — All others**: sports/cultural (DIRECTOR, DEAN_STUDENT_WELFARE only); academic_activity/other_activity (any non-STUDENT/BASIC_USER role). Creatable when iqac_confirmed=True.

Each confirm action is irreversible and triggers a phase-transition email notification to the next phase's roles.

**Disposition**: M4 (shipped). Entry types are a fixed code-defined set (`ENTRY_TYPE_ROLE_MAP`); adding or changing types requires a code change. See `docs/milestones/M4.md` Session 5 for implementation detail and `docs/modules/configuration.md` → "Three-Phase Calendar Collaboration Chain" for the canonical reference.

---

## E-003 — VisitingFaculty / adjunct / guest / contract / honorary faculty entity

**Status**: Acknowledged. M5b in scope.

**Source**: Original informal requirements
(`docs/durgam_informal_requirements.docx`), Configuration Module section:

> "Dept HoD/AHoD/HoD office should be able to manage the visiting
> faculty/adjunct faculty/guest faculty/contract faculty/honorary faculty
> of their department. Name, designation, organization, expertise,
> available from when to when, approved by admin or not. During course
> allocation in department module, the faculty whose availability is valid
> shall be pulled in."

**Gap in v3 RFP**: §9.3 lists course allocation pulling from a faculty pool
including "visiting/adjunct/guest with valid availability dates" (§9.10
Department module), but neither §8 nor §9.3 defines a configuration entity to
hold these people. They are NOT system Faculty (no User account, no M10
Faculty record) — they are inline-stored external personnel. The v3 coverage
matrix omitted the entity entirely.

**Disposition for M5b**: Add a `VisitingFaculty` entity in the configuration
module.
- Managed by: HoD, AHoD, HoD Office (scoped to their department).
- Fields: department_id (FK), name, designation, organization, expertise,
  available_from (date), available_to (date), is_admin_approved (bool), plus
  TimestampedSoftDelete mixin.
- AY-relevance: availability is date-windowed, not AY-locked (a visiting
  faculty's window may straddle AYs); no AY-immutability rule applies.
- Does NOT depend on M10 Faculty — details are stored inline. This makes it
  M5-ready, unlike the mentor/class-teacher assignments.
- Feeds M13 course allocation (the "valid availability" filter) — M13
  consumes; M5b stores.

**M5b planning prompt must address**: whether `is_admin_approved` uses a
simple boolean set by SYSTEM_ADMIN, or routes through the approval engine
(recommend: simple boolean at M5b; approval-routed admin sign-off is a
possible M7+ enhancement, not required by the source).

---

## E-004 — RoleEmail model diverges from §8.5 canonical schema; NULL-scope uniqueness gap

**Status**: Resolved-at-M5a.

**Source**: Code review at M5 planning, against RFP §8.5 and the M0 inherited
note in `docs/milestones/M5.md`.

**Gap**: The current `RoleEmail` model (`durgam/models/config_anchors.py`)
diverges from the §8.5 canonical definition in two ways:
1. It uses an `int` primary key and plain `SQLModel` base, where §8.5
   specifies `TimestampedSoftDelete` (UUID PK + audit + soft-delete columns).
   Every other config entity uses the mixin. RoleEmail was created as a
   bootstrap artifact at M4 to support calendar phase-transition emails.
2. Its unique constraint `(role_code, scope_type, scope_id)` does NOT prevent
   duplicate NULL-scope rows: in PostgreSQL, NULL != NULL, so two rows with
   the same role_code and NULL scope_type/scope_id both satisfy the
   constraint. The M0 inherited note flagged this: "resolve RoleEmail
   NULL-scope constraint before role-email assignment goes live."

**Disposition for M5a**: Before building the RoleEmail management UI:
1. Migrate RoleEmail to TimestampedSoftDelete (UUID PK, audit columns,
   soft-delete) to match §8.5. Alembic migration must preserve the M4
   bootstrap placeholder rows (re-key from int to UUID; the calendar email
   lookups read by (role_code, scope) not by id, so the re-key is safe —
   verify in migration test).
2. Fix the NULL-scope gap with a partial unique index:
   `CREATE UNIQUE INDEX uq_role_emails_global ON role_emails (role_code)
    WHERE scope_type IS NULL AND is_deleted = false;`
   plus the existing scoped constraint for non-NULL scopes (also made partial
   on is_deleted = false to match the soft-delete pattern used elsewhere).

**M5a planning prompt must address**: migration ordering (the RoleEmail re-key
must run and be verified before the management UI is wired), and confirm the
M4 calendar phase-transition email lookups still resolve after the re-key (an
integration test asserting this).

---

## E-005 — LetterheadAsset and TemplateAsset are both DOCX; unification deferred to M5b

**Status**: Acknowledged. M5b in scope.

**Source**: Stakeholder confirmation during M5a gate verification. The
institution's letterheads are DOCX templates (not images or PDFs as originally
assumed from §9.3's phrasing "identity assets — letterheads, stamps, seals").

**Gap in v3 RFP**: §9.3 describes letterheads as "identity assets" alongside
stamps and seals, implying image files (PNG/JPG/PDF). The actual stakeholder
workflow is: a DOCX template contains the letterhead formatting (header, footer,
institutional branding), and document generation merges content into this
template. This makes LetterheadAsset and TemplateAsset structurally identical —
both store DOCX files, both are role-scoped, both use the same upload/replace/
deactivate lifecycle.

**Disposition**:
- **M5a (done)**: LetterheadAsset MIME filter changed from PNG/JPG/PDF to DOCX
  only. The existing `merge_letterhead_and_content()` docgen primitive (which
  inserts a letterhead IMAGE into a DOCX header) is no longer usable with DOCX
  letterheads. It remains in the codebase as a working image-merge primitive
  but is not called by any production code path at M5a.
- **M5b (planned)**: Evaluate unifying LetterheadAsset and TemplateAsset into a
  single `DocumentTemplate` model with a `purpose` discriminator (letterhead,
  bos, mom, vac). Update the docgen merge to accept a DOCX base template
  instead of an image. This is the natural refactoring point since M5b adds
  bulk import and additional config entities.
- **TD-012 superseded**: The original TD-012 ("PDF letterheads in docgen merge")
  is no longer relevant — letterheads are DOCX, not PDF. The new concern is
  DOCX-to-DOCX merge, addressed at M5b via E-005.

---

## E-006 — Scope-type extensibility (forward-concern for M5b)

**Source**: M5a gate verification — RoleEmail and LetterheadAsset scope management.

**Gap**: The scope_type system currently handles a fixed set of scope types:
global (NULL), `campus`, `department`, `school`. These are hard-coded in the
UI dropdown (`role_emails.py`, `_SCOPE_TYPE_OPTIONS`) and in the scope-object
resolution logic (`config_role_email.py`, `_load_scope_objects()`).

Future milestones will model new scope-bearing entity types — committees,
centres, cells, statutory bodies — each of which may need a corresponding
scope_type for role-scoped configuration (letterheads, role-emails, approval
chains). An admin creating a role scoped to a committee would need
`scope_type="committee"` and a dropdown of committee entities.

**Forward-concern (not a bug)**:
- M5b role-and-scope and approval configuration work must NOT hard-code
  today's scope types. The scope_type dropdown and resolution logic must be
  extensible to scope types added when new entity kinds are modeled.
- Recommended approach: derive scope-type options from a registry or from
  the DB (e.g., distinct scope_types in `user_roles`, or a config table).
  Scope-object resolution should use a pluggable lookup keyed by scope_type,
  not an if/elif chain.
- At M5a this is acceptable — only three scope types exist and the admin UI
  serves its purpose. The concern is recorded here so M5b planning accounts
  for it before the scope-type count grows.

**Disposition**: No code change at M5a. M5b planning must address this.