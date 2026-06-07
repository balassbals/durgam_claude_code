"""Unit tests for approval routing — scope chain and stage approver resolution."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.services.approval_routing import (
    ApprovalRoutingError,
    get_requestor_scope_chain,
    resolve_stage_approvers,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _mock_session_with_user_roles(user_roles, departments=None):
    """Build a mock session that returns user_roles from select(UserRole)
    and optional Department lookups via session.get."""
    session = MagicMock()
    departments = departments or {}

    def exec_side_effect(stmt):
        result = MagicMock()
        result.all.return_value = user_roles
        result.first.return_value = user_roles[0] if user_roles else None
        return result

    session.exec.side_effect = exec_side_effect

    def get_side_effect(model, pk):
        if model.__name__ == "Department":
            return departments.get(pk)
        return None

    session.get.side_effect = get_side_effect
    return session


def _make_user_role(scope_type=None, scope_id=None, role_id=None):
    ur = MagicMock()
    ur.scope_type = scope_type
    ur.scope_id = scope_id
    ur.role_id = role_id or uuid4()
    ur.user_id = uuid4()
    return ur


def _make_department(dept_id, school_id, campus_id):
    dept = MagicMock()
    dept.id = dept_id
    dept.school_id = school_id
    dept.main_campus_id = campus_id
    dept.is_deleted = False
    return dept


def _make_request(current_stage=1, requestor_user_id=None):
    req = MagicMock()
    req.id = uuid4()
    req.current_stage = current_stage
    req.requestor_user_id = requestor_user_id or uuid4()
    return req


def _make_process(channel_role_codes=None):
    proc = MagicMock()
    proc.channel_role_codes = channel_role_codes or []
    return proc


# ── Scope chain tests ──────────────────────────────────────────────────


class TestGetRequestorScopeChain:
    def test_scope_chain_includes_dept_then_school_then_campus_then_universitywide(
        self,
    ):
        dept_id = uuid4()
        school_id = uuid4()
        campus_id = uuid4()

        ur = _make_user_role(scope_type="department", scope_id=dept_id)
        dept = _make_department(dept_id, school_id, campus_id)

        session = _mock_session_with_user_roles([ur], {dept_id: dept})

        chain = get_requestor_scope_chain(ur.user_id, session)

        types_in_order = [t for t, _ in chain]
        assert types_in_order.index("department") < types_in_order.index("school")
        assert types_in_order.index("school") < types_in_order.index("campus")
        assert types_in_order.index("campus") < types_in_order.index(None)

        assert ("department", dept_id) in chain
        assert ("school", school_id) in chain
        assert ("campus", campus_id) in chain
        assert (None, None) in chain

    def test_universitywide_only_when_no_scoped_roles(self):
        ur = _make_user_role(scope_type=None, scope_id=None)
        session = _mock_session_with_user_roles([ur])

        chain = get_requestor_scope_chain(ur.user_id, session)

        assert chain == [(None, None)]

    def test_school_scoped_role_included(self):
        school_id = uuid4()
        ur = _make_user_role(scope_type="school", scope_id=school_id)
        session = _mock_session_with_user_roles([ur])

        chain = get_requestor_scope_chain(ur.user_id, session)

        assert ("school", school_id) in chain
        assert (None, None) in chain


# ── Resolve stage approvers tests ──────────────────────────────────────


class TestResolveStageApprovers:
    @patch("durgam.services.approval_routing.get_requestor_scope_chain")
    def test_returns_dept_match_first(self, mock_chain):
        dept_id = uuid4()
        school_id = uuid4()
        mock_chain.return_value = [
            ("department", dept_id),
            ("school", school_id),
            (None, None),
        ]

        role_id = uuid4()
        hod_user_id = uuid4()

        role_mock = MagicMock()
        role_mock.id = role_id
        role_mock.code = "HOD"
        role_mock.is_deleted = False

        holder = MagicMock()
        holder.user_id = hod_user_id
        holder.role_id = role_id
        holder.scope_type = "department"
        holder.scope_id = dept_id

        user_mock = MagicMock()
        user_mock.id = hod_user_id
        user_mock.is_deleted = False
        user_mock.is_active = True

        session = MagicMock()
        call_count = {"n": 0}

        def exec_side(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.first.return_value = role_mock
                return result
            elif call_count["n"] == 2:
                result.all.return_value = [holder]
                return result
            else:
                result.first.return_value = user_mock
                return result

        session.exec.side_effect = exec_side

        req = _make_request()
        proc = _make_process(["HOD"])

        users = resolve_stage_approvers(request=req, process=proc, session=session)

        assert len(users) == 1
        assert users[0].id == hod_user_id

    @patch("durgam.services.approval_routing.get_requestor_scope_chain")
    def test_falls_back_to_school(self, mock_chain):
        dept_id = uuid4()
        school_id = uuid4()
        mock_chain.return_value = [
            ("department", dept_id),
            ("school", school_id),
            (None, None),
        ]

        role_id = uuid4()
        dean_user_id = uuid4()

        role_mock = MagicMock()
        role_mock.id = role_id
        role_mock.code = "DEAN"
        role_mock.is_deleted = False

        school_holder = MagicMock()
        school_holder.user_id = dean_user_id
        school_holder.role_id = role_id
        school_holder.scope_type = "school"
        school_holder.scope_id = school_id

        user_mock = MagicMock()
        user_mock.id = dean_user_id
        user_mock.is_deleted = False
        user_mock.is_active = True

        session = MagicMock()
        call_count = {"n": 0}

        def exec_side(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.first.return_value = role_mock
                return result
            elif call_count["n"] == 2:
                result.all.return_value = []
                return result
            elif call_count["n"] == 3:
                result.all.return_value = [school_holder]
                return result
            else:
                result.first.return_value = user_mock
                return result

        session.exec.side_effect = exec_side

        req = _make_request()
        proc = _make_process(["DEAN"])

        users = resolve_stage_approvers(request=req, process=proc, session=session)

        assert len(users) == 1
        assert users[0].id == dean_user_id

    @patch("durgam.services.approval_routing.get_requestor_scope_chain")
    def test_falls_back_to_universitywide(self, mock_chain):
        dept_id = uuid4()
        mock_chain.return_value = [
            ("department", dept_id),
            (None, None),
        ]

        role_id = uuid4()
        registrar_user_id = uuid4()

        role_mock = MagicMock()
        role_mock.id = role_id
        role_mock.code = "REGISTRAR"
        role_mock.is_deleted = False

        holder = MagicMock()
        holder.user_id = registrar_user_id
        holder.role_id = role_id
        holder.scope_type = None
        holder.scope_id = None

        user_mock = MagicMock()
        user_mock.id = registrar_user_id
        user_mock.is_deleted = False
        user_mock.is_active = True

        session = MagicMock()
        call_count = {"n": 0}

        def exec_side(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.first.return_value = role_mock
                return result
            elif call_count["n"] == 2:
                result.all.return_value = []
                return result
            elif call_count["n"] == 3:
                result.all.return_value = [holder]
                return result
            else:
                result.first.return_value = user_mock
                return result

        session.exec.side_effect = exec_side

        req = _make_request()
        proc = _make_process(["REGISTRAR"])

        users = resolve_stage_approvers(request=req, process=proc, session=session)

        assert len(users) == 1
        assert users[0].id == registrar_user_id

    @patch("durgam.services.approval_routing.get_requestor_scope_chain")
    def test_returns_empty_when_no_holder(self, mock_chain):
        mock_chain.return_value = [(None, None)]

        role_mock = MagicMock()
        role_mock.id = uuid4()
        role_mock.code = "GHOST_ROLE"
        role_mock.is_deleted = False

        session = MagicMock()
        call_count = {"n": 0}

        def exec_side(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.first.return_value = role_mock
                return result
            else:
                result.all.return_value = []
                return result

        session.exec.side_effect = exec_side

        req = _make_request()
        proc = _make_process(["GHOST_ROLE"])

        users = resolve_stage_approvers(request=req, process=proc, session=session)
        assert users == []

    def test_raises_on_stage_out_of_bounds(self):
        session = MagicMock()
        req = _make_request(current_stage=3)
        proc = _make_process(["HOD", "DEAN"])

        with pytest.raises(ApprovalRoutingError, match="out of bounds"):
            resolve_stage_approvers(request=req, process=proc, session=session)

    def test_raises_on_empty_channel(self):
        session = MagicMock()
        req = _make_request(current_stage=1)
        proc = _make_process([])

        with pytest.raises(ApprovalRoutingError, match="out of bounds"):
            resolve_stage_approvers(request=req, process=proc, session=session)
