"""Authenticated file download endpoint — /api/files/{file_id}.

Extracts the ``dsession`` cookie, resolves the UserSession, checks
``file_asset:read`` permission, and streams file bytes from StorageBackend
with correct Content-Type and Content-Disposition headers.

Restricted file types (letterhead, template) escalate to a resource-specific
permission check via ``_PURPOSE_PERMISSION_MAP``. See the security note
in that block for the inverted-default rationale.

Returns 403 for invalid/missing session or insufficient permissions,
404 for missing or soft-deleted files.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from starlette.requests import Request
from starlette.responses import Response

from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.models.crosscutting import FileAsset
from durgam.repositories.auth import UserSessionRepository
from durgam.storage import get_storage_backend

log = structlog.get_logger(__name__)

_FORBIDDEN = Response("Forbidden", status_code=403)
_NOT_FOUND = Response("Not found", status_code=404)

# SECURITY: purpose-based permission escalation.
# The default is PERMISSIVE — any authenticated user with file_asset:read can
# download files whose purpose is NOT listed here. Restricted file types MUST
# be added to this map explicitly, or they inherit the permissive default and
# leak. Every future restricted file purpose (certificate, confidential
# attachment, exam material, etc.) must add its entry here.
# This inverted default is deliberate at M5a (most file types — exports,
# generic attachments — should be downloadable by any authenticated user).
# Flag for review at M20 hardening to confirm no restricted purposes were
# missed.
_PURPOSE_PERMISSION_MAP: dict[str, str] = {
    "letterhead": "letterhead_asset",
    "template": "template_asset",
    "counsellor_roster": "mental_health_counsellor",
}


async def download_file(request: Request) -> Response:
    """Stream-through download for a single FileAsset."""
    file_id_str = request.path_params.get("file_id", "")
    try:
        file_id = UUID(file_id_str)
    except (ValueError, AttributeError):
        return _NOT_FOUND

    raw_token = request.cookies.get("dsession", "")
    if not raw_token:
        return _FORBIDDEN

    with open_session() as session:
        sess_repo = UserSessionRepository(session)
        sess_record = sess_repo.get_active(raw_token)
        if sess_record is None:
            return _FORBIDDEN

        user_id = sess_record.user_id

        if not can(user_id, "read", "file_asset", None, None, session):
            return _FORBIDDEN

        file_asset = session.get(FileAsset, file_id)
        if file_asset is None or file_asset.is_deleted:
            return _NOT_FOUND

        restricted_resource = _PURPOSE_PERMISSION_MAP.get(file_asset.purpose or "")
        if restricted_resource is not None:
            if not can(user_id, "read", restricted_resource, None, None, session):
                return _FORBIDDEN

        storage_key = file_asset.storage_key
        content_type = file_asset.mime_type
        original_name = file_asset.original_name

    backend = get_storage_backend()
    try:
        data = backend.get(storage_key)
    except FileNotFoundError:
        log.error("download: storage key missing", storage_key=storage_key)
        return _NOT_FOUND

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{original_name}"'},
    )
