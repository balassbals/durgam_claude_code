"""FacultyPickerService — read-only faculty lookup for the M10 Phase 11C picker.

Backs both the ``/api/faculty/picker`` JSON endpoint and the in-app reusable
faculty picker component. Returns ONLY picker display fields — never PII
(no aadhaar_enc, pan_enc, password_hash, phone, emergency contacts, etc.).
"""

from __future__ import annotations

from uuid import UUID

from durgam.repositories.faculty import FacultyRepository

# The picker display fields — the ONLY columns a picker row ever exposes.
# Sensitive Faculty/User columns are intentionally excluded.
PICKER_FIELDS = ("id", "employee_id", "title", "first_name", "last_name", "display")


def _display(employee_id: str, title: str, first_name: str, last_name: str) -> str:
    name = " ".join(p for p in (title, first_name, last_name) if p)
    return f"{employee_id} — {name}" if name else employee_id


class FacultyPickerService:
    def __init__(self, repo: FacultyRepository) -> None:
        self._repo = repo

    def search(
        self,
        *,
        search: str | None = None,
        department_id: UUID | None = None,
        campus_id: UUID | None = None,
        designation_id: UUID | None = None,
        employee_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, str]]:
        """Return up to 50 active faculties as picker rows (display fields only)."""
        rows = self._repo.list_for_picker(
            search=search,
            department_id=department_id,
            campus_id=campus_id,
            designation_id=designation_id,
            employee_type=employee_type,
            limit=limit,
        )
        return [
            {
                "id": str(f.id),
                "employee_id": f.employee_id,
                "title": f.title,
                "first_name": f.first_name,
                "last_name": f.last_name,
                "display": _display(f.employee_id, f.title, f.first_name, f.last_name),
            }
            for f in rows
        ]
