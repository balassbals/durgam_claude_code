"""Read-only Faculty picker endpoint — /api/faculty/picker (M10 Phase 11C).

Extracts the ``dsession`` cookie, resolves the UserSession, and authorises the
caller iff they can WRITE at least one of the five M5b assignment-style
resources that use the picker (the same permission that gates the admin forms —
no new permission triple). Returns up to 50 active faculties as picker rows
containing ONLY display fields (id, employee_id, title, first/last name, and a
formatted ``display`` string). No PII is ever serialised.

Query params (all optional):
  search        — case-insensitive partial match on employee_id / name / title
  department_id — UUID filter
  campus_id     — UUID filter
  designation_id— UUID filter
  employee_type — exact match on the owning User.employee_type

Returns 403 for missing/invalid session or insufficient permission.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.repositories.auth import UserSessionRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.services.faculty_picker import FacultyPickerService

log = structlog.get_logger(__name__)

_FORBIDDEN = Response("Forbidden", status_code=403)

# The picker is used by exactly these four admin forms; a caller may use it iff
# they can write at least one of them (mirrors each form's _config_guard write
# check). No dedicated picker permission is introduced.
# (class_coordinator_assignment removed in M10 Phase 11D — Q-P11D.1.)
_PICKER_RESOURCES = (
    "faculty_mentor_assignment",
    "class_teacher_assignment",
    "non_owned_course",
    "ug_timetable",
)


def _opt_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        return None


def _picker_authorized(user_id: UUID, session) -> bool:
    return any(
        can(user_id, "write", resource, None, None, session)
        for resource in _PICKER_RESOURCES
    )


async def faculty_picker(request: Request) -> Response:
    """Return up to 50 active faculties matching the query (display fields only)."""
    raw_token = request.cookies.get("dsession", "")
    if not raw_token:
        return _FORBIDDEN

    qp = request.query_params
    search = qp.get("search") or qp.get("q")
    department_id = _opt_uuid(qp.get("department_id"))
    campus_id = _opt_uuid(qp.get("campus_id"))
    designation_id = _opt_uuid(qp.get("designation_id"))
    employee_type = qp.get("employee_type")

    with open_session() as session:
        sess_record = UserSessionRepository(session).get_active(raw_token)
        if sess_record is None:
            return _FORBIDDEN

        user_id = sess_record.user_id
        if not _picker_authorized(user_id, session):
            return _FORBIDDEN

        results = FacultyPickerService(FacultyRepository(session)).search(
            search=search,
            department_id=department_id,
            campus_id=campus_id,
            designation_id=designation_id,
            employee_type=employee_type,
            limit=50,
        )

    return JSONResponse({"results": results})
