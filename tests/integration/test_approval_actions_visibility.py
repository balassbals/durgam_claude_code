"""Integration tests for ApprovalAction visibility model (M10 Phase 7A).

Coverage:
  ApprovalAction created on approve (5 tests):
  1  test_approve_creates_approval_action_row
  2  test_approve_action_has_correct_fields
  3  test_approve_action_default_visibility_is_true
  4  test_approve_action_custom_visibility_false
  5  test_approve_action_with_visible_to_lower_user_ids

  ApprovalAction created on reject (3 tests):
  6  test_reject_creates_approval_action_row
  7  test_reject_action_has_correct_fields
  8  test_reject_action_default_visibility_is_true

  list_actions_for_requestor (4 tests):
  9  test_list_actions_for_requestor_returns_visible_action
  10 test_list_actions_for_requestor_excludes_invisible_action
  11 test_list_actions_for_requestor_empty_when_no_actions
  12 test_list_actions_for_requestor_filters_correctly_when_mixed

  list_actions_for_approver (6 tests):
  13 test_list_actions_for_approver_own_action_always_visible
  14 test_list_actions_for_approver_lower_stage_visible
  15 test_list_actions_for_approver_same_stage_visible
  16 test_list_actions_for_approver_higher_stage_excluded_by_default
  17 test_list_actions_for_approver_higher_stage_visible_when_granted
  18 test_list_actions_for_approver_returns_empty_for_no_actions

DB strategy: db_session (function-scoped, rolls back). All tests use synthetic data only.
0 skips in isolation. No seed dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Session

from durgam.models.crosscutting import ApprovalAction, ApprovalProcess, ApprovalRequest
from durgam.models.identity import Role, User, UserRole
from durgam.repositories.approval_action import ApprovalActionRepository
from durgam.services.approval_request import ApprovalRequestService


# ── Helpers ────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_user(session: Session) -> User:
    uid = uuid4().hex[:8]
    now = _now()
    user = User(
        username=f"aa7_{uid}",
        email=f"aa7_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return user


def _make_role(session: Session, code: str) -> Role:
    now = _now()
    role = Role(code=code, name=f"Role {code}", level=50, created_at=now, updated_at=now)
    session.add(role)
    session.flush()
    return role


def _link_universitywide(session: Session, user: User, role: Role) -> UserRole:
    """Assign user the role with no scope (universitywide scope_type=NULL)."""
    ur = UserRole(user_id=user.id, role_id=role.id, scope_type=None, scope_id=None)
    session.add(ur)
    session.flush()
    return ur


def _make_process(session: Session, role_code: str) -> ApprovalProcess:
    """Create a synthetic 1-stage legacy ApprovalProcess (no OR-set options)."""
    now = _now()
    proc = ApprovalProcess(
        code=f"T7A_{uuid4().hex[:8]}",
        title="Test Phase 7A Process",
        channel_role_codes=[role_code],
        requestor_role_codes=["FACULTY"],
        created_at=now,
        updated_at=now,
    )
    session.add(proc)
    session.flush()
    return proc


def _make_request(
    session: Session,
    process: ApprovalProcess,
    requestor: User,
    *,
    stage: int = 1,
    state: str = "submitted",
) -> ApprovalRequest:
    """Create an ApprovalRequest at the given stage."""
    now = _now()
    req = ApprovalRequest(
        process_id=process.id,
        requestor_user_id=requestor.id,
        title="Test 7A Request",
        state=state,
        current_stage=stage,
        created_by=requestor.id,
        updated_by=requestor.id,
        created_at=now,
        updated_at=now,
    )
    session.add(req)
    session.flush()
    session.refresh(req)
    return req


def _make_action(
    session: Session,
    approval_request_id: UUID,
    actor_user_id: UUID,
    *,
    stage_index: int = 1,
    action_type: str = "approve",
    comment: str | None = None,
    is_visible_to_requestor: bool = True,
    visible_to_lower_user_ids_json: list[str] | None = None,
) -> ApprovalAction:
    """Directly insert an ApprovalAction row — used for visibility filter tests."""
    now = _now()
    action = ApprovalAction(
        approval_request_id=approval_request_id,
        stage_index=stage_index,
        actor_user_id=actor_user_id,
        action_type=action_type,
        comment=comment,
        is_visible_to_requestor=is_visible_to_requestor,
        visible_to_lower_user_ids_json=visible_to_lower_user_ids_json,
        created_by=actor_user_id,
        updated_by=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(action)
    session.flush()
    return action


def _setup_approve_pair(
    session: Session,
) -> tuple[User, User, ApprovalProcess, ApprovalRequest]:
    """Create a requestor, an approver (universitywide), and a 1-stage process + request."""
    role_code = f"A7_{uuid4().hex[:8]}"
    requestor = _make_user(session)
    approver = _make_user(session)
    role = _make_role(session, role_code)
    _link_universitywide(session, approver, role)
    proc = _make_process(session, role_code)
    req = _make_request(session, proc, requestor)
    return requestor, approver, proc, req


# ── Group A: ApprovalAction created on approve ────────────────────────────────


class TestApproveCreatesAction:

    def test_approve_creates_approval_action_row(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).approve(
            request_id=req.id, approver_user_id=approver.id
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        assert len(actions) == 1

    def test_approve_action_has_correct_fields(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).approve(
            request_id=req.id, approver_user_id=approver.id, comment="Looks good"
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        a = actions[0]
        assert a.stage_index == 1
        assert a.actor_user_id == approver.id
        assert a.action_type == "approve"
        assert a.comment == "Looks good"
        assert a.approval_request_id == req.id

    def test_approve_action_default_visibility_is_true(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).approve(
            request_id=req.id, approver_user_id=approver.id
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        assert actions[0].is_visible_to_requestor is True

    def test_approve_action_custom_visibility_false(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).approve(
            request_id=req.id,
            approver_user_id=approver.id,
            is_visible_to_requestor=False,
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        assert actions[0].is_visible_to_requestor is False

    def test_approve_action_with_visible_to_lower_user_ids(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        lower_user_id = uuid4()
        ApprovalRequestService(db_session).approve(
            request_id=req.id,
            approver_user_id=approver.id,
            visible_to_lower_user_ids=[lower_user_id],
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        assert actions[0].visible_to_lower_user_ids_json == [str(lower_user_id)]


# ── Group B: ApprovalAction created on reject ─────────────────────────────────


class TestRejectCreatesAction:

    def test_reject_creates_approval_action_row(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).reject(
            request_id=req.id, approver_user_id=approver.id, comment="Not suitable"
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        assert len(actions) == 1

    def test_reject_action_has_correct_fields(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).reject(
            request_id=req.id, approver_user_id=approver.id, comment="Incomplete docs"
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        a = actions[0]
        assert a.action_type == "reject"
        assert a.comment == "Incomplete docs"
        assert a.actor_user_id == approver.id
        assert a.stage_index == 1

    def test_reject_action_default_visibility_is_true(self, db_session: Session) -> None:
        _, approver, _, req = _setup_approve_pair(db_session)
        ApprovalRequestService(db_session).reject(
            request_id=req.id, approver_user_id=approver.id, comment="Not approved"
        )
        actions = ApprovalActionRepository(db_session).list_by_request_id(req.id)
        assert actions[0].is_visible_to_requestor is True


# ── Group C: list_actions_for_requestor ───────────────────────────────────────


class TestListActionsForRequestor:

    def _make_req(self, session: Session) -> ApprovalRequest:
        requestor = _make_user(session)
        role_code = f"A7R_{uuid4().hex[:8]}"
        proc = _make_process(session, role_code)
        return _make_request(session, proc, requestor)

    def test_list_actions_for_requestor_returns_visible_action(self, db_session: Session) -> None:
        req = self._make_req(db_session)
        actor = _make_user(db_session)
        _make_action(db_session, req.id, actor.id, is_visible_to_requestor=True)
        actions = ApprovalRequestService(db_session).list_actions_for_requestor(req.id)
        assert len(actions) == 1

    def test_list_actions_for_requestor_excludes_invisible_action(self, db_session: Session) -> None:
        req = self._make_req(db_session)
        actor = _make_user(db_session)
        _make_action(db_session, req.id, actor.id, is_visible_to_requestor=False)
        actions = ApprovalRequestService(db_session).list_actions_for_requestor(req.id)
        assert actions == []

    def test_list_actions_for_requestor_empty_when_no_actions(self, db_session: Session) -> None:
        req = self._make_req(db_session)
        actions = ApprovalRequestService(db_session).list_actions_for_requestor(req.id)
        assert actions == []

    def test_list_actions_for_requestor_filters_correctly_when_mixed(self, db_session: Session) -> None:
        req = self._make_req(db_session)
        actor1 = _make_user(db_session)
        actor2 = _make_user(db_session)
        _make_action(db_session, req.id, actor1.id, stage_index=1, is_visible_to_requestor=True)
        _make_action(db_session, req.id, actor2.id, stage_index=2, is_visible_to_requestor=False)
        actions = ApprovalRequestService(db_session).list_actions_for_requestor(req.id)
        assert len(actions) == 1
        assert actions[0].actor_user_id == actor1.id


# ── Group D: list_actions_for_approver ────────────────────────────────────────


class TestListActionsForApprover:

    def _make_req(self, session: Session) -> ApprovalRequest:
        requestor = _make_user(session)
        role_code = f"A7A_{uuid4().hex[:8]}"
        proc = _make_process(session, role_code)
        return _make_request(session, proc, requestor)

    def test_list_actions_for_approver_own_action_always_visible(self, db_session: Session) -> None:
        """Own action at a higher stage is visible regardless of visibility flags."""
        req = self._make_req(db_session)
        own_actor = _make_user(db_session)
        # Action at stage 2, invisible to requestor, no lower-user grant
        _make_action(
            db_session, req.id, own_actor.id,
            stage_index=2, is_visible_to_requestor=False,
        )
        # approver_stage=1 means stage 2 > approver_stage → normally hidden, but own-action bypass
        actions = ApprovalRequestService(db_session).list_actions_for_approver(
            req.id, own_actor.id, approver_stage=1
        )
        assert len(actions) == 1

    def test_list_actions_for_approver_lower_stage_visible(self, db_session: Session) -> None:
        """Stage 1 action is visible to a stage-2 approver (hierarchical visibility)."""
        req = self._make_req(db_session)
        stage1_actor = _make_user(db_session)
        stage2_approver = _make_user(db_session)
        _make_action(db_session, req.id, stage1_actor.id, stage_index=1)
        actions = ApprovalRequestService(db_session).list_actions_for_approver(
            req.id, stage2_approver.id, approver_stage=2
        )
        assert len(actions) == 1
        assert actions[0].actor_user_id == stage1_actor.id

    def test_list_actions_for_approver_same_stage_visible(self, db_session: Session) -> None:
        """Stage N action is visible to a stage-N approver (stage ≤ approver_stage)."""
        req = self._make_req(db_session)
        actor = _make_user(db_session)
        other_approver = _make_user(db_session)
        _make_action(db_session, req.id, actor.id, stage_index=2)
        actions = ApprovalRequestService(db_session).list_actions_for_approver(
            req.id, other_approver.id, approver_stage=2
        )
        assert len(actions) == 1

    def test_list_actions_for_approver_higher_stage_excluded_by_default(self, db_session: Session) -> None:
        """Stage 2 action is NOT visible to a stage-1 approver without explicit grant."""
        req = self._make_req(db_session)
        stage2_actor = _make_user(db_session)
        stage1_approver = _make_user(db_session)
        _make_action(db_session, req.id, stage2_actor.id, stage_index=2)
        actions = ApprovalRequestService(db_session).list_actions_for_approver(
            req.id, stage1_approver.id, approver_stage=1
        )
        assert actions == []

    def test_list_actions_for_approver_higher_stage_visible_when_granted(self, db_session: Session) -> None:
        """Stage 2 action IS visible to stage-1 approver when their ID is in visible_to_lower_user_ids_json."""
        req = self._make_req(db_session)
        stage2_actor = _make_user(db_session)
        stage1_approver = _make_user(db_session)
        _make_action(
            db_session, req.id, stage2_actor.id,
            stage_index=2,
            visible_to_lower_user_ids_json=[str(stage1_approver.id)],
        )
        actions = ApprovalRequestService(db_session).list_actions_for_approver(
            req.id, stage1_approver.id, approver_stage=1
        )
        assert len(actions) == 1
        assert actions[0].actor_user_id == stage2_actor.id

    def test_list_actions_for_approver_returns_empty_for_no_actions(self, db_session: Session) -> None:
        req = self._make_req(db_session)
        approver = _make_user(db_session)
        actions = ApprovalRequestService(db_session).list_actions_for_approver(
            req.id, approver.id, approver_stage=1
        )
        assert actions == []
