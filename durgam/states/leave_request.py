"""Leave requestor state: LeavePageState (balance cards + request list + apply modal).

M8 Phase 7 — unified state so the apply modal can reload the list in one handler.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.auth.decorators import audit_action, require_role
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


def _build_leave_progress(ar: Any, proc_channel: list[str], steps_map: dict) -> str:
    """Compact progress line for an in-flight leave request."""
    if ar is None:
        return ""
    resolved = ar.resolved_channel_json or []
    total = len(resolved) if resolved else len(proc_channel)
    current = ar.current_stage
    if resolved and 0 < current <= len(resolved):
        awaiting = resolved[current - 1].get("role_code", "?")
    elif proc_channel and 0 < current <= len(proc_channel):
        awaiting = proc_channel[current - 1]
    else:
        awaiting = "?"
    steps = steps_map.get(ar.id, [])
    forwarded = [s for s in steps if s.decision == "forwarded"]
    if forwarded:
        last = forwarded[-1]
        rec_role = last.approver_role_code
        comment = (last.comment or "").strip()
        text = f"Stage {current} of {total} — Rec. by {rec_role}"
        if comment:
            text += f": '{comment[:60]}'"
        text += f". Awaiting {awaiting}."
    else:
        text = f"Stage {current} of {total} — Awaiting {awaiting}."
    return text


def _build_leave_history_summary(
    ar: Any, proc_channel: list[str], steps_map: dict, r_state: str
) -> str:
    """One-line terminal summary for a completed leave request."""
    if r_state == "withdrawn":
        return "Withdrawn by requestor."
    if r_state == "cancelled":
        if ar is None:
            return "Cancelled."
        steps = steps_map.get(ar.id, [])
        for s in reversed(steps):
            if s.decision in ("cancelled", "rejected"):
                comment = (s.comment or "").strip()
                text = f"Cancelled by {s.approver_role_code}"
                if comment:
                    text += f": '{comment[:60]}'"
                return text + "."
        return "Cancelled."
    if ar is None:
        return ""
    resolved = ar.resolved_channel_json or []
    total = len(resolved) if resolved else len(proc_channel)
    steps = steps_map.get(ar.id, [])
    for s in reversed(steps):
        if s.decision in ("approved", "rejected"):
            comment = (s.comment or "").strip()
            decided = s.decided_at.strftime("%Y-%m-%d") if s.decided_at else ""
            word = "Approved" if s.decision == "approved" else "Rejected"
            text = f"{word} by {s.approver_role_code}"
            if decided:
                text += f" ({decided})"
            if comment:
                text += f": '{comment[:60]}'"
            text += f". Stage {s.stage} of {total}."
            return text
    decision_word = "Approved" if r_state == "approved" else "Rejected"
    return f"{decision_word}."


def _build_svc(session):
    from durgam.repositories.leave import (
        LeaveBalanceRepository,
        LeaveRepository,
        LeaveSanctionRuleRepository,
    )
    from durgam.services.approval_request import ApprovalRequestService
    from durgam.services.leave_request import LeaveRequestService

    return LeaveRequestService(
        session=session,
        leave_repo=LeaveRepository(session),
        balance_repo=LeaveBalanceRepository(session),
        rule_repo=LeaveSanctionRuleRepository(session),
        approval_service=ApprovalRequestService(session),
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

    # ── Withdraw-approved modal state ────────────────────────────────
    show_withdraw_modal: bool = False
    withdraw_reason: str = ""
    withdraw_request_id: str = ""

    # ── Computed vars ────────────────────────────────────────────────

    @rx.var
    def is_director(self) -> bool:
        return any(r.get("role_code") == "DIRECTOR" for r in self._current_user_roles)

    @rx.var
    def withdraw_reason_valid(self) -> bool:
        return len(self.withdraw_reason.strip()) >= 10

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
            _no_balance_types = {"SCL", "EOL", "SL"}
            self.balances = [
                {
                    "leave_type": b.leave_type,
                    "opening": b.opening_balance,
                    "credited": b.credited,
                    "availed": b.availed,
                    "forfeited": b.forfeited,
                    "encashed": b.encashed,
                    "closing": b.closing_balance,
                    "is_no_balance_type": b.leave_type in _no_balance_types,
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

            # "approved" is in-flight while today <= ends_on (within the withdrawal
            # window); it moves to history once the leave period has ended.
            terminal = {"rejected", "withdrawn", "cancelled"}

            # Enrich all rows with approval progress / history summary.
            from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
            from durgam.repositories.approval_step import ApprovalStepRepository

            all_ar_ids = [r.approval_request_id for r in requests]
            ar_map: dict = {}
            if all_ar_ids:
                for ar_row in session.exec(
                    select(ApprovalRequest).where(
                        ApprovalRequest.id.in_(all_ar_ids)  # type: ignore[union-attr]
                    )
                ).all():
                    ar_map[ar_row.id] = ar_row

            leave_proc = session.exec(
                select(ApprovalProcess).where(
                    ApprovalProcess.code == "LEAVE_APPROVAL",  # type: ignore[union-attr]
                    ApprovalProcess.is_deleted == False,  # noqa: E712
                )
            ).first()
            proc_channel_codes: list[str] = (
                leave_proc.channel_role_codes
                if leave_proc and leave_proc.channel_role_codes
                else []
            )

            step_repo = ApprovalStepRepository(session)
            steps_map: dict = {}
            for ar_id in all_ar_ids:
                steps_map[ar_id] = step_repo.list_for_request(ar_id)

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
                ar = ar_map.get(r.approval_request_id)
                is_approved_in_window = (
                    r.state == "approved" and r.ends_on is not None and r.ends_on >= today
                )
                if r.state in terminal or (r.state == "approved" and not is_approved_in_window):
                    row["history_text"] = _build_leave_history_summary(
                        ar, proc_channel_codes, steps_map, r.state
                    )
                    self.history.append(row)
                else:
                    if is_approved_in_window:
                        row["progress_text"] = _build_leave_history_summary(
                            ar, proc_channel_codes, steps_map, r.state
                        )
                    else:
                        row["progress_text"] = _build_leave_progress(ar, proc_channel_codes, steps_map)
                    row["within_withdraw_window"] = is_approved_in_window
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

    async def submit_withdrawal(self, form_data: dict) -> None:
        """Withdraw an approved leave request (post-approval path).

        No @require_role decorator — service enforces actor==requestor internally
        (same pattern as withdraw_leave above). Service also writes the audit row.
        """
        guard = _resolve_or_redirect(self)
        if guard is not None:
            return guard
        reason = form_data.get("withdraw_reason", "").strip()
        request_id = form_data.get("withdraw_request_id", "").strip()
        if len(reason) < 10:
            self.flash = "Reason must be at least 10 characters."
            self.flash_type = "error"
            return
        if not request_id:
            return
        user_id = UUID(self.current_user_id)
        with open_session() as session:
            from durgam.services.leave_request import LeaveRequestError

            try:
                svc = _build_svc(session)
                svc.withdraw(
                    UUID(request_id),
                    actor_user_id=user_id,
                    reason=reason,
                )
                session.commit()
            except (LeaveRequestError, ValueError) as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        self.close_withdraw_modal()
        await self.load_my_leave()
        self.flash = "Your leave has been withdrawn. Balance will be updated."
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

    def set_withdraw_reason(self, value: str) -> None:
        self.withdraw_reason = value

    # ── Withdraw-approved modal lifecycle ────────────────────────────

    def open_withdraw_modal(self, request_id: str) -> None:
        self.withdraw_request_id = request_id
        self.withdraw_reason = ""
        self.show_withdraw_modal = True

    def close_withdraw_modal(self) -> None:
        self.show_withdraw_modal = False
        self.withdraw_reason = ""
        self.withdraw_request_id = ""

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
            from durgam.services.leave_rules import LeaveBalanceError, LeaveChannelError, LeaveEligibilityError, LeaveRuleError

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
            except (LeaveRequestError, LeaveRuleError, LeaveChannelError, LeaveBalanceError, LeaveEligibilityError) as e:
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
