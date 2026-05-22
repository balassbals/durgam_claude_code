"""StudentCategoryConfigState — per-AY singleton counts form."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.student_category_count import StudentCategoryCountRepository
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.services.student_category_count import (
    StudentCategoryCountError,
    StudentCategoryCountService,
)
from durgam.states.base import BaseState


def _svc(session) -> StudentCategoryCountService:
    return StudentCategoryCountService(
        scc_repo=StudentCategoryCountRepository(session),
    )


class StudentCategoryConfigState(BaseState):
    # AY selector
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    # Form fields (strings for rx.input compatibility)
    scc_id: str = ""
    sc_count: str = "0"
    st_count: str = "0"
    obc_count: str = "0"
    ews_count: str = "0"
    general_count: str = "0"
    notes: str = ""

    loading: bool = True

    async def load_student_categories(self) -> None:
        guard = self._config_guard("student_category_count", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.ay_options = []

        with open_session() as session:
            ay_repo = AcademicYearRepository(session)
            for ay in ay_repo.list_active():
                self.ay_options.append({
                    "value": str(ay.id),
                    "label": ay.code,
                    "is_locked": "1" if ay.is_locked else "0",
                })
            if self.ay_options and not self.selected_ay_id:
                self.selected_ay_id = self.ay_options[0]["value"]

            self._load_counts(session)

        self._load_nav_entries()
        self.loading = False

    def _load_counts(self, session) -> None:
        if not self.selected_ay_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        svc = _svc(session)
        scc = svc.get_or_create_by_ay(UUID(self.selected_ay_id), UUID(self.current_user_id))
        session.commit()
        self.scc_id = str(scc.id)
        self.sc_count = str(scc.sc_count)
        self.st_count = str(scc.st_count)
        self.obc_count = str(scc.obc_count)
        self.ews_count = str(scc.ews_count)
        self.general_count = str(scc.general_count)
        self.notes = scc.notes or ""

    async def on_ay_change(self, value: str) -> None:
        self.selected_ay_id = value
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_counts(session)
        matched = [o for o in self.ay_options if o["value"] == value]
        self.ay_is_locked = bool(matched and matched[0]["is_locked"] == "1")

    def set_sc_count(self, v: str) -> None:
        self.sc_count = v

    def set_st_count(self, v: str) -> None:
        self.st_count = v

    def set_obc_count(self, v: str) -> None:
        self.obc_count = v

    def set_ews_count(self, v: str) -> None:
        self.ews_count = v

    def set_general_count(self, v: str) -> None:
        self.general_count = v

    def set_notes(self, v: str) -> None:
        self.notes = v

    @require_role(action="write", resource="student_category_count")
    @audit_action(action="write", resource="student_category_count")
    async def save_student_categories(self, form_data: dict) -> None:
        fields: dict = {}
        errors: list[str] = []
        for key in ("sc_count", "st_count", "obc_count", "ews_count", "general_count"):
            raw = form_data.get(key, "0").strip()
            try:
                val = int(raw)
                if val < 0:
                    raise ValueError
                fields[key] = val
            except ValueError:
                errors.append(f"{key.replace('_', ' ').title()} must be a non-negative integer.")

        notes_raw = form_data.get("notes", "").strip()
        fields["notes"] = notes_raw or None

        if errors:
            self.flash = " | ".join(errors)
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                svc.update(UUID(self.scc_id), fields, UUID(self.current_user_id))
                session.commit()
        except (StudentCategoryCountError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            return

        await self.load_student_categories()
        self.flash = "Student category counts saved."
        self.flash_type = "success"
