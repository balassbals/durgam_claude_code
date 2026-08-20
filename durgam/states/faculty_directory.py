"""FacultyDirectoryState — peer-view faculty directory (M10 Phase 8A).

Browsable by any authenticated user holding faculty:read:* (the directory scope).
Mirrors FacultyAdminListState structurally; no admin gate. Search + multi-select
filters + pagination. Builds photo download URLs from photo_file_id (DOWNLOAD_PREFIX,
P2.3 learning). NO PII fields.
"""

from __future__ import annotations

import math

import reflex as rx

from durgam.api import DOWNLOAD_PREFIX
from durgam.db import open_session
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import FacultyService
from durgam.states.base import BaseState


def _build_svc(session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


def _photo_url(photo_file_id: str) -> str:
    if not photo_file_id:
        return ""
    return DOWNLOAD_PREFIX + "/api/files/" + photo_file_id


class FacultyDirectoryState(BaseState):
    loading: bool = True
    rows: list[dict] = []
    total: int = 0

    search_query: str = ""
    selected_departments: list[str] = []
    selected_campuses: list[str] = []
    selected_designations: list[str] = []

    page: int = 1
    page_size: int = 12

    dept_options: list[str] = []
    campus_options: list[str] = []
    # desig_options (not designation_options) — avoid the inherited BaseState
    # collision documented at M10 P6.1 / base.py:56.
    desig_options: list[str] = []

    # ── Derived ────────────────────────────────────────────────────────────────

    @rx.var
    def total_pages(self) -> int:
        if self.total <= 0:
            return 1
        return max(1, math.ceil(self.total / self.page_size))

    # ── Internal query ─────────────────────────────────────────────────────────

    def _run_query(self) -> None:
        self.rows = []
        with open_session() as session:
            svc = _build_svc(session)
            rows, total = svc.list_faculty_for_directory(
                search=self.search_query or None,
                department_codes=self.selected_departments or None,
                campus_codes=self.selected_campuses or None,
                designations=self.selected_designations or None,
                page=self.page,
                page_size=self.page_size,
            )
            for r in rows:
                r["photo_url"] = _photo_url(r.get("photo_file_id", ""))
                r["initials"] = "".join(
                    part[0] for part in r["name"].split() if part
                )[:2].upper()
            self.rows = rows
            self.total = total

    # ── On-load ────────────────────────────────────────────────────────────────

    async def load_records(self):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        self.loading = True
        self.rows = []
        self.total = 0
        with open_session() as session:
            svc = _build_svc(session)
            depts, campuses, desigs = svc.faculty_filter_options()
            self.dept_options = depts
            self.campus_options = campuses
            self.desig_options = desigs
        self._run_query()
        self.loading = False
        self._load_nav_entries()

    # ── Search ─────────────────────────────────────────────────────────────────

    def set_search_query(self, q: str):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        self.search_query = q
        self.page = 1
        self._run_query()

    # ── Filters ────────────────────────────────────────────────────────────────

    def set_department_filter(self, codes: list[str]):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        self.selected_departments = codes
        self.page = 1
        self._run_query()

    def set_campus_filter(self, codes: list[str]):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        self.selected_campuses = codes
        self.page = 1
        self._run_query()

    def set_designation_filter(self, names: list[str]):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        self.selected_designations = names
        self.page = 1
        self._run_query()

    def toggle_department(self, code: str):
        codes = list(self.selected_departments)
        if code in codes:
            codes.remove(code)
        else:
            codes.append(code)
        return self.set_department_filter(codes)

    def toggle_campus(self, code: str):
        codes = list(self.selected_campuses)
        if code in codes:
            codes.remove(code)
        else:
            codes.append(code)
        return self.set_campus_filter(codes)

    def toggle_designation(self, name: str):
        names = list(self.selected_designations)
        if name in names:
            names.remove(name)
        else:
            names.append(name)
        return self.set_designation_filter(names)

    def clear_filters(self):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        self.search_query = ""
        self.selected_departments = []
        self.selected_campuses = []
        self.selected_designations = []
        self.page = 1
        self._run_query()

    # ── Pagination ─────────────────────────────────────────────────────────────

    def next_page(self):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        if self.page < self.total_pages:
            self.page += 1
            self._run_query()

    def prev_page(self):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard
        if self.page > 1:
            self.page -= 1
            self._run_query()

    # ── Navigation ───────────────────────────────────────────────────────────

    def navigate_to_detail_by_id(self, faculty_id: str):
        return rx.redirect("/faculty/" + faculty_id)
