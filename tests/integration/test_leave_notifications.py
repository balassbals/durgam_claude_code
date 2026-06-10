"""TD-037: integration tests for notification enqueueing in the approval engine.

Two tests (post-fix):
  - test_auto_approve_creates_requestor_notification  — reproducer; verifies the fix
  - test_normal_approve_creates_notifications         — regression for existing approve() path

All tests use db_session (clean DB, rollback per test). No seeded_session.
Pattern matches test_leave_request_integration.py exactly.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import func, select

from durgam.models.crosscutting import ApprovalProcess, Notification
from durgam.models.identity import Role, User, UserRole
from durgam.services.approval_request import ApprovalRequestService


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------

def _user(session) -> User:
    from durgam.services.password import hash_password
    u = User(
        username=f"tn{uuid4().hex[:8]}",
        email=f"tn{uuid4().hex[:8]}@test.local",
        full_name="Notification Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _role(session, code: str) -> Role:
    r = Role(code=f"{code}_{uuid4().hex[:6]}", name=f"Test {code}", level=50)
    session.add(r)
    session.flush()
    session.refresh(r)
    return r


def _assign_role(session, user: User, role: Role) -> None:
    ur = UserRole(user_id=user.id, role_id=role.id, scope_type=None, scope_id=None)
    session.add(ur)
    session.flush()


def _process(session, code_suffix: str = "") -> ApprovalProcess:
    """Create a minimal ApprovalProcess with M8 path (channel_role_codes=None)."""
    proc = ApprovalProcess(
        code=f"TEST_NOTIF_{uuid4().hex[:6]}{code_suffix}",
        title="Notification Test Process",
        requestor_role_codes=[],
        channel_role_codes=None,   # M8 path: channel comes from resolved_channel_json
        requires_upward_attachments=False,
        max_upward_attachments=0,
        requires_downward_attachments=False,
        max_downward_attachments=0,
        is_finance=False,
    )
    session.add(proc)
    session.flush()
    session.refresh(proc)
    return proc


def _notification_count(session) -> int:
    return session.exec(
        select(func.count()).select_from(Notification).where(
            Notification.is_deleted == False  # noqa: E712
        )
    ).one()


# ---------------------------------------------------------------------------
# Reproducer — verifies the TD-037 fix is present
# ---------------------------------------------------------------------------

def test_auto_approve_creates_requestor_notification(db_session):
    """Reproducer (TD-037, H1): auto-approve path MUST notify the requestor.

    Setup: requestor is the sole holder of the sole channel role → all stages
    are skipped → request auto-approves at submit() time.

    MUST FAIL in commit 1 (count == 0 before fix).
    MUST PASS in commit 2 (count >= 2: in_app + email for requestor).
    """
    sole_role = _role(db_session, "SOLE")
    requestor = _user(db_session)
    _assign_role(db_session, requestor, sole_role)

    process = _process(db_session)

    svc = ApprovalRequestService(db_session)
    request = svc.submit(
        process_id=process.id,
        requestor_user_id=requestor.id,
        title="Auto-approve notification reproducer",
        resolved_channel=[{"role_code": sole_role.code, "recommend_only": False}],
    )
    db_session.flush()

    # Request must have auto-approved.
    assert request.state == "approved", (
        f"Expected state='approved' (auto-approve); got '{request.state}'"
    )

    count = _notification_count(db_session)
    assert count >= 2, (
        f"Expected ≥ 2 notifications (in_app + email for requestor) after auto-approve; got {count}. "
        "TD-037: _enqueue_notifications(action='approve') missing from auto-approve path."
    )

    # At least one notification must target the requestor with action='approve'.
    approve_notifs = db_session.exec(
        select(Notification).where(
            Notification.recipient_user_id == requestor.id,
            Notification.is_deleted == False,  # noqa: E712
        )
    ).all()
    assert len(approve_notifs) >= 1, (
        f"Expected ≥ 1 notification for requestor {requestor.id}; found 0."
    )
    for n in approve_notifs:
        assert (n.payload_json or {}).get("action") == "approve", (
            f"Expected payload action='approve'; got {n.payload_json!r}"
        )


# ---------------------------------------------------------------------------
# Regression — existing approve() path (line 255) still enqueues notifications
# ---------------------------------------------------------------------------

def test_normal_approve_creates_notifications(db_session):
    """Regression: the existing approve() terminal-notification path is unaffected by the fix.

    Setup: requestor does NOT hold the approver role → auto-approve does NOT fire →
    submit() notifies the approver (action='submit') → approve() notifies the
    requestor (action='approve'). Both calls must produce notification rows.
    """
    approver_role = _role(db_session, "APPROVER")
    requestor_role = _role(db_session, "REQUESTOR")

    requestor = _user(db_session)
    approver = _user(db_session)
    # requestor holds requestor_role only; approver holds approver_role.
    _assign_role(db_session, requestor, requestor_role)
    _assign_role(db_session, approver, approver_role)

    process = _process(db_session)

    svc = ApprovalRequestService(db_session)
    request = svc.submit(
        process_id=process.id,
        requestor_user_id=requestor.id,
        title="Normal approve notification regression",
        resolved_channel=[{"role_code": approver_role.code, "recommend_only": False}],
    )
    db_session.flush()

    # Must NOT have auto-approved — requestor does not hold the approver role.
    assert request.state == "submitted", (
        f"Expected state='submitted' (non-auto-approve); got '{request.state}'"
    )

    # submit() must have notified the approver (action='submit').
    submit_count = _notification_count(db_session)
    assert submit_count >= 2, (
        f"Expected ≥ 2 submit notifications (in_app + email for approver); got {submit_count}."
    )

    # Now approve at stage 1 (terminal).
    svc.approve(
        request_id=request.id,
        approver_user_id=approver.id,
        comment="Looks good",
    )
    db_session.flush()

    assert request.state == "approved"

    # Total notifications: ≥ 4 (2 submit + 2 approve) — both calls worked.
    total_count = _notification_count(db_session)
    assert total_count >= 4, (
        f"Expected ≥ 4 total notifications (submit + approve); got {total_count}."
    )

    # At least one notification must target the requestor with action='approve'.
    approve_notifs = db_session.exec(
        select(Notification).where(
            Notification.recipient_user_id == requestor.id,
            Notification.is_deleted == False,  # noqa: E712
        )
    ).all()
    assert len(approve_notifs) >= 1, (
        f"Expected ≥ 1 approve notification for requestor {requestor.id}; found 0."
    )
    assert all(
        (n.payload_json or {}).get("action") == "approve" for n in approve_notifs
    ), f"All requestor notifications must have action='approve'; got {[n.payload_json for n in approve_notifs]!r}"
