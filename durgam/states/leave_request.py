"""Leave requestor state: LeavePageState (balance cards + request list + apply modal).

M8 Phase 7 — unified state so the apply modal can reload the list in one handler.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


LEAVE_TYPE_OPTIONS = [
    ("CL",  "Casual Leave"),
    ("SCL", "Special Casual Leave"),
    ("EL",  "Earned Leave"),
    ("HPL", "Half Pay Leave"),
    ("CML", "Commuted Leave"),
    ("EOL", "Extraordinary Leave"),
    ("ML",  "Maternity Leave"),
    ("SL",  "Study Leave"),
]


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "—"
    return d.isoformat()


def _build_svc(session):
    from durgam.repositories.approval_process import ApprovalProcessRepository
    from durgam.repositories.approval_request import ApprovalRequestRepository
    from durgam.repositories.approval_step import ApprovalStepRepository
    from durgam.repositories.leave import (
        LeaveBalanceRepository,
        LeaveRepository,
        LeaveSanctionRuleRepository,
    )
    from durgam.repositories.notification import NotificationRepository
    from durgam.services.approval_request import ApprovalRequestService
    from durgam.services.leave_request import LeaveRequestService

    approval_svc = ApprovalRequestService(
        session=session,
        proc_repo=ApprovalProcessRepository(session),
        request_repo=ApprovalRequestRepository(session),
        step_repo=ApprovalStepRepository(session),
        notification_repo=NotificationRepository(session),
    )
    return LeaveRequestService(
        session=session,
        leave_repo=LeaveRepository(session),
        balance_repo=LeaveBalanceRepository(session),
        rule_repo=LeaveSanctionRuleRepository(session),
        approval_service=approval_svc,
    )


class LeavePageState(BaseState):
    # ── List / balance state ─────────────────────────────────────────
    balances: list[dict[str, Any]] = []
    in_flight: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    loading: bool = True
    flash: str = ""
    flash_type: str = "info"
    current_ay_id: str = ""

    # ── Apply modal state ────────────────────────────────────────────
    show_modal: bool = False
    leave_type: str = "CL"
    starts_on: str = ""
    ends_on: str = ""
    reason: str = ""
    half_day: bool = False
    half_day_which: str = "first"
    address_during_leave: str = ""
    headquarters_left: bool = False
    alternate_arrangement: str = ""
    intended_outside_india: bool = False
    in_charge_designation: str = ""
    preview_days: float = 0.0
    preview_channel_label: str = ""
    submitting: bool = False
    form_error: str = ""

    # ── Computed vars ────────────────────────────────────────────────

    @rx.var
    def is_director(self) -> bool:
        return any(r.get("role_code") == "DIRECTOR" for r in self._current_user_roles)

    # ── Flash helpers ────────────────────────────────────────────────

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── List page handlers ───────────────────────────────────────────

    async def load_my_leave(self) -> rx.Component | None:
        guard = _resolve_or_redirect(self)
        if guard is not None:
            return guard
        self.loading = True
        self.balances = []
        self.in_flight = []
        self.history = []
        self.flash = ""
        self.flash_type = "info"
        user_id = UUID(self.current_user_id)

        with open_session() as session:
            from sqlmodel import select

            from durgam.models.config_anchors import AcademicYear
            from durgam.models.leave import LeaveBalance, LeaveRequest

            today = date.today()
            ay = session.exec(
                select(AcademicYear).where(
                    AcademicYear.starts_on <= today,
                    AcademicYear.ends_on >= today,
                    AcademicYear.is_deleted == False,  # noqa: E712
                )
            ).first()
            if ay is None:
                self.flash = "No active academic year configured."
                self.flash_type = "warning"
                self.loading = False
                self._load_nav_entries()
                return None

            self.current_ay_id = str(ay.id)

            balances = session.exec(
                select(LeaveBalance).where(
                    LeaveBalance.employee_user_id == user_id,
                    LeaveBalance.academic_year_id == ay.id,
                    LeaveBalance.is_deleted == False,  # noqa: E712
                )
            ).all()
            self.balances = [
                {
                    "leave_type": b.leave_type,
                    "opening": b.opening_balance,
                    "credited": b.credited,
                    "availed": b.availed,
                    "forfeited": b.forfeited,
                    "encashed": b.encashed,
                    "closing": b.closing_balance,
                }
                for b in balances
            ]

            requests = list(
                session.exec(
                    select(LeaveRequest)
                    .where(
                        LeaveRequest.requestor_user_id == user_id,
                        LeaveRequest.academic_year_id == ay.id,
                        LeaveRequest.is_deleted == False,  # noqa: E712
                    )
                    .order_by(LeaveRequest.starts_on.desc())  # type: ignore[union-attr]
                ).all()
            )

            terminal = {"approved", "rejected", "withdrawn", "cancelled"}
            for r in requests:
                row = {
                    "id": str(r.id),
                    "leave_type": r.leave_type,
                    "starts_on": _fmt_date(r.starts_on),
                    "ends_on": _fmt_date(r.ends_on),
                    "chargeable_days": r.chargeable_days,
                    "state": r.state,
                    "reason": r.reason or "",
                }
                if r.state in terminal:
                    self.history.append(row)
                else:
                    self.in_flight.append(row)

        self.loading = False
        self._load_nav_entries()
        return None

    async def withdraw_leave(self, leave_request_id: str) -> None:
        guard = _resolve_or_redirect(self)
        if guard is not None:
            return guard
        user_id = UUID(self.current_user_id)
        with open_session() as session:
            from durgam.services.leave_request import LeaveRequestError

            try:
                svc = _build_svc(session)
                svc.withdraw(UUID(leave_request_id), user_id)
                session.commit()
            except LeaveRequestError as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        await self.load_my_leave()
        self.flash = "Leave request withdrawn."
        self.flash_type = "success"

    # ── Apply modal setters (M7 rule — explicit setters required) ────

    def set_leave_type(self, value: str) -> None:
        self.leave_type = value
        self.preview_days = 0.0
        self.preview_channel_label = ""

    def set_starts_on(self, value: str) -> None:
        self.starts_on = value

    def set_ends_on(self, value: str) -> None:
        self.ends_on = value

    def set_reason(self, value: str) -> None:
        self.reason = value

    def set_half_day(self, value: bool) -> None:
        self.half_day = value

    def set_half_day_which(self, value: str) -> None:
        self.half_day_which = value

    def set_address_during_leave(self, value: str) -> None:
        self.address_during_leave = value

    def set_headquarters_left(self, value: bool) -> None:
        self.headquarters_left = value

    def set_alternate_arrangement(self, value: str) -> None:
        self.alternate_arrangement = value

    def set_intended_outside_india(self, value: bool) -> None:
        self.intended_outside_india = value

    def set_in_charge_designation(self, value: str) -> None:
        self.in_charge_designation = value

    # ── Modal lifecycle ──────────────────────────────────────────────

    def open_modal(self) -> None:
        self._reset_form()
        self.show_modal = True

    def close_modal(self) -> None:
        self.show_modal = False
        self._reset_form()

    def _reset_form(self) -> None:
        self.leave_type = "CL"
        self.starts_on = ""
        self.ends_on = ""
        self.reason = ""
        self.half_day = False
        self.half_day_which = "first"
        self.address_during_leave = ""
        self.headquarters_left = False
        self.alternate_arrangement = ""
        self.intended_outside_india = False
        self.in_charge_designation = ""
        self.preview_days = 0.0
        self.preview_channel_label = ""
        self.submitting = False
        self.form_error = ""

    # ── Preview ──────────────────────────────────────────────────────

    async def fetch_preview(self) -> None:
        guard = _resolve_or_redirect(self)
        if guard is not None:
            return guard
        if not self.starts_on or not self.ends_on or not self.current_ay_id:
            return
        user_id = UUID(self.current_user_id)
        ay_id = UUID(self.current_ay_id)
        try:
            s = date.fromisoformat(self.starts_on)
            e = date.fromisoformat(self.ends_on)
        except ValueError:
            return

        with open_session() as session:
            from durgam.services.leave_rules import LeaveChannelError, LeaveRuleError
            from durgam.services.leave_request import LeaveRequestError

            try:
                svc = _build_svc(session)
                self.preview_days = svc.preview_chargeable_days(
                    leave_type=self.leave_type,
                    starts_on=s,
                    ends_on=e,
                    academic_year_id=ay_id,
                    half_day=self.half_day,
                    half_day_which=self.half_day_which if self.half_day else None,
                )
                channel = svc.preview_channel(user_id, self.leave_type)
                if channel:
                    stages = []
                    for ch in channel:
                        if ch["recommend_only"]:
                            stages.append(f"Recommend ({ch['role_code']})")
                        else:
                            stages.append(ch["role_code"])
                    self.preview_channel_label = " → ".join(stages)
                else:
                    self.preview_channel_label = "—"
            except (LeaveChannelError, LeaveRequestError, LeaveRuleError, ValueError) as e:
                self.preview_channel_label = f"No rule: {e}"
                self.preview_days = 0.0

    # ── Submit ───────────────────────────────────────────────────────

    async def submit_leave(self, form_data: dict) -> None:
        guard = _resolve_or_redirect(self)
        if guard is not None:
            return guard

        self.form_error = ""
        self.submitting = True

        if not self.current_ay_id:
            self.form_error = "No active academic year; cannot submit leave."
            self.submitting = False
            return

        starts_on_str = form_data.get("starts_on", "").strip()
        ends_on_str = form_data.get("ends_on", "").strip()
        reason = form_data.get("reason", "").strip()

        if not starts_on_str or not ends_on_str:
            self.form_error = "Start date and end date are required."
            self.submitting = False
            return
        if not reason:
            self.form_error = "Reason is required."
            self.submitting = False
            return

        try:
            starts_on = date.fromisoformat(starts_on_str)
            ends_on = date.fromisoformat(ends_on_str)
        except ValueError:
            self.form_error = "Invalid date format."
            self.submitting = False
            return

        user_id = UUID(self.current_user_id)
        ay_id = UUID(self.current_ay_id)

        with open_session() as session:
            from durgam.services.leave_request import LeaveRequestError
            from durgam.services.leave_rules import LeaveChannelError, LeaveRuleError

            try:
                svc = _build_svc(session)
                svc.submit(
                    requestor_user_id=user_id,
                    leave_type=self.leave_type,
                    starts_on=starts_on,
                    ends_on=ends_on,
                    academic_year_id=ay_id,
                    reason=reason,
                    half_day=self.half_day,
                    half_day_which=self.half_day_which if self.half_day else None,
                    address_during_leave=self.address_during_leave or None,
                    headquarters_left=self.headquarters_left,
                    alternate_arrangement=self.alternate_arrangement or None,
                    intended_outside_india=self.intended_outside_india,
                    in_charge_designation=self.in_charge_designation or None,
                )
                session.commit()
            except (LeaveRequestError, LeaveRuleError, LeaveChannelError) as e:
                self.form_error = str(e)
                self.submitting = False
                return
            except Exception:
                log.error("submit_leave_failed", exc_info=True)
                self.form_error = "An unexpected error occurred. Please try again."
                self.submitting = False
                return

        self.close_modal()
        self.submitting = False
        await self.load_my_leave()
        self.flash = "Leave request submitted successfully."
        self.flash_type = "success"
