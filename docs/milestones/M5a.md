# M5a — File Infrastructure & Identity Assets

**RFP reference:** §9.3, §12 M5
**Branch:** `m5a-config-assets`
**Parent milestone:** M5 — Configuration — Identity Attachments

---

## Scope

1. File upload/storage foundation (UploadService, StorageBackend, FileAsset)
2. RoleEmail remediation (E-004: int PK → UUID + TimestampedSoftDelete + partial unique indexes) + management UI
3. Authenticated file download endpoint (`/api/files/{file_id}`) with purpose-based permission escalation
4. LetterheadAsset management UI (upload/replace/deactivate/download)
5. TemplateAsset management UI (upload/replace/deactivate; types: bos/mom/vac)
6. Docgen merge primitive (letterhead + content blocks → DOCX)
7. Reusable file upload component (`file_upload_zone`)

## Sessions

| Session | Commit | What shipped |
|---|---|---|
| 1 | `ab10769` | StorageBackend (local + MinIO), UploadService, FileAsset purpose field; 34 new tests |
| 2 | `37c2f6a` | RoleEmail E-004 re-key migration + management UI + calendar email safety; 14 new tests |
| 3 | `7b50fe5` | LetterheadAsset model + UI + download endpoint + file_upload_zone; 17 new tests |
| 4 | (pending) | TemplateAsset model + UI + docgen merge + full E2E + documentation |

## Design Decisions (from planning)

| ID | Decision |
|---|---|
| DQ-M5a-1 | FileAsset stays in `crosscutting.py` (cross-cutting concern per §8.4) |
| DQ-M5a-2 | Flat storage keys (UUID directly in base dir; no sharding) |
| DQ-M5a-3 | RoleEmail flat list UI (not grouped by role) |
| DQ-M5a-4 | UploadService orchestrates scan (ClamAV mock boundary) |
| DQ-M5a-5 | Partial unique indexes at DB level for LetterheadAsset |
| DQ-M5a-6 | TemplateAsset is a separate model from LetterheadAsset |
| DQ-M5a-7 | Authenticated stream-through download endpoint |

## Migrations (3)

1. `a1b2c3d4e5f6` — RoleEmail re-key (int→UUID + TimestampedSoftDelete + partial unique indexes)
2. `b2c3d4e5f6a7` — LetterheadAsset partial unique indexes
3. `c3d4e5f6a7b8` — TemplateAsset table + partial unique index

## Permission Triples (10 new)

| Resource | Actions | Granted to |
|---|---|---|
| `file_asset` | `read` | All roles (`_PUBLIC_READ`) |
| `role_email` | `read`, `write`, `delete` | Registrar family + SYSTEM_ADMIN |
| `letterhead_asset` | `read`, `write`, `delete` | Registrar family + SYSTEM_ADMIN |
| `template_asset` | `read`, `write`, `delete` | IQAC_COORDINATOR + SYSTEM_ADMIN |

## Errata Resolved

- **E-004** (RoleEmail NULL-scope constraint): Resolved at M5a Session 2. Re-keyed from int to UUID PK, added `TimestampedSoftDelete`, split unique constraint into two partial unique indexes (global + scoped) WHERE `is_deleted = false`.

## Tech Debt Recorded

- **TD-012**: PDF letterheads accepted for storage but `merge_letterhead_and_content()` raises `DocgenError` if called with `mime_type="application/pdf"`. Add `pdf2image` + `poppler-utils` when PDF merge is needed.
- **TD-013**: Download endpoint registered via `app._api.add_route()` (private Reflex attribute). Re-verify on any Reflex version bump.

## Gate Checklist

- [x] `uv run pytest --ignore=tests/e2e -v` — 544 passed
- [x] `DURGAM_E2E=1 uv run pytest tests/e2e/ -q --no-cov` — 87 passed, 3× deterministic
- [x] Migration forward+reverse clean
- [x] Manual: fresh seed → login as each role → verify access/denial
- [x] Upload/download flows for letterhead and template
- [x] Incognito check on all 3 new routes
- [x] CLAUDE.md current-milestone updated
