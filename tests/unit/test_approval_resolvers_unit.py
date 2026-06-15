"""Unit tests for approval_resolvers — M10 Phase 3A (mock session, no DB).

Tests dispatch logic, UnknownResolverError, and the
dept_head_at_requestor_campus resolver edge cases via mocked session.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.services.approval_resolvers import (
    RESOLVERS,
    ResolverContext,
    UnknownResolverError,
    _resolve_dept_head_at_requestor_campus,
    resolve,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _ctx(requestor_user_id=None) -> ResolverContext:
    return ResolverContext(
        requestor_user_id=requestor_user_id or uuid4(),
        process_id=uuid4(),
        stage_index=1,
    )


def _seq_session(*results):
    """Build a mock session whose exec() calls return results in sequence.

    Each element of *results is a (all_value, first_value) pair.
    The first call returns results[0], the second results[1], etc.
    """
    session = MagicMock()
    call_idx = [0]

    def exec_side(stmt):
        n = call_idx[0]
        call_idx[0] += 1
        mock_result = MagicMock()
        if n < len(results):
            all_val, first_val = results[n]
            mock_result.all.return_value = all_val
            mock_result.first.return_value = first_val
        else:
            mock_result.all.return_value = []
            mock_result.first.return_value = None
        return mock_result

    session.exec.side_effect = exec_side
    return session


def _make_ur(scope_type=None, scope_id=None, role_id=None, user_id=None):
    ur = MagicMock()
    ur.scope_type = scope_type
    ur.scope_id = scope_id
    ur.role_id = role_id or uuid4()
    ur.user_id = user_id or uuid4()
    return ur


def _make_dept(dept_id, campus_id):
    d = MagicMock()
    d.id = dept_id
    d.main_campus_id = campus_id
    d.is_deleted = False
    return d


def _make_role(role_id=None):
    r = MagicMock()
    r.id = role_id or uuid4()
    return r


def _make_user(user_id=None):
    u = MagicMock()
    u.id = user_id or uuid4()
    return u


# ── Tests: dispatch layer ─────────────────────────────────────────────────────


class TestResolverDispatch:
    def test_resolve_known_name_dispatches(self):
        """resolve() calls the registered function and returns its value."""
        sentinel = [_make_user()]
        fake_fn = MagicMock(return_value=sentinel)
        ctx = _ctx()
        session = MagicMock()

        with patch.dict(RESOLVERS, {"_test_resolver": fake_fn}):
            result = resolve("_test_resolver", ctx, session)

        fake_fn.assert_called_once_with(ctx, session)
        assert result is sentinel

    def test_resolve_unknown_name_raises(self):
        """resolve() raises UnknownResolverError for an unregistered name."""
        with pytest.raises(UnknownResolverError, match="not found"):
            resolve("nonexistent_resolver", _ctx(), MagicMock())

    def test_resolvers_registry_contains_expected_key(self):
        """The registry exposes dept_head_at_requestor_campus."""
        assert "dept_head_at_requestor_campus" in RESOLVERS


# ── Tests: dept_head_at_requestor_campus ─────────────────────────────────────


class TestDeptHeadAtRequestorCampus:
    def test_no_dept_scoped_roles_returns_empty(self):
        """Requestor has no department-scoped roles → empty list, no HOD lookup."""
        # Call 0: user_roles → []
        session = _seq_session(([], None))
        session.get.return_value = None

        result = _resolve_dept_head_at_requestor_campus(_ctx(), session)

        assert result == []

    def test_returns_hod_user_for_matching_campus(self):
        """Requestor's Faculty row exists → returns HoD of requestor's dept+campus."""
        dept_id = uuid4()
        campus_id = uuid4()
        hod_role_id = uuid4()
        hod_user_id = uuid4()

        faculty = MagicMock()
        faculty.department_id = dept_id
        faculty.campus_id = campus_id
        faculty.is_deleted = False

        hod_role = _make_role(role_id=hod_role_id)
        hod_user = _make_user(user_id=hod_user_id)

        session = _seq_session(
            ([], faculty),      # 0: Faculty lookup → .first() = faculty
            ([], hod_role),     # 1: HOD Role lookup → .first() = hod_role
            ([], hod_user),     # 2: User join query → .first() = hod_user
        )

        result = _resolve_dept_head_at_requestor_campus(_ctx(), session)

        assert len(result) == 1
        assert result[0].id == hod_user_id

    def test_hod_role_not_found_returns_empty(self):
        """HOD role absent from DB → empty list even when dept chain resolves."""
        campus_id = uuid4()
        dept_id = uuid4()
        dept = _make_dept(dept_id, campus_id)
        ur_requestor = _make_ur(scope_type="department", scope_id=dept_id)

        session = _seq_session(
            ([ur_requestor], None),     # 0: user_roles
            ([dept], None),             # 1: departments at campus
            ([], None),                 # 2: HOD role → None
        )
        session.get.side_effect = lambda model, pk: dept if pk == dept_id else None

        result = _resolve_dept_head_at_requestor_campus(_ctx(), session)

        assert result == []
