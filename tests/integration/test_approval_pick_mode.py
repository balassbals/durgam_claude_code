"""Integration tests for get_stage_pick_mode helper — M10 Phase 3B.

Uses db_session (function-scoped, rolls back) and synthetic ApprovalProcess fixtures.
No existing approval processes are modified.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.crosscutting import ApprovalProcess
from durgam.services.approval_engine import get_stage_pick_mode


def _process(session: Session, *, stage_pick_modes_json=None) -> ApprovalProcess:
    """Create a minimal ApprovalProcess with optional stage_pick_modes_json."""
    p = ApprovalProcess(
        id=uuid4(),
        code=f"TST_{uuid4().hex[:6]}",
        title="Pick-mode Test Process",
        stage_pick_modes_json=stage_pick_modes_json,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p


class TestGetStagePickMode:
    def test_returns_approver_for_indexed_stage(self, db_session):
        """stage_pick_modes_json has stage 1 = 'approver' → returns 'approver'."""
        p = _process(db_session, stage_pick_modes_json={"1": "approver", "2": "requestor"})

        result = get_stage_pick_mode(db_session, p.id, stage_index=1)

        assert result == "approver"

    def test_returns_requestor_for_indexed_stage(self, db_session):
        """stage_pick_modes_json has stage 2 = 'requestor' → returns 'requestor'."""
        p = _process(db_session, stage_pick_modes_json={"1": "approver", "2": "requestor"})

        result = get_stage_pick_mode(db_session, p.id, stage_index=2)

        assert result == "requestor"

    def test_returns_none_for_missing_stage_index(self, db_session):
        """stage_pick_modes_json defined but stage 99 absent → returns None."""
        p = _process(db_session, stage_pick_modes_json={"1": "approver", "2": "requestor"})

        result = get_stage_pick_mode(db_session, p.id, stage_index=99)

        assert result is None

    def test_returns_none_when_json_is_null(self, db_session):
        """stage_pick_modes_json is NULL → returns None (legacy stage)."""
        p = _process(db_session, stage_pick_modes_json=None)

        result = get_stage_pick_mode(db_session, p.id, stage_index=1)

        assert result is None

    def test_returns_none_for_invalid_value(self, db_session):
        """stage_pick_modes_json has invalid value 'garbage' → returns None."""
        p = _process(db_session, stage_pick_modes_json={"1": "garbage"})

        result = get_stage_pick_mode(db_session, p.id, stage_index=1)

        assert result is None
