"""Leave Celery jobs: CL forfeiture, EL/HPL credit, overstay flag (M8 Phase 6).

All tasks accept an optional reference_date for deterministic testing.
Notifications are table-enqueued (Q-NOTIF — no asyncio.create_task per M7 convention).
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlmodel import select

from durgam.audit.log import write_audit_row
from durgam.audit.snapshot import audit_snapshot
from durgam.db import open_session
from durgam.models.config_anchors import AcademicYear
from durgam.models.crosscutting import Notification
from durgam.models.identity import Role, User, UserRole
from durgam.models.leave import (
    LateAttendanceMarker,
    LeaveBalance,
    LeaveRequest,
)
from durgam.services.leave_rules import is_vacation_employee
from durgam.tasks.celery_app import app

log = structlog.get_logger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────────


def _active_ay(session, ref: date) -> AcademicYear | None:
    return session.exec(
        select(AcademicYear).where(
            AcademicYear.starts_on <= ref,
            AcademicYear.ends_on >= ref,
            AcademicYear.is_deleted == False,  # noqa: E712
        )
    ).first()


def _notify(
    session,
    *,
    recipient_user_id: UUID,
    subject: str,
    body: str,
    payload: dict | None = None,
) -> None:
    """Enqueue in_app + email notifications for one recipient (table-only, no SMTP)."""
    now = datetime.now(UTC)
    for channel in ("in_app", "email"):
        notif = Notification(
            recipient_user_id=recipient_user_id,
            channel=channel,
            subject=subject,
            body_text=body,
            payload_json=payload or {},
            delivery_status="pending",
            created_at=now,
            updated_at=now,
        )
        session.add(notif)
    session.flush()


# ── Job 1: forfeit_late_cl ─────────────────────────────────────────────────────


@app.task(name="durgam.tasks.leave_jobs.forfeit_late_cl")
def forfeit_late_cl(reference_date: date | None = None) -> dict:
    """Forfeit 1 day CL for employees with ≥3 late-attendance markers in the previous month.

    Runs nightly at 00:30 UTC. reference_date enables deterministic tests.
    Idempotency: balance.forfeiture_applied_for is a JSONB list of "YYYY-MM" period keys;
    a period key is appended on forfeiture and checked before re-running.
    """
    ref = reference_date or date.today()

    prev_year = ref.year if ref.month > 1 else ref.year - 1
    prev_month = ref.month - 1 if ref.month > 1 else 12
    period_key = f"{prev_year:04d}-{prev_month:02d}"
    prev_month_start = date(prev_year, prev_month, 1)
    prev_month_end = date(
        prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1]
    )

    employees_processed = 0
    employees_forfeited = 0
    employees_skipped = 0
    errors: list[dict] = []

    with open_session() as session:
        ay = _active_ay(session, ref)
        if ay is None:
            log.warning("forfeit_late_cl_no_ay", ref=str(ref))
            return {
                "period": period_key,
                "employees_processed": 0,
                "employees_forfeited": 0,
                "employees_skipped_idempotent": 0,
                "errors": [{"error": "No active AY found for ref date"}],
            }

        markers = session.exec(
            select(LateAttendanceMarker).where(
                LateAttendanceMarker.occurred_on >= prev_month_start,
                LateAttendanceMarker.occurred_on <= prev_month_end,
                LateAttendanceMarker.is_deleted == False,  # noqa: E712
            )
        ).all()

        by_employee: dict[UUID, int] = defaultdict(int)
        for m in markers:
            by_employee[m.employee_user_id] += 1

        for user_id, count in by_employee.items():
            if count < 3:
                continue
            employees_processed += 1
            try:
                balance = session.exec(
                    select(LeaveBalance).where(
                        LeaveBalance.employee_user_id == user_id,
                        LeaveBalance.leave_type == "CL",
                        LeaveBalance.academic_year_id == ay.id,
                        LeaveBalance.is_deleted == False,  # noqa: E712
                    )
                ).first()
                if balance is None:
                    log.warning(
                        "forfeit_late_cl_no_balance", user_id=str(user_id)
                    )
                    continue

                if period_key in balance.forfeiture_applied_for:
                    employees_skipped += 1
                    continue

                before_snap = audit_snapshot(balance)
                balance.forfeited += 1.0
                balance.closing_balance -= 1.0
                balance.forfeiture_applied_for = (
                    list(balance.forfeiture_applied_for) + [period_key]
                )
                session.add(balance)
                session.flush()
                session.refresh(balance)

                write_audit_row(
                    actor_user_id=None,
                    actor_role_code=None,
                    action="forfeit_cl",
                    resource="leave_balance",
                    resource_id=str(balance.id),
                    request_id=None,
                    ip=None,
                    user_agent=None,
                    before=before_snap,
                    after=audit_snapshot(balance),
                    session=session,
                )
                _notify(
                    session,
                    recipient_user_id=user_id,
                    subject="CL Forfeiture Notice",
                    body=(
                        f"1 day of Casual Leave has been forfeited for "
                        f"late attendance in {period_key}."
                    ),
                    payload={"period": period_key, "days_forfeited": 1.0},
                )
                employees_forfeited += 1
                log.info(
                    "forfeit_late_cl_forfeited",
                    user_id=str(user_id),
                    period=period_key,
                )
            except Exception as exc:
                log.exception(
                    "forfeit_late_cl_error", user_id=str(user_id), exc=str(exc)
                )
                errors.append({"user_id": str(user_id), "error": str(exc)})

        session.commit()

    return {
        "period": period_key,
        "employees_processed": employees_processed,
        "employees_forfeited": employees_forfeited,
        "employees_skipped_idempotent": employees_skipped,
        "errors": errors,
    }


# ── Job 2: lapse_unavailed_cl ─────────────────────────────────────────────────


@app.task(name="durgam.tasks.leave_jobs.lapse_unavailed_cl")
def lapse_unavailed_cl(reference_date: date | None = None) -> dict:
    """Zero positive CL balances on 31 December (RFP §11.3 "un-availed CL lapses").

    Runs Dec 31 at 23:00 UTC. Idempotent: closing_balance > 0 guard means re-runs
    are no-ops once balances are already zeroed.
    """
    ref = reference_date or date.today()

    employees_processed = 0
    employees_lapsed = 0
    total_days_lapsed = 0.0
    errors: list[dict] = []

    with open_session() as session:
        ay = _active_ay(session, ref)
        if ay is None:
            log.warning("lapse_unavailed_cl_no_ay", ref=str(ref))
            return {
                "employees_processed": 0,
                "employees_lapsed": 0,
                "total_days_lapsed": 0.0,
                "errors": [{"error": "No active AY found for ref date"}],
            }

        active_users = session.exec(
            select(User).where(
                User.is_active == True,  # noqa: E712
                User.is_deleted == False,  # noqa: E712
            )
        ).all()

        for user in active_users:
            employees_processed += 1
            try:
                balance = session.exec(
                    select(LeaveBalance).where(
                        LeaveBalance.employee_user_id == user.id,
                        LeaveBalance.leave_type == "CL",
                        LeaveBalance.academic_year_id == ay.id,
                        LeaveBalance.is_deleted == False,  # noqa: E712
                    )
                ).first()
                if balance is None or balance.closing_balance <= 0:
                    continue

                lapse_days = balance.closing_balance
                before_snap = audit_snapshot(balance)
                balance.forfeited += lapse_days
                balance.closing_balance = 0.0
                session.add(balance)
                session.flush()
                session.refresh(balance)

                write_audit_row(
                    actor_user_id=None,
                    actor_role_code=None,
                    action="lapse_cl",
                    resource="leave_balance",
                    resource_id=str(balance.id),
                    request_id=None,
                    ip=None,
                    user_agent=None,
                    before=before_snap,
                    after=audit_snapshot(balance),
                    session=session,
                )
                _notify(
                    session,
                    recipient_user_id=user.id,
                    subject="CL Balance Lapsed",
                    body=(
                        f"{lapse_days:.1f} day(s) of Casual Leave have lapsed "
                        f"as of 31 December."
                    ),
                    payload={"days_lapsed": lapse_days},
                )
                employees_lapsed += 1
                total_days_lapsed += lapse_days
                log.info(
                    "lapse_unavailed_cl_lapsed",
                    user_id=str(user.id),
                    days=lapse_days,
                )
            except Exception as exc:
                log.exception(
                    "lapse_unavailed_cl_error", user_id=str(user.id), exc=str(exc)
                )
                errors.append({"user_id": str(user.id), "error": str(exc)})

        session.commit()

    return {
        "employees_processed": employees_processed,
        "employees_lapsed": employees_lapsed,
        "total_days_lapsed": total_days_lapsed,
        "errors": errors,
    }


# ── Job 3: credit_periodic_el_hpl ─────────────────────────────────────────────


def _last_credit_date(balance: LeaveBalance, joined: date) -> date:
    if balance.last_credited_at is not None:
        return balance.last_credited_at.date()
    return joined


def _ref_to_dt(ref: date) -> datetime:
    return datetime(ref.year, ref.month, ref.day, tzinfo=UTC)


def _credit_el(
    session,
    user: User,
    ay_id: UUID,
    ref: date,
    period_start_dt: datetime,
    period_label: str,
    joined: date,
) -> bool:
    """Credit EL for one employee. Returns True if credit was applied.

    Vacation (teaching) employees receive component (a) only: days_of_service / 30.
    Components (b) vacation-duty and (c) LWP adjustment are deferred to M13.
    See TD-035.
    """
    from durgam.repositories.leave import LeaveBalanceRepository

    bal_repo = LeaveBalanceRepository(session)
    balance = bal_repo.get_or_create(user.id, "EL", ay_id, actor_id=user.id)

    if balance.last_credited_at is not None and balance.last_credited_at >= period_start_dt:
        return False  # already credited this period

    last_date = _last_credit_date(balance, joined)
    days_since = max(0, (ref - last_date).days)
    months_since = round(days_since / 30.0 * 2) / 2  # round to nearest 0.5

    if is_vacation_employee(user.employee_type):
        el_credit = days_since / 30.0  # component (a) only — see TD-035
    else:
        el_credit = months_since * 2.5

    el_headroom = max(0.0, 300.0 - balance.closing_balance)
    effective_credit = min(el_credit, el_headroom)
    if effective_credit <= 0:
        return False

    before_snap = audit_snapshot(balance)
    balance.credited += effective_credit
    balance.closing_balance += effective_credit
    balance.last_credited_at = _ref_to_dt(ref)
    session.add(balance)
    session.flush()
    session.refresh(balance)

    write_audit_row(
        actor_user_id=None,
        actor_role_code=None,
        action="credit_el",
        resource="leave_balance",
        resource_id=str(balance.id),
        request_id=None,
        ip=None,
        user_agent=None,
        before=before_snap,
        after=audit_snapshot(balance),
        session=session,
    )
    _notify(
        session,
        recipient_user_id=user.id,
        subject="EL Credit",
        body=(
            f"{effective_credit:.2f} days of Earned Leave credited "
            f"for period {period_label}."
        ),
        payload={
            "period": period_label,
            "days_credited": effective_credit,
            "leave_type": "EL",
        },
    )
    log.info("credit_el", user_id=str(user.id), days=effective_credit, period=period_label)
    return True


def _credit_hpl(
    session,
    user: User,
    ay_id: UUID,
    ref: date,
    period_start_dt: datetime,
    period_label: str,
    joined: date,
) -> bool:
    """Credit HPL for one employee at 5/3 days per month. Returns True if applied."""
    from durgam.repositories.leave import LeaveBalanceRepository

    bal_repo = LeaveBalanceRepository(session)
    balance = bal_repo.get_or_create(user.id, "HPL", ay_id, actor_id=user.id)

    if balance.last_credited_at is not None and balance.last_credited_at >= period_start_dt:
        return False

    last_date = _last_credit_date(balance, joined)
    days_since = max(0, (ref - last_date).days)
    months_since = round(days_since / 30.0 * 2) / 2

    hpl_credit = months_since * (5.0 / 3.0)
    hpl_headroom = max(0.0, 180.0 - balance.closing_balance)
    effective_credit = min(hpl_credit, hpl_headroom)
    if effective_credit <= 0:
        return False

    before_snap = audit_snapshot(balance)
    balance.credited += effective_credit
    balance.closing_balance += effective_credit
    balance.last_credited_at = _ref_to_dt(ref)
    session.add(balance)
    session.flush()
    session.refresh(balance)

    write_audit_row(
        actor_user_id=None,
        actor_role_code=None,
        action="credit_hpl",
        resource="leave_balance",
        resource_id=str(balance.id),
        request_id=None,
        ip=None,
        user_agent=None,
        before=before_snap,
        after=audit_snapshot(balance),
        session=session,
    )
    _notify(
        session,
        recipient_user_id=user.id,
        subject="HPL Credit",
        body=(
            f"{effective_credit:.2f} days of Half-Pay Leave credited "
            f"for period {period_label}."
        ),
        payload={
            "period": period_label,
            "days_credited": effective_credit,
            "leave_type": "HPL",
        },
    )
    log.info("credit_hpl", user_id=str(user.id), days=effective_credit, period=period_label)
    return True


@app.task(name="durgam.tasks.leave_jobs.credit_periodic_el_hpl")
def credit_periodic_el_hpl(reference_date: date | None = None) -> dict:
    """Credit EL and HPL for all active employees at the start of each half-year.

    Scheduled: 1 Jan and 1 Jul at 02:00 UTC (two beat entries, same function).
    The function determines the current period from reference_date.

    EL credit rules (RFP §11.5):
    - Non-vacation employees: 2.5 days per month of service in the period.
    - Vacation (teaching) employees: days_of_service / 30 for component (a) only.
      Components (b) vacation-duty and (c) LWP adjustment require M13 Attendance.
      See TD-035 for full formula and deferral rationale.
    HPL credit: 5/3 days per month for all employee types.
    Accumulation caps: EL 300 days, HPL 180 days.
    Idempotency: balance.last_credited_at >= period_start triggers a skip.
    """
    ref = reference_date or date.today()

    is_h1 = ref.month <= 6
    period_label = f"{ref.year}-H{'1' if is_h1 else '2'}"
    period_start = date(ref.year, 1, 1) if is_h1 else date(ref.year, 7, 1)
    period_start_dt = datetime(
        period_start.year, period_start.month, period_start.day, tzinfo=UTC
    )

    el_credits = 0
    hpl_credits = 0
    errors: list[dict] = []

    with open_session() as session:
        ay = _active_ay(session, ref)
        if ay is None:
            log.warning("credit_periodic_el_hpl_no_ay", ref=str(ref))
            return {
                "period": period_label,
                "el_credits": 0,
                "hpl_credits": 0,
                "errors": [{"error": "No active AY found for ref date"}],
            }

        active_users = session.exec(
            select(User).where(
                User.is_active == True,  # noqa: E712
                User.is_deleted == False,  # noqa: E712
            )
        ).all()

        for user in active_users:
            joined = user.joined_on or period_start
            try:
                if _credit_el(
                    session, user, ay.id, ref, period_start_dt, period_label, joined
                ):
                    el_credits += 1
            except Exception as exc:
                log.exception(
                    "credit_el_error", user_id=str(user.id), exc=str(exc)
                )
                errors.append(
                    {"user_id": str(user.id), "type": "EL", "error": str(exc)}
                )
            try:
                if _credit_hpl(
                    session, user, ay.id, ref, period_start_dt, period_label, joined
                ):
                    hpl_credits += 1
            except Exception as exc:
                log.exception(
                    "credit_hpl_error", user_id=str(user.id), exc=str(exc)
                )
                errors.append(
                    {"user_id": str(user.id), "type": "HPL", "error": str(exc)}
                )

        session.commit()

    return {
        "period": period_label,
        "el_credits": el_credits,
        "hpl_credits": hpl_credits,
        "errors": errors,
    }


# ── Job 4: check_overstay ─────────────────────────────────────────────────────


@app.task(name="durgam.tasks.leave_jobs.check_overstay")
def check_overstay(reference_date: date | None = None) -> dict:
    """Flag approved leave requests whose ends_on has passed without return-to-duty.

    Runs nightly at 01:00 UTC (RFP §11.2 "absence after expiry treated as EOL").
    Idempotent: overstay_flagged = True guard prevents re-flagging.

    Auto-EOL LeaveRequest creation is NOT in v1. Deferred until M13 Attendance
    Module ships return-to-duty records — without that data, the overstay duration
    cannot be computed accurately. When M13 lands, extend this job to create an
    EOL LeaveRequest for the gap between ends_on and the recorded return date.
    """
    ref = reference_date or date.today()

    flagged = 0
    errors: list[dict] = []

    with open_session() as session:
        overstayed = session.exec(
            select(LeaveRequest).where(
                LeaveRequest.state == "approved",
                LeaveRequest.ends_on < ref,
                LeaveRequest.overstay_flagged == False,  # noqa: E712
                LeaveRequest.is_deleted == False,  # noqa: E712
            )
        ).all()

        hr_head_role = session.exec(
            select(Role).where(
                Role.code == "HR_HEAD",
                Role.is_deleted == False,  # noqa: E712
            )
        ).first()
        hr_head_user_ids: list[UUID] = []
        if hr_head_role is not None:
            hr_head_urs = session.exec(
                select(UserRole).where(UserRole.role_id == hr_head_role.id)
            ).all()
            hr_head_user_ids = [ur.user_id for ur in hr_head_urs]

        for leave_req in overstayed:
            try:
                before_snap = audit_snapshot(leave_req)
                leave_req.overstay_flagged = True
                session.add(leave_req)
                session.flush()
                session.refresh(leave_req)

                write_audit_row(
                    actor_user_id=None,
                    actor_role_code=None,
                    action="flag_overstay",
                    resource="leave_request",
                    resource_id=str(leave_req.id),
                    request_id=None,
                    ip=None,
                    user_agent=None,
                    before=before_snap,
                    after=audit_snapshot(leave_req),
                    session=session,
                )
                _notify(
                    session,
                    recipient_user_id=leave_req.requestor_user_id,
                    subject="Leave Overstay Flagged",
                    body=(
                        "Your approved leave has ended but return-to-duty has not "
                        "been recorded. This overstay is being treated as "
                        "Extraordinary Leave per RFP §11.2."
                    ),
                    payload={"leave_request_id": str(leave_req.id)},
                )
                for hr_uid in hr_head_user_ids:
                    _notify(
                        session,
                        recipient_user_id=hr_uid,
                        subject="Employee Leave Overstay",
                        body=(
                            f"An approved leave ending {leave_req.ends_on} has not "
                            "been followed by return-to-duty."
                        ),
                        payload={"leave_request_id": str(leave_req.id)},
                    )
                flagged += 1
                log.info(
                    "check_overstay_flagged",
                    leave_request_id=str(leave_req.id),
                )
            except Exception as exc:
                log.exception(
                    "check_overstay_error",
                    leave_request_id=str(leave_req.id),
                    exc=str(exc),
                )
                errors.append(
                    {"leave_request_id": str(leave_req.id), "error": str(exc)}
                )

        session.commit()

    return {"flagged": flagged, "errors": errors}
