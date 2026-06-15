"""Integration tests for resolve_stage_candidates engine helper — M10 Phase 3A.

Uses db_session (function-scoped, rolls back) and synthetic fixtures.
Tests verify the OR-set engine helper in isolation; no existing approval
processes are modified (STEP-A discipline).
"""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.crosscutting import ApprovalProcess
from durgam.models.identity import User
from durgam.repositories.approval_stage_option import ApprovalStageOptionRepository
from durgam.services.approval_engine import EngineError, resolve_stage_candidates
from durgam.services.approval_resolvers import RESOLVERS, ResolverContext


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _process(session: Session) -> ApprovalProcess:
    p = ApprovalProcess(
        id=uuid4(),
        code=f"TST_{uuid4().hex[:6]}",
        title="Test Process",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p


def _ctx(process_id, stage_index=1) -> ResolverContext:
    return ResolverContext(
        requestor_user_id=uuid4(),
        process_id=process_id,
        stage_index=stage_index,
    )


def _fake_user() -> User:
    u = User(
        id=uuid4(),
        username=f"eng_{uuid4().hex[:6]}",
        email=f"eng_{uuid4().hex[:6]}@test.com",
        full_name="Engine Test",
        password_hash="x",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return u


# ── Tests ────────────────────────────────────────────────────────────────────


class TestResolveStageCandidates:
    def test_no_options_returns_empty_list(self, db_session):
        """No ApprovalStageOption rows → empty list (caller falls back to legacy path)."""
        p = _process(db_session)
        ctx = _ctx(p.id)

        result = resolve_stage_candidates(db_session, p.id, stage_index=1, ctx=ctx)

        assert result == []

    def test_one_option_dispatches_to_resolver(self, db_session):
        """One option row → dispatches to resolver and returns its users."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)
        repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="_test_eng_resolver",
            label="Test resolver",
        )

        user = _fake_user()
        fake_fn = lambda ctx, session: [user]

        with patch.dict(RESOLVERS, {"_test_eng_resolver": fake_fn}):
            ctx = _ctx(p.id)
            result = resolve_stage_candidates(db_session, p.id, stage_index=1, ctx=ctx)

        assert len(result) == 1
        assert result[0].id == user.id

    def test_two_options_returns_union_of_users(self, db_session):
        """Two option rows → union of both resolvers' results."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)
        repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="_test_eng_a",
            label="A",
            sort_order=0,
        )
        repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="_test_eng_b",
            label="B",
            sort_order=1,
        )

        user_a = _fake_user()
        user_b = _fake_user()
        fake_a = lambda ctx, session: [user_a]
        fake_b = lambda ctx, session: [user_b]

        with patch.dict(RESOLVERS, {"_test_eng_a": fake_a, "_test_eng_b": fake_b}):
            ctx = _ctx(p.id)
            result = resolve_stage_candidates(db_session, p.id, stage_index=1, ctx=ctx)

        result_ids = {u.id for u in result}
        assert user_a.id in result_ids
        assert user_b.id in result_ids

    def test_duplicate_user_from_two_resolvers_deduplicated(self, db_session):
        """Same user returned by two resolvers appears only once in result."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)
        repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="_test_dup_a",
            label="A",
        )
        repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="_test_dup_b",
            label="B",
        )

        shared_user = _fake_user()
        fake_a = lambda ctx, session: [shared_user]
        fake_b = lambda ctx, session: [shared_user]

        with patch.dict(RESOLVERS, {"_test_dup_a": fake_a, "_test_dup_b": fake_b}):
            ctx = _ctx(p.id)
            result = resolve_stage_candidates(db_session, p.id, stage_index=1, ctx=ctx)

        assert len(result) == 1
        assert result[0].id == shared_user.id

    def test_unknown_resolver_name_raises_engine_error(self, db_session):
        """Unknown resolver_name in option row → EngineError (not UnknownResolverError)."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)
        repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="definitely_not_registered",
            label="Bad",
        )

        ctx = _ctx(p.id)
        with pytest.raises(EngineError, match="not found"):
            resolve_stage_candidates(db_session, p.id, stage_index=1, ctx=ctx)

    def test_options_for_different_stage_not_returned(self, db_session):
        """Options seeded for stage 2 are not included when querying stage 1."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)
        repo.create(
            approval_process_id=p.id,
            stage_index=2,
            resolver_name="_test_stage2_resolver",
            label="Stage 2 only",
        )

        user = _fake_user()
        fake_fn = lambda ctx, session: [user]

        with patch.dict(RESOLVERS, {"_test_stage2_resolver": fake_fn}):
            ctx = _ctx(p.id, stage_index=1)
            result = resolve_stage_candidates(db_session, p.id, stage_index=1, ctx=ctx)

        # Stage 1 has no options → empty fallback signal
        assert result == []
