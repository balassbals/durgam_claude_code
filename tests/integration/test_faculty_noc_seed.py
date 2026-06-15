"""Integration tests for faculty_noc ApprovalProcess seed (M10 Phase 5B).

READ-ONLY on seeded_session — no inserts, updates, or deletes on seeded rows.
The idempotency test calls _seed_faculty_noc_process() which issues on_conflict_do_nothing
inserts; no existing rows are mutated. seeded_session rolls back on teardown.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalProcess, ApprovalStageOption


class TestFacultyNocSeed:
    def test_faculty_noc_process_seeded(self, seeded_session: Session) -> None:
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == "faculty_noc",
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()

        assert process is not None, "faculty_noc process must be seeded"
        assert process.title == "Faculty No Objection Certificate"
        assert process.requestor_role_codes == ["FACULTY"]
        assert process.channel_role_codes == ["HOD", "REGISTRAR"]
        assert process.stage_pick_modes_json == {"1": "approver"}
        assert not process.is_finance

    def test_faculty_noc_stage1_option_seeded(self, seeded_session: Session) -> None:
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == "faculty_noc",
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert process is not None

        option = seeded_session.exec(
            select(ApprovalStageOption).where(
                ApprovalStageOption.approval_process_id == process.id,
                ApprovalStageOption.stage_index == 1,
                ApprovalStageOption.is_deleted == False,  # noqa: E712
            )
        ).first()

        assert option is not None, "Stage 1 ApprovalStageOption must be seeded"
        assert option.resolver_name == "dept_head_at_requestor_campus"
        assert option.label == "Head of Department"
        assert option.sort_order == 0

    def test_faculty_noc_seed_idempotent(self, seeded_session: Session) -> None:
        from scripts.seed import _seed_faculty_noc_process

        # Process and option already seeded; second call must be a no-op
        _seed_faculty_noc_process(seeded_session)
        seeded_session.flush()

        processes = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == "faculty_noc",
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).all()
        assert len(processes) == 1, "Idempotent: must not create duplicate processes"
