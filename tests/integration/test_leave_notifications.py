"""TD-037: integration tests for notification enqueueing in the approval engine.

Commit 1 contains two tests:
  - test_notifications_zero_before_fix  (diagnostic; MUST PASS pre-fix; deleted in commit 2)
  - test_auto_approve_creates_requestor_notification  (reproducer; MUST FAIL pre-fix)

Commit 2 adds:
  - test_normal_approve_creates_notifications  (regression for the existing approve() path)
  and deletes test_notifications_zero_before_fix.

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
# Diagnostic test (COMMIT 1 only — deleted in commit 2)
# ---------------------------------------------------------------------------

def test_notifications_zero_before_fix(db_session):
    """DIAGNOSTIC (delete in commit 2): auto-approve path enqueues zero notifications.

    This test MUST PASS before the fix — it proves TD-037 is real.
    Root cause (H1): ApprovalRequestService.submit() auto-approve block calls
    _run_post_approval() but never calls _enqueue_notifications(action='approve').
    Pre-fix count is 0; post-fix count is ≥ 2 (in_app + email for requestor).
    """
    sole_role = _role(db_session, "SOLE")
    requestor = _user(db_session)
    _assign_role(db_session, requestor, sole_role)

    process = _process(db_session)

    svc = ApprovalRequestService(db_session)
    svc.submit(
        process_id=process.id,
        requestor_user_id=requestor.id,
        title="Auto-approve notification diagnostic",
        resolved_channel=[{"role_code": sole_role.code, "recommend_only": False}],
    )
    db_session.flush()

    count = _notification_count(db_session)
    # Pre-fix: this assertion passes (count IS 0, proving the bug).
    # Post-fix: this assertion fails (count is ≥ 2), which is why it is deleted.
    assert count == 0, (
        f"Diagnostic passed: zero notifications on auto-approve path (count={count}). "
        "TD-037 bug confirmed. Delete this test in commit 2."
    )


# ---------------------------------------------------------------------------
# Reproducer (survives into commit 2; asserts the fix is present)
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
