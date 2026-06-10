"""State for leave balance admin edit page — /admin/leave/balance-edit (M8.1 E-022)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import reflex as rx

from durgam.db import open_session
from durgam.states.base import BaseState


class LeaveBalanceAdminState(BaseState):
    # ── Filter state ─────────────────────────────────────────────────
    username_filter: str = ""
    leave_type_filter: str = "all"
    ay_id_filter: str = "all"

    # ── Results ──────────────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    loading: bool = True

    # ── AY dropdown options ──────────────────────────────────────────
    ay_options: list[dict[str, str]] = []

    # ── Edit modal state ─────────────────────────────────────────────
    show_edit_modal: bool = False
    edit_balance_id: str = ""
    edit_username: str = ""
    edit_leave_type: str = ""
    edit_ay_name: str = ""
    edit_opening: float = 0.0
    edit_credited: float = 0.0
    edit_availed: float = 0.0
    edit_forfeited: float = 0.0
    edit_encashed: float = 0.0

    # ── Flash ────────────────────────────────────────────────────────
    flash: str = ""
    flash_type: str = "info"

    # ── Computed vars ────────────────────────────────────────────────

    @rx.var
    def computed_closing(self) -> float:
        return (
            self.edit_opening
            + self.edit_credited
            - self.edit_availed
            - self.edit_forfeited
            - self.edit_encashed
        )

    @rx.var
    def is_save_valid(self) -> bool:
        return self.computed_closing >= 0

    # ── Filter setters ───────────────────────────────────────────────

    def set_username_filter(self, value: str) -> None:
        self.username_filter = value

    def set_leave_type_filter(self, value: str) -> None:
        self.leave_type_filter = value

    def set_ay_id_filter(self, value: str) -> None:
        self.ay_id_filter = value

    # ── Edit field setters ───────────────────────────────────────────

    def set_edit_opening(self, value: str) -> None:
        try:
            self.edit_opening = float(value)
        except (ValueError, TypeError):
            self.edit_opening = 0.0

    def set_edit_credited(self, value: str) -> None:
        try:
            self.edit_credited = float(value)
        except (ValueError, TypeError):
            self.edit_credited = 0.0

    def set_edit_availed(self, value: str) -> None:
        try:
            self.edit_availed = float(value)
        except (ValueError, TypeError):
            self.edit_availed = 0.0

    def set_edit_forfeited(self, value: str) -> None:
        try:
            self.edit_forfeited = float(value)
        except (ValueError, TypeError):
            self.edit_forfeited = 0.0

    def set_edit_encashed(self, value: str) -> None:
        try:
            self.edit_encashed = float(value)
        except (ValueError, TypeError):
            self.edit_encashed = 0.0

    # ── Flash helper ─────────────────────────────────────────────────

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── Page-load / filter handlers ──────────────────────────────────

    async def load_admin_balances(self) -> rx.Component | None:
        guard = self._config_guard("leave_balance_admin", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.rows = []
        with open_session() as session:
            from sqlmodel import select

            from durgam.models.config_anchors import AcademicYear
            from durgam.models.identity import User
            from durgam.models.leave import LeaveBalance
            from durgam.repositories.academic_year import AcademicYearRepository
            from durgam.repositories.leave import LeaveBalanceRepository

            # Populate AY dropdown on every load (cheap, small table)
            ay_repo = AcademicYearRepository(session)
            all_ays = ay_repo.list_active()
            self.ay_options = [
                {"id": str(ay.id), "name": ay.code}
                for ay in all_ays
            ]

            balance_repo = LeaveBalanceRepository(session)
            ay_id = UUID(self.ay_id_filter) if self.ay_id_filter not in ("all", "") else None
            lt_filter = self.leave_type_filter if self.leave_type_filter != "all" else None
            un_filter = self.username_filter.strip() or None

            results = balance_repo.admin_search_balances(
                username_filter=un_filter,
                leave_type_filter=lt_filter,
                ay_id_filter=ay_id,
            )
            self.rows = [
                {
                    "id": str(bal.id),
                    "username": user.username,
                    "leave_type": bal.leave_type,
                    "ay_name": ay.code,
                    "opening": bal.opening_balance,
                    "credited": bal.credited,
                    "availed": bal.availed,
                    "forfeited": bal.forfeited,
                    "encashed": bal.encashed,
                    "closing": bal.closing_balance,
                }
                for bal, user, ay in results
            ]
        self.loading = False
        self._load_nav_entries()
        return None

    async def apply_filters(self) -> None:
        await self.load_admin_balances()

    async def clear_filters(self) -> None:
        self.username_filter = ""
        self.leave_type_filter = "all"
        self.ay_id_filter = "all"
        await self.load_admin_balances()

    # ── Edit modal lifecycle ─────────────────────────────────────────

    def open_edit_modal(
        self,
        balance_id: str,
        username: str,
        leave_type: str,
        ay_name: str,
        opening: float,
        credited: float,
        availed: float,
        forfeited: float,
        encashed: float,
    ) -> None:
        self.edit_balance_id = balance_id
        self.edit_username = username
        self.edit_leave_type = leave_type
        self.edit_ay_name = ay_name
        self.edit_opening = opening
        self.edit_credited = credited
        self.edit_availed = availed
        self.edit_forfeited = forfeited
        self.edit_encashed = encashed
        self.flash = ""
        self.flash_type = "info"
        self.show_edit_modal = True

    def close_edit_modal(self) -> None:
        self.show_edit_modal = False
        self.edit_balance_id = ""
        self.edit_username = ""
        self.edit_leave_type = ""
        self.edit_ay_name = ""
        self.edit_opening = 0.0
        self.edit_credited = 0.0
        self.edit_availed = 0.0
        self.edit_forfeited = 0.0
        self.edit_encashed = 0.0

    async def submit_edit(self, form_data: dict) -> None:
        """Apply the admin balance edit, commit, flash, refresh."""
        guard = self._config_guard("leave_balance_admin", "write")
        if guard is not None:
            return guard
        balance_id = self.edit_balance_id
        if not balance_id:
            return
        actor_id = UUID(self.current_user_id)
        fields: dict = {}
        for field_name, setter in (
            ("opening_balance", "edit_opening"),
            ("credited",        "edit_credited"),
            ("availed",         "edit_availed"),
            ("forfeited",       "edit_forfeited"),
            ("encashed",        "edit_encashed"),
        ):
            fields[field_name] = getattr(self, setter)

        with open_session() as session:
            from durgam.repositories.leave import LeaveBalanceValidationError
            from durgam.services.leave_balance_import import LeaveBalanceImportService
            from durgam.services.org_exceptions import AcademicYearLockedError

            try:
                svc = LeaveBalanceImportService(session)
                svc.admin_edit_balance(
                    balance_id=UUID(balance_id),
                    fields=fields,
                    actor_id=actor_id,
                )
                session.commit()
            except (LeaveBalanceValidationError, AcademicYearLockedError, ValueError) as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        self.close_edit_modal()
        await self.load_admin_balances()
        self.flash = "Balance updated successfully."
        self.flash_type = "success"
