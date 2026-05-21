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