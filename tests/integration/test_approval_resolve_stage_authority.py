"""Integration tests for resolve_stage_authority — M10 Phase 4 (STEP-A).

Uses db_session (function-scoped, rolls back) + synthetic ApprovalProcess and
ApprovalStageOption fixtures.  Resolvers injected via monkeypatch.setitem so
no real DB queries are needed inside the test resolver functions.

No existing tests, migrations, schema, or seed data are touched.
"""

from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.crosscutting import ApprovalProcess, ApprovalStageOption
from durgam.models.identity import User
from durgam.services.approval_engine import (
    MisconfiguredStageError,
    StageOptionMismatchError,
    resolve_stage_authority,
)
from durgam.services.approval_resolvers import RESOLVERS, ResolverContext, UnknownResolverError


# ── Synthetic fixture helpers ────────────────────────────────────────────────


def _make_process(session: Session, pick_modes: dict | None = None) -> ApprovalProcess:
    """Create a minimal synthetic ApprovalProcess."""
    p = ApprovalProcess(
        id=uuid4(),
        code=f"TEST-PROC-{uuid4().hex[:6]}",
        title="Test Process",
        stage_pick_modes_json=pick_modes,
    )
    session.add(p)
    session.flush()
    return p


def _make_option(
    session: Session,
    process_id,
    stage_index: int,
    resolver_name: str,
    sort_order: int = 0,
) -> ApprovalStageOption:
    opt = ApprovalStageOption(
        id=uuid4(),
        approval_process_id=process_id,
        stage_index=stage_index,
        resolver_name=resolver_name,
        label=f"opt-{resolver_name}",
        sort_order=sort_order,
    )
    session.add(opt)
    session.flush()
    return opt


def _fake_user() -> User:
    """Unsaved User object used as resolver return value — never inserted into DB."""
    return User(
        id=uuid4(),
        username=f"u{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@dev.local",
        password_hash="x",
        is_active=True,
    )


def _ctx() -> ResolverContext:
    return ResolverContext(
        requestor_user_id=uuid4(),
        process_id=uuid4(),
        stage_index=1,
    )


# ── Tests ────────────────────────────────────────────────────────────────────


class TestResolveStageAuthority:
    def test_no_options_returns_legacy(self, db_session):
        """Stage with no ApprovalStageOption rows → ('legacy', [])."""
        p = _make_process(db_session, pick_modes=None)

        status, users = resolve_stage_authority(db_session, p.id, stage_index=1, ctx=_ctx())

        assert status == "legacy"
        assert users == []

    def test_approver_pool_returns_union_with_dedup(self, db_session, monkeypatch):
        """pick_mode='approver' → union of all resolvers' users, deduplicated."""
        p = _make_process(db_session, pick_modes={"1": "approver"})
        _make_option(db_session, p.id, stage_index=1, resolver_name="_p4_res_a", sort_order=0)
        _make_option(db_session, p.id, stage_index=1, resolver_name="_p4_res_b", sort_order=1)

        user_a = _fake_user()
        shared = _fake_user()
        user_b = _fake_user()

        monkeypatch.setitem(RESOLVERS, "_p4_res_a", lambda ctx, s: [user_a, shared])
        monkeypatch.setitem(RESOLVERS, "_p4_res_b", lambda ctx, s: [shared, user_b])

        status, users = resolve_stage_authority(db_session, p.id, stage_index=1, ctx=_ctx())

        assert status == "approver_pool"
        result_ids = [u.id for u in users]
        assert user_a.id in result_ids
        assert shared.id in result_ids
        assert user_b.id in result_ids
        assert len(result_ids) == 3  # shared deduplicated

    def test_requestor_pick_with_valid_option_returns_option_candidates(
        self, db_session, monkeypatch
    ):
        """pick_mode='requestor' + valid option_id → ('requestor_pick', [that option's users])."""
        p = _make_process(db_session, pick_modes={"1": "requestor"})
        opt = _make_option(db_session, p.id, stage_index=1, resolver_name="_p4_picked")

        user = _fake_user()
        monkeypatch.setitem(RESOLVERS, "_p4_picked", lambda ctx, s: [user])

        status, users = resolve_stage_authority(
            db_session, p.id, stage_index=1, ctx=_ctx(),
            requestor_picked_option_id=opt.id,
        )

        assert status == "requestor_pick"
        assert len(users) == 1
        assert users[0].id == user.id

    def test_requestor_pick_without_option_returns_pending(self, db_session):
        """pick_mode='requestor' + no option_id → ('pending_pick', [])."""
        p = _make_process(db_session, pick_modes={"1": "requestor"})
        _make_option(db_session, p.id, stage_index=1, resolver_name="any_resolver")

        status, users = resolve_stage_authority(
            db_session, p.id, stage_index=1, ctx=_ctx(),
            requestor_picked_option_id=None,
        )

        assert status == "pending_pick"
        assert users == []

    def test_requestor_pick_with_invalid_option_raises_stage_mismatch(self, db_session):
        """option_id from a different stage → StageOptionMismatchError."""
        p = _make_process(db_session, pick_modes={"1": "requestor", "2": "requestor"})
        # stage 1 option (the one we'll query)
        _make_option(db_session, p.id, stage_index=1, resolver_name="stage1_res")
        # stage 2 option — wrong for stage 1 query
        wrong_opt = _make_option(db_session, p.id, stage_index=2, resolver_name="stage2_res")

        with pytest.raises(StageOptionMismatchError, match="does not belong"):
            resolve_stage_authority(
                db_session, p.id, stage_index=1, ctx=_ctx(),
                requestor_picked_option_id=wrong_opt.id,
            )

    def test_options_without_pick_mode_raises_misconfigured(self, db_session):
        """Options exist but stage_pick_modes_json is NULL → MisconfiguredStageError."""
        p = _make_process(db_session, pick_modes=None)
        _make_option(db_session, p.id, stage_index=1, resolver_name="any_resolver")

        with pytest.raises(MisconfiguredStageError, match="no pick_mode"):
            resolve_stage_authority(db_session, p.id, stage_index=1, ctx=_ctx())

    def test_options_with_invalid_pick_mode_value_raises_misconfigured(self, db_session):
        """Options exist but pick_mode is 'garbage' (not approver/requestor) → MisconfiguredStageError."""
        p = _make_process(db_session, pick_modes={"1": "garbage"})
        _make_option(db_session, p.id, stage_index=1, resolver_name="any_resolver")

        with pytest.raises(MisconfiguredStageError, match="no pick_mode"):
            resolve_stage_authority(db_session, p.id, stage_index=1, ctx=_ctx())

    def test_picked_option_with_unknown_resolver_raises(self, db_session):
        """Requestor picks an option whose resolver_name is not in RESOLVERS → UnknownResolverError."""
        p = _make_process(db_session, pick_modes={"1": "requestor"})
        opt = _make_option(
            db_session, p.id, stage_index=1,
            resolver_name="definitely_not_registered_p4",
        )

        with pytest.raises(UnknownResolverError, match="not in RESOLVERS"):
            resolve_stage_authority(
                db_session, p.id, stage_index=1, ctx=_ctx(),
                requestor_picked_option_id=opt.id,
            )
