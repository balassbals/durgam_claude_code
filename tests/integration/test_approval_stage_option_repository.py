"""Integration tests for ApprovalStageOptionRepository — M10 Phase 3A.

Uses db_session (function-scoped, rolls back) and synthetic ApprovalProcess
fixtures to avoid dependency on seeded data.  No existing tests are touched.
"""

from datetime import datetime, UTC
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.crosscutting import ApprovalProcess
from durgam.repositories.approval_stage_option import ApprovalStageOptionRepository


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _process(session: Session) -> ApprovalProcess:
    """Create a minimal ApprovalProcess for FK purposes."""
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


# ── Tests ────────────────────────────────────────────────────────────────────


class TestApprovalStageOptionRepository:
    def test_create_and_get(self, db_session):
        """create() persists a row; get() retrieves it by id."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)

        opt = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="dept_head_at_requestor_campus",
            label="HoD at requestor's campus",
            sort_order=0,
        )

        fetched = repo.get(opt.id)
        assert fetched is not None
        assert fetched.id == opt.id
        assert fetched.resolver_name == "dept_head_at_requestor_campus"
        assert fetched.stage_index == 1

    def test_list_by_process_stage_returns_options_in_sort_order(self, db_session):
        """list_by_process_stage returns options ordered by sort_order."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)

        opt_b = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_b",
            label="B",
            sort_order=10,
        )
        opt_a = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_a",
            label="A",
            sort_order=5,
        )

        opts = repo.list_by_process_stage(p.id, stage_index=1)
        assert [o.id for o in opts] == [opt_a.id, opt_b.id]

    def test_list_by_process_stage_excludes_soft_deleted(self, db_session):
        """Soft-deleted options are not returned by list_by_process_stage."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)

        active = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_active",
            label="Active",
        )
        deleted = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_deleted",
            label="Deleted",
        )
        repo.soft_delete(deleted.id)

        opts = repo.list_by_process_stage(p.id, stage_index=1)
        ids = [o.id for o in opts]
        assert active.id in ids
        assert deleted.id not in ids

    def test_list_by_process_stage_filters_by_stage_index(self, db_session):
        """Options for stage 2 are not returned when querying stage 1."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)

        stage1_opt = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_for_stage1",
            label="Stage 1",
        )
        repo.create(
            approval_process_id=p.id,
            stage_index=2,
            resolver_name="resolver_for_stage2",
            label="Stage 2",
        )

        opts = repo.list_by_process_stage(p.id, stage_index=1)
        assert len(opts) == 1
        assert opts[0].id == stage1_opt.id

    def test_update_changes_label_and_sort_order(self, db_session):
        """update() persists label and sort_order changes."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)

        opt = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_x",
            label="Old Label",
            sort_order=0,
        )

        updated = repo.update(opt.id, label="New Label", sort_order=99)

        assert updated.label == "New Label"
        assert updated.sort_order == 99

    def test_get_returns_none_for_soft_deleted(self, db_session):
        """get() returns None for a soft-deleted option."""
        p = _process(db_session)
        repo = ApprovalStageOptionRepository(db_session)

        opt = repo.create(
            approval_process_id=p.id,
            stage_index=1,
            resolver_name="resolver_gone",
            label="Gone",
        )
        repo.soft_delete(opt.id)

        assert repo.get(opt.id) is None
