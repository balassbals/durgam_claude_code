"""Late Attendance admin state — HR entry of manual late-attendance markers (M8 Phase 8)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


class LateAttendanceAdminState(BaseState):
    markers: list[dict[str, Any]] = []
    loading: bool = True
    flash: str = ""
    flash_type: str = "info"

    # Add-marker form
    form_employee_username: str = ""
    form_employee_user_id: str = ""
    form_employee_display: str = ""
    form_occurred_on: str = ""
    form_notes: str = ""

    # Filter vars
    filter_month: str = ""

    # ── Setters ──────────────────────────────────────────────────────────

    def set_form_employee_username(self, v: str) -> None:
        self.form_employee_username = v

    def set_form_occurred_on(self, v: str) -> None:
        self.form_occurred_on = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def set_filter_month(self, v: str) -> None:
        self.filter_month = v

    # ── Resolve employee from username ────────────────────────────────────

    async def resolve_employee(self) -> None:
        """Look up the employee by username and populate form_employee_user_id."""
        username = self.form_employee_username.strip()
        if not username:
            self.form_employee_user_id = ""
            self.form_employee_display = ""
            return

        from durgam.repositories.user import UserRepository

        user_id_str: str = ""
        user_display: str = ""

        with open_session() as session:
            repo = UserRepository(session)
            user = repo.get_by_username(username)
            if user is not None:
                # Read all needed attrs inside the session block before it closes.
                user_id_str = str(user.id)
                user_display = (
                    f"{user.full_name} ({user.username})" if user.full_name else user.username
                )

        if not user_id_str:
            self.form_employee_user_id = ""
            self.form_employee_display = ""
            self.flash = f"No employee found with username '{username}'."
            self.flash_type = "error"
            return

        self.form_employee_user_id = user_id_str
        self.form_employee_display = user_display
        self.flash = ""
        self.flash_type = "info"

    # ── Load ─────────────────────────────────────────────────────────────

    async def load_markers(self) -> None:
        guard = self._config_guard("late_attendance", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.markers = []
        self.flash = ""
        self.flash_type = "info"

        from durgam.repositories.leave import LateAttendanceMarkerRepository
        from durgam.repositories.user import UserRepository

        with open_session() as session:
            marker_repo = LateAttendanceMarkerRepository(session)
            user_repo = UserRepository(session)

            raw = marker_repo.list_recent(
                limit=200,
                filter_month=self.filter_month or None,
            )

            user_cache: dict[UUID, str] = {}

            for m in raw:
                if m.employee_user_id not in user_cache:
                    u = user_repo.get_by_id(m.employee_user_id)
                    user_cache[m.employee_user_id] = (
                        f"{u.full_name} ({u.username})" if u and u.full_name else (u.username if u else str(m.employee_user_id))
                    )
                self.markers.append({
                    "id": str(m.id),
                    "employee": user_cache[m.employee_user_id],
                    "occurred_on": str(m.occurred_on),
                    "notes": m.notes or "—",
                    "recorded_at": m.created_at.strftime("%Y-%m-%d") if m.created_at else "—",
                })

        self._load_nav_entries()
        self.loading = False

    # ── Add marker ────────────────────────────────────────────────────────

    async def add_marker(self, form_data: dict) -> None:
        employee_user_id_str = self.form_employee_user_id.strip()
        occurred_on_str = (form_data.get("form_occurred_on") or self.form_occurred_on).strip()
        notes = (form_data.get("form_notes") or self.form_notes).strip() or None

        if not employee_user_id_str:
            self.flash = "Resolve an employee first (enter username and press Enter)."
            self.flash_type = "error"
            return
        if not occurred_on_str:
            self.flash = "Date is required."
            self.flash_type = "error"
            return

        from datetime import date

        try:
            occurred_on = date.fromisoformat(occurred_on_str)
        except ValueError:
            self.flash = "Invalid date format — use YYYY-MM-DD."
            self.flash_type = "error"
            return

        actor_id = UUID(self.current_user_id)

        from durgam.repositories.leave import LateAttendanceMarkerRepository
        from sqlalchemy.exc import IntegrityError

        try:
            with open_session() as session:
                repo = LateAttendanceMarkerRepository(session)
                repo.add(
                    employee_user_id=UUID(employee_user_id_str),
                    occurred_on=occurred_on,
                    recorded_by=actor_id,
                    notes=notes,
                )
                session.commit()
        except IntegrityError:
            self.flash = f"A late-attendance marker for this employee on {occurred_on_str} already exists."
            self.flash_type = "error"
            return
        except Exception:
            log.error("late_attendance_add_failed", exc_info=True)
            self.flash = "An unexpected error occurred. Please try again."
            self.flash_type = "error"
            return

        # Reset form fields
        self.form_employee_username = ""
        self.form_employee_user_id = ""
        self.form_employee_display = ""
        self.form_occurred_on = ""
        self.form_notes = ""

        await self.load_markers()
        self.flash = "Late-attendance marker recorded."
        self.flash_type = "success"

    async def apply_filter(self) -> None:
        await self.load_markers()

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"
