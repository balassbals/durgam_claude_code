"""LeaveRequestService — orchestrates leave submission, withdrawal, approval, and cancellation.

Follows M7 ApprovalRequestService pattern: no @require_role/@audit_action decorators;
page-state handlers own permission enforcement. Service owns domain rules and audit emission.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlmodel import Session, select

from durgam.audit.log import write_audit_row
from durgam.audit.snapshot import audit_snapshot
from durgam.auth.permissions import PermissionDenied, can
from durgam.models.config_anchors import Holiday
from durgam.models.identity import Role, User, UserRole
from durgam.models.leave import LeaveBalance, LeaveRequest
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.repositories.approval_request import ApprovalRequestRepository
from durgam.repositories.leave import (
    LeaveBalanceRepository,
    LeaveSanctionRuleRepository,
    LeaveRepository,
)
from durgam.services.approval_request import ApprovalRequestError, ApprovalRequestService
from durgam.services.leave_rules import (
    LeaveRuleError,
    check_balance,
    check_combination,
    check_eligibility,
    check_max_at_a_time,
    compute_leave_days,
    resolve_channel,
)

log = structlog.get_logger(__name__)


class LeaveRequestError(Exception):
    """Domain errors for the leave request service (non-rules-engine failures)."""


class LeaveRequestService:
    """Owns the LeaveRequest domain. Delegates state machine to ApprovalRequestService."""

    def __init__(
        self,
        session: Session,
        leave_repo: LeaveRepository,
        balance_repo: LeaveBalanceRepository,
        rule_repo: LeaveSanctionRuleRepository,
        approval_service: ApprovalRequestService,
    ) -> None:
        self._session = session
        self._leave_repo = leave_repo
        self._balance_repo = balance_repo
        self._rule_repo = rule_repo
        self._approval_service = approval_service

    def submit(
        self,
        *,
        requestor_user_id: UUID,
        leave_type: str,
        starts_on: date,
        ends_on: date,
        academic_year_id: UUID,
        reason: str,
        half_day: bool = False,
        half_day_which: str | None = None,
        address_during_leave: str | None = None,
        headquarters_left: bool = False,
        alternate_arrangement: str | None = None,
        intended_outside_india: bool = False,
        in_charge_designation: str | None = None,
        medical_cert_file_id: UUID | None = None,
        fitness_cert_file_id: UUID | None = None,
        bond_file_id: UUID | None = None,
        has_medical_cert: bool = False,
        exception_reason: str | None = None,
    ) -> LeaveRequest:
        # 1+2. Load user and build user_fields dict for eligibility checks.
        user = self._session.get(User, requestor_user_id)
        if user is None or user.is_deleted:
            raise LeaveRequestError("Requestor not found.")
        user_fields: dict[str, Any] = {
            "is_active": user.is_active,
            "gender": user.gender,
            "joined_on": user.joined_on,
            "employee_type": user.employee_type,
        }

        # 3. Fetch user role codes for channel resolution.
        user_role_rows = self._session.exec(
            select(UserRole).where(UserRole.user_id == requestor_user_id)
        ).all()
        user_roles: list[str] = []
        for ur in user_role_rows:
            role = self._session.get(Role, ur.role_id)
            if role is not None and not role.is_deleted:
                user_roles.append(role.code)

        # 4. Fetch holiday dates for the AY (CL excludes internal holidays).
        holidays_list = self._session.exec(
            select(Holiday).where(
                Holiday.academic_year_id == academic_year_id,
                Holiday.is_deleted == False,  # noqa: E712
            )
        ).all()
        holidays: set[date] = {h.holiday_date for h in holidays_list}

        # 5. Compute chargeable leave days.
        chargeable_days = compute_leave_days(
            starts_on, ends_on, leave_type, half_day, half_day_which, holidays
        )

        # 6. Total calendar span (prefix/suffix boundary-exclusion is caller's responsibility).
        total_span_days = (ends_on - starts_on).days + 1

        # 7. Eligibility check (ML service ≥ 1yr; SL service ≥ 5yr; active status).
        check_eligibility(user_fields, leave_type, chargeable_days)

        # 8. Balance check — EOL/SL have no running balance; CML debits HPL at 2×.
        if leave_type not in {"EOL", "SL"}:
            bal_leave_type = "HPL" if leave_type == "CML" else leave_type
            balance = self._balance_repo.get_or_create(
                requestor_user_id,
                bal_leave_type,
                academic_year_id,
                actor_id=requestor_user_id,
            )
            check_balance(leave_type, chargeable_days, balance)

        # 9. Max-at-a-time check (span limits, medical cert rules per §11.5–11.7).
        check_max_at_a_time(
            leave_type,
            chargeable_days,
            total_span_days=total_span_days,
            intended_outside_india=intended_outside_india,
            has_medical_cert=has_medical_cert,
            exception_reason=exception_reason,
        )

        # 10. Combination check — no overlapping active requests.
        overlapping = self._leave_repo.list_overlapping(requestor_user_id, starts_on, ends_on)
        check_combination(leave_type, overlapping)

        # 11. Resolve sanctioning channel from the active matrix (may raise LeaveChannelError).
        rules = self._rule_repo.list_active()
        channel = resolve_channel(user_roles, leave_type, rules)

        # 11b. If the matched rule requires an in-charge designation, validate it.
        matched_rule = self._match_rule(user_roles, leave_type, rules)
        if matched_rule is not None and matched_rule.requires_in_charge:
            if not in_charge_designation or not in_charge_designation.strip():
                raise LeaveRuleError("in-charge faculty designation required")

        # 12. Pre-generate the leave request ID so the approval payload can reference it
        #     before the LeaveRequest row exists. This resolves the circular FK:
        #     LeaveRequest.approval_request_id → ApprovalRequest (NOT NULL),
        #     ApprovalRequest.payload_json.leave_request_id → LeaveRequest (soft-ref).
        leave_req_id = uuid4()

        # 13. Submit to approval engine — persists ApprovalRequest and writes its audit row.
        proc_repo = ApprovalProcessRepository(self._session)
        process = proc_repo.get_by_code("LEAVE_APPROVAL")
        if process is None:
            raise LeaveRequestError("LEAVE_APPROVAL approval process not configured.")
        approval_request = self._approval_service.submit(
            process_id=process.id,
            requestor_user_id=requestor_user_id,
            title=f"{leave_type} {starts_on} to {ends_on}",
            payload={"leave_request_id": str(leave_req_id)},
            resolved_channel=channel,
        )

        # 14. Now approval_request.id is known — create and persist the LeaveRequest.
        now = datetime.now(UTC)
        leave_req = LeaveRequest(
            id=leave_req_id,
            requestor_user_id=requestor_user_id,
            academic_year_id=academic_year_id,
            leave_type=leave_type,
            starts_on=starts_on,
            ends_on=ends_on,
            half_day=half_day,
            half_day_which=half_day_which,
            chargeable_days=chargeable_days,
            reason=reason,
            address_during_leave=address_during_leave,
            headquarters_left=headquarters_left,
            alternate_arrangement=alternate_arrangement,
            intended_outside_india=intended_outside_india,
            in_charge_designation=in_charge_designation,
            state="submitted",
            medical_cert_file_id=medical_cert_file_id,
            fitness_cert_file_id=fitness_cert_file_id,
            bond_file_id=bond_file_id,
            approval_request_id=approval_request.id,
            created_by=requestor_user_id,
            updated_by=requestor_user_id,
            created_at=now,
            updated_at=now,
        )
        leave_req.is_post_facto = starts_on < date.today()
        self._leave_repo.add(leave_req)

        # 15. Post-add sync for the auto-approval (skip-self) case.
        #     When the approval engine skips all stages during submit(), it calls
        #     _finalize_leave_from_approval BEFORE the LeaveRequest row is in the DB.
        #     That call returns early (leave_req not found). Re-run it now that the
        #     row is persisted so state and balance are correctly applied.
        if approval_request.state == "approved":
            self._approval_service.finalize_leave_if_auto_approved(
                approval_request.id, requestor_user_id
            )

        self._session.refresh(leave_req)  # pick up state change from finalize callback

        after_snap = audit_snapshot(leave_req)
        write_audit_row(
            actor_user_id=requestor_user_id,
            actor_role_code=None,
            action="create",
            resource="leave_request",
            resource_id=str(leave_req.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after=after_snap,
            session=self._session,
        )

        log.info(
            "leave_request_submitted",
            leave_id=str(leave_req.id),
            leave_type=leave_type,
            requestor=str(requestor_user_id),
            chargeable_days=chargeable_days,
            channel_stages=len(channel),
        )
        return leave_req

    def withdraw(
        self,
        leave_request_id: UUID,
        actor_user_id: UUID,
        reason: str = "",
    ) -> LeaveRequest:
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")

        # Actor authorization: requestor can always withdraw their own; others need admin perm.
        if leave_req.requestor_user_id != actor_user_id:
            if not can(actor_user_id, "write", "leave_request_admin", "*", None, self._session):
                raise PermissionDenied(actor_user_id, "write", "leave_request_admin")

        state = leave_req.state
        if state not in {"submitted", "in_review", "approved"}:
            raise LeaveRequestError(f"Cannot withdraw from state {state!r}.")

        before_snap = audit_snapshot(leave_req)

        if state == "approved":
            return self._withdraw_approved(
                leave_request_id, leave_req, actor_user_id, reason, before_snap
            )

        # ── M8-frozen pre-approval path (submitted | in_review) ──────────────
        # Pass the actual requestor ID so the approval engine's internal ownership
        # check passes (admin-initiated pre-approval withdrawals are routed here too).
        self._approval_service.withdraw(
            request_id=leave_req.approval_request_id,
            requestor_user_id=leave_req.requestor_user_id,
        )
        refreshed = self._leave_repo.get(leave_request_id)
        if refreshed is None:
            raise LeaveRequestError("Leave request disappeared after withdrawal.")

        write_audit_row(
            actor_user_id=actor_user_id,
            actor_role_code=None,
            action="withdraw",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"state": "withdrawn"},
            session=self._session,
        )
        return refreshed

    def _withdraw_approved(
        self,
        leave_request_id: UUID,
        leave_req: LeaveRequest,
        actor_user_id: UUID,
        reason: str,
        before_snap: dict,
    ) -> LeaveRequest:
        """Approved-state withdrawal: reverse unused balance, notify, audit."""
        if not reason.strip():
            raise ValueError(
                "Withdrawal reason is required when withdrawing an approved leave."
            )

        today = date.today()
        ends_on = leave_req.ends_on
        starts_on = leave_req.starts_on

        if today > ends_on:
            raise LeaveRequestError("Cannot withdraw: leave period has ended.")

        # Unused-tail formula (DD-M8.1-P5-1):
        # unused_tail = sanctioned * max(0, (ends_on - max(starts_on, today)).days + 1) / chargeable
        # Capped at sanctioned to prevent over-credit on single-day/half-day leaves.
        sanctioned = leave_req.sanctioned_days if leave_req.sanctioned_days is not None else leave_req.chargeable_days
        chargeable = leave_req.chargeable_days
        calendar_remaining = max(0, (ends_on - max(starts_on, today)).days + 1)
        unused_tail = min(sanctioned, sanctioned * calendar_remaining / chargeable)

        requestor_id = leave_req.requestor_user_id
        ay_id = leave_req.academic_year_id
        leave_type = leave_req.leave_type

        # Balance reversal by type
        if leave_type in {"CL", "EL", "HPL", "ML"} and unused_tail > 0:
            balance = self._balance_repo.get_or_create(
                requestor_id, leave_type, ay_id, actor_id=actor_user_id
            )
            bal, before_bal, after_bal = self._balance_repo.reverse_deduction(
                balance, unused_tail, actor_user_id
            )
            write_audit_row(
                actor_user_id=actor_user_id, actor_role_code=None,
                action="reverse_deduction", resource="leave_balance",
                resource_id=str(bal.id), request_id=None, ip=None, user_agent=None,
                before=before_bal, after=after_bal, session=self._session,
            )

        elif leave_type == "CML" and unused_tail > 0:
            # Re-credit CML days and HPL at 2× (mirrors the debit in _finalize_leave_from_approval)
            cml_bal = self._balance_repo.get_or_create(
                requestor_id, "CML", ay_id, actor_id=actor_user_id
            )
            cml, before_cml, after_cml = self._balance_repo.reverse_deduction(
                cml_bal, unused_tail, actor_user_id
            )
            write_audit_row(
                actor_user_id=actor_user_id, actor_role_code=None,
                action="reverse_deduction", resource="leave_balance",
                resource_id=str(cml.id), request_id=None, ip=None, user_agent=None,
                before=before_cml, after=after_cml, session=self._session,
            )
            hpl_bal = self._balance_repo.get_or_create(
                requestor_id, "HPL", ay_id, actor_id=actor_user_id
            )
            hpl, before_hpl, after_hpl = self._balance_repo.reverse_deduction(
                hpl_bal, unused_tail * 2.0, actor_user_id
            )
            write_audit_row(
                actor_user_id=actor_user_id, actor_role_code=None,
                action="reverse_deduction", resource="leave_balance",
                resource_id=str(hpl.id), request_id=None, ip=None, user_agent=None,
                before=before_hpl, after=after_hpl, session=self._session,
            )
        # SCL, EOL, SL: no balance change

        # Update leave request
        leave_req.withdrawal_reason = reason.strip()[:1000]
        leave_req.state = "withdrawn"
        self._leave_repo.save(leave_req)

        # Transition the backing ApprovalRequest to "withdrawn" directly.
        # ApprovalRequestService.withdraw() only handles "submitted" state; for post-approval
        # withdrawal we bypass it and update the approval_request row directly.
        approval_repo = ApprovalRequestRepository(self._session)
        approval_req = approval_repo.get_by_id_any(leave_req.approval_request_id)
        if approval_req is not None:
            approval_repo.update_state(approval_req, "withdrawn", decided_at=datetime.now(UTC))

        # Notification fan-out
        from durgam.services.leave_notification import resolve_withdrawal_notification_recipients
        from durgam.tasks.leave_jobs import _notify
        requestor = self._session.get(User, requestor_id)
        recipients = resolve_withdrawal_notification_recipients(requestor_id, self._session)
        requestor_display = (requestor.full_name or requestor.username) if requestor else "Unknown"
        subject = f"Leave withdrawn: {requestor_display} ({leave_type}, {starts_on}–{ends_on})"
        body = (
            f"Requestor: {requestor.username if requestor else 'unknown'}\n"
            f"Leave type: {leave_type}\n"
            f"Period: {starts_on} to {ends_on}\n"
            f"Re-credited: {unused_tail:.2f} days\n"
            f"Reason: {reason.strip()[:200]}"
        )
        for recipient in recipients:
            _notify(
                self._session,
                recipient_user_id=recipient.id,
                subject=subject,
                body=body,
                payload={"action": "leave_withdrawn", "leave_request_id": str(leave_request_id)},
            )

        actor_roles = self._get_actor_roles_json(actor_user_id)
        write_audit_row(
            actor_user_id=actor_user_id,
            actor_role_code=None,
            action="withdraw",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"state": "withdrawn", "withdrawal_reason": reason.strip()[:1000]},
            actor_roles_json=actor_roles,
            session=self._session,
        )

        log.info(
            "leave_request_withdrawn_post_approval",
            leave_id=str(leave_request_id),
            leave_type=leave_type,
            actor=str(actor_user_id),
            unused_tail=unused_tail,
            recipients=len(recipients),
        )

        refreshed = self._leave_repo.get(leave_request_id)
        if refreshed is None:
            raise LeaveRequestError("Leave request disappeared after withdrawal.")
        return refreshed

    def _get_actor_roles_json(self, actor_user_id: UUID) -> list[dict]:
        user_role_rows = self._session.exec(
            select(UserRole).where(UserRole.user_id == actor_user_id)
        ).all()
        result = []
        for ur in user_role_rows:
            role = self._session.get(Role, ur.role_id)
            if role and not role.is_deleted:
                result.append({
                    "role_code": role.code,
                    "scope_type": ur.scope_type,
                    "scope_id": str(ur.scope_id) if ur.scope_id else None,
                })
        return result

    def cancel(
        self,
        leave_request_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> LeaveRequest:
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")

        before_snap = audit_snapshot(leave_req)
        self._approval_service.cancel(
            request_id=leave_req.approval_request_id,
            sys_admin_user_id=actor_id,
            comment=reason,
        )
        leave_req.cancellation_reason = reason
        leave_req.state = "cancelled"
        self._leave_repo.save(leave_req)

        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="cancel",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"state": "cancelled", "cancellation_reason": reason},
            session=self._session,
        )
        return leave_req

    def set_sanctioned_days(
        self,
        leave_request_id: UUID,
        approver_user_id: UUID,
        sanctioned_days: float,
    ) -> LeaveRequest:
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")
        if sanctioned_days <= 0 or sanctioned_days > leave_req.chargeable_days:
            raise LeaveRequestError(
                f"sanctioned_days must be > 0 and ≤ chargeable_days "
                f"({leave_req.chargeable_days}); got {sanctioned_days}"
            )

        before_snap = audit_snapshot(leave_req)
        leave_req.sanctioned_days = sanctioned_days
        self._leave_repo.save(leave_req)

        write_audit_row(
            actor_user_id=approver_user_id,
            actor_role_code=None,
            action="set_sanctioned_days",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"sanctioned_days": sanctioned_days},
            session=self._session,
        )
        return leave_req

    def get_balances_for_user(
        self,
        user_id: UUID,
        academic_year_id: UUID,
    ) -> list[LeaveBalance]:
        return self._balance_repo.list_for_user(user_id, academic_year_id)

    def preview_chargeable_days(
        self,
        *,
        leave_type: str,
        starts_on: date,
        ends_on: date,
        academic_year_id: UUID,
        half_day: bool = False,
        half_day_which: str | None = None,
    ) -> float:
        """Return the chargeable leave day count without running eligibility/balance checks.

        Used by the Apply form to show the user how many days will be charged before submit.
        """
        holidays_list = self._session.exec(
            select(Holiday).where(
                Holiday.academic_year_id == academic_year_id,
                Holiday.is_deleted == False,  # noqa: E712
            )
        ).all()
        holidays: set[date] = {h.holiday_date for h in holidays_list}
        return compute_leave_days(starts_on, ends_on, leave_type, half_day, half_day_which, holidays)

    def preview_channel(
        self,
        requestor_user_id: UUID,
        leave_type: str,
    ) -> list[dict]:
        """Return the approval channel stages without committing any state.

        Returns the same structure as resolve_channel: list of dicts with
        role_code, recommend_only, scope_type keys.
        Raises LeaveChannelError if no rule matches.
        """
        user_role_rows = self._session.exec(
            select(UserRole).where(UserRole.user_id == requestor_user_id)
        ).all()
        user_roles: list[str] = []
        for ur in user_role_rows:
            role = self._session.get(Role, ur.role_id)
            if role is not None and not role.is_deleted:
                user_roles.append(role.code)

        rules = self._rule_repo.list_active()
        return resolve_channel(user_roles, leave_type, rules)

    # ── Admin state-change ───────────────────────────────────────────────

    _ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        "submitted": {"cancelled", "rejected"},
        "in_review":  {"cancelled", "rejected"},
        "approved":   {"cancelled", "withdrawn"},
    }

    def admin_change_state(
        self,
        leave_request_id: UUID,
        new_state: str,
        actor_user_id: UUID,
        reason: str = "",
    ) -> LeaveRequest:
        """Admin-initiated state transition for leave requests.

        Allowed transitions (DD-M8.1-P8-5):
          submitted → cancelled | rejected
          in_review → cancelled | rejected
          approved  → cancelled | withdrawn   (delegates to withdraw())

        Reason is required for all six transitions.
        Raises LeaveRequestError for forbidden transitions.
        Raises ValueError for missing reason.
        """
        if not reason.strip():
            raise ValueError("Reason is required.")
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")
        current_state = leave_req.state
        allowed = self._ALLOWED_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            raise LeaveRequestError(
                f"Transition {current_state!r} → {new_state!r} is not allowed."
            )
        # approved → cancelled / approved → withdrawn: delegate to withdraw()
        # (handles balance reversal, notification fan-out, admin bypass check)
        if current_state == "approved":
            return self.withdraw(leave_request_id, actor_user_id=actor_user_id, reason=reason)
        # submitted/in_review → cancelled or rejected
        before_snap = audit_snapshot(leave_req)
        if new_state == "cancelled":
            self._approval_service.cancel(
                request_id=leave_req.approval_request_id,
                sys_admin_user_id=actor_user_id,
                comment=reason,
            )
            leave_req.cancellation_reason = reason
        else:
            # rejected
            self._approval_service.cancel(
                request_id=leave_req.approval_request_id,
                sys_admin_user_id=actor_user_id,
                comment=reason,
            )
        leave_req.state = new_state
        self._leave_repo.save(leave_req)

        write_audit_row(
            actor_user_id=actor_user_id,
            actor_role_code=None,
            action=f"admin_{new_state}",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"state": new_state, "reason": reason.strip()},
            session=self._session,
        )

        from durgam.tasks.leave_jobs import _notify
        requestor = self._session.get(User, leave_req.requestor_user_id)
        if requestor is not None:
            subject = (
                f"Leave {new_state}: "
                f"{leave_req.leave_type} {leave_req.starts_on}–{leave_req.ends_on}"
            )
            body = (
                f"Your leave request has been {new_state} by an administrator.\n"
                f"Reason: {reason.strip()[:200]}"
            )
            _notify(
                self._session,
                recipient_user_id=requestor.id,
                subject=subject,
                body=body,
                payload={"action": f"leave_{new_state}", "leave_request_id": str(leave_request_id)},
            )

        refreshed = self._leave_repo.get(leave_request_id)
        if refreshed is None:
            raise LeaveRequestError("Leave request disappeared after state change.")
        return refreshed

    # ── Post-facto forfeiture reversal ────────────────────────────────────

    @staticmethod
    def _reverse_cl_forfeitures_for_postfacto(
        session: Session,
        leave_req: "LeaveRequest",
    ) -> None:
        """Reverse CL forfeitures for months covered by a post-facto approved leave.

        Staticmethod — called by ApprovalRequestService._finalize_leave_from_approval via
        deferred import to avoid circular service initialization.
        Only applies to CL leave type. For non-CL: no-op.
        """
        if leave_req.leave_type != "CL":
            return
        from durgam.repositories.leave import LateAttendanceMarkerRepository, LeaveBalanceRepository  # noqa: F401
        # Collect YYYY-MM strings covered by the leave period
        covered_months: list[str] = []
        cur = date(leave_req.starts_on.year, leave_req.starts_on.month, 1)
        end_month = date(leave_req.ends_on.year, leave_req.ends_on.month, 1)
        while cur <= end_month:
            covered_months.append(cur.strftime("%Y-%m"))
            year, month = cur.year, cur.month
            cur = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        if not covered_months:
            return
        marker_repo = LateAttendanceMarkerRepository(session)
        markers = marker_repo.get_late_markers_in_range(
            leave_req.requestor_user_id,
            leave_req.starts_on,
            leave_req.ends_on,
        )
        marker_months = {m.occurred_on.strftime("%Y-%m") for m in markers}
        months_to_reverse = [m for m in covered_months if m in marker_months]
        if not months_to_reverse:
            return
        bal_repo = LeaveBalanceRepository(session)
        balance = bal_repo.get_or_create(
            leave_req.requestor_user_id,
            "CL",
            leave_req.academic_year_id,
            actor_id=leave_req.requestor_user_id,
        )
        results = bal_repo.reverse_cl_forfeiture_for_months(
            balance,
            months_to_reverse,
            actor_id=leave_req.requestor_user_id,
        )
        for before_snap, after_snap in results:
            write_audit_row(
                actor_user_id=leave_req.requestor_user_id,
                actor_role_code=None,
                action="postfacto_forfeit_reversal",
                resource="leave_balance",
                resource_id=str(balance.id),
                request_id=None,
                ip=None,
                user_agent=None,
                before=before_snap,
                after=after_snap,
                session=session,
            )

    # ── Private helpers ─────────────────────────────────────────────────

    def _match_rule(
        self, user_roles: list[str], leave_type: str, rules: list[Any]
    ) -> Any | None:
        """Return the highest-priority matching sanctioning rule, or None.

        Mirrors the rule-selection algorithm in resolve_channel so the service
        can inspect requires_in_charge without re-opening that function.
        """
        candidates = [
            r for r in rules
            if (r.leave_type == leave_type or r.leave_type == "*")
            and (r.applicant_role_code in user_roles or r.applicant_role_code == "*")
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda r: r.priority)[0]
