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


# ── Phase 5D: 4 linear faculty processes ────────────────────────────────────


_PHASE_5D_PROCESSES = [
    ("faculty_invited_talk", "Faculty Invited Talk Request"),
    ("faculty_professional_membership", "Faculty Professional Body Membership Request"),
    ("faculty_wfh", "Faculty Work From Home Request"),
    ("faculty_field_visit", "Faculty Field/Industry Visit Request"),
]


class TestPhase5DLinearSeeds:
    @pytest.mark.parametrize("code,title", _PHASE_5D_PROCESSES)
    def test_process_seeded(self, seeded_session: Session, code: str, title: str) -> None:
        """Each Phase 5D process exists with correct metadata."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()

        assert process is not None, f"{code} process must be seeded"
        assert process.title == title
        assert process.requestor_role_codes == ["FACULTY"]
        assert process.channel_role_codes == ["HOD", "DIRECTOR"]
        assert process.stage_pick_modes_json == {"1": "approver"}
        assert not process.is_finance
        assert process.max_upward_attachments == 3
        assert process.allowed_attachment_mime_types_json == ["application/pdf"]
        assert process.max_downward_attachments == 0, "Only faculty_noc has downward attachments"

    @pytest.mark.parametrize("code,_", _PHASE_5D_PROCESSES)
    def test_stage1_option_seeded(self, seeded_session: Session, code: str, _: str) -> None:
        """Each Phase 5D process has exactly one Stage 1 resolver option."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
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

        assert option is not None, f"Stage 1 option must be seeded for {code}"
        assert option.resolver_name == "dept_head_at_requestor_campus"
        assert option.label == "Head of Department"
        assert option.sort_order == 0

    def test_phase5d_seeds_idempotent(self, seeded_session: Session) -> None:
        """Calling _seed_faculty_simple_linear_process on already-seeded data returns 0."""
        from scripts.seed import _seed_faculty_simple_linear_process

        for code, title in _PHASE_5D_PROCESSES:
            result = _seed_faculty_simple_linear_process(
                seeded_session,
                code=code,
                title=title,
                channel_role_codes=["HOD", "DIRECTOR"],
            )
            seeded_session.flush()
            assert result == 0, f"Second seed call for {code} must be idempotent (got {result})"

            count = len(seeded_session.exec(
                select(ApprovalProcess).where(
                    ApprovalProcess.code == code,
                    ApprovalProcess.is_deleted == False,  # noqa: E712
                )
            ).all())
            assert count == 1, f"Idempotent: must not create duplicate process for {code}"


# ── Phase 5E: 3 terminal-variant faculty processes ───────────────────────────


_PHASE_5E_PROCESSES = [
    ("faculty_apc", "Faculty Article Processing Charge Request", ["HOD", "FINANCE_OFFICER", "VC"]),
    ("faculty_travel", "Faculty Travel Request", ["HOD", "DIRECTOR", "VC"]),
    (
        "faculty_external_grant_proposal",
        "Faculty External Grant Proposal Submission Request",
        ["HOD", "REGISTRAR"],
    ),
]


class TestPhase5ETerminalSeeds:
    @pytest.mark.parametrize("code,title,channel", _PHASE_5E_PROCESSES)
    def test_process_seeded(self, seeded_session: Session, code: str, title: str, channel: list) -> None:
        """Each Phase 5E process exists with correct metadata."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()

        assert process is not None, f"{code} process must be seeded"
        assert process.title == title
        assert process.requestor_role_codes == ["FACULTY"]
        assert process.channel_role_codes == channel
        assert process.stage_pick_modes_json == {"1": "approver"}
        assert not process.is_finance
        assert process.max_upward_attachments == 3
        assert process.allowed_attachment_mime_types_json == ["application/pdf"]
        assert process.max_downward_attachments == 0

    @pytest.mark.parametrize("code,_,channel", _PHASE_5E_PROCESSES)
    def test_channel_length(self, seeded_session: Session, code: str, _: str, channel: list) -> None:
        """faculty_apc and faculty_travel have 3-item channel; external_grant has 2."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert process is not None
        assert len(process.channel_role_codes) == len(channel)

    @pytest.mark.parametrize("code,_,__", _PHASE_5E_PROCESSES)
    def test_stage1_option_seeded(self, seeded_session: Session, code: str, _: str, __: list) -> None:
        """Each Phase 5E process has exactly one Stage 1 resolver option."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
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

        assert option is not None, f"Stage 1 option must be seeded for {code}"
        assert option.resolver_name == "dept_head_at_requestor_campus"
        assert option.label == "Head of Department"
        assert option.sort_order == 0

    def test_phase5e_seeds_idempotent(self, seeded_session: Session) -> None:
        """Calling _seed_faculty_simple_linear_process on already-seeded data returns 0."""
        from scripts.seed import _seed_faculty_simple_linear_process

        for code, title, channel in _PHASE_5E_PROCESSES:
            result = _seed_faculty_simple_linear_process(
                seeded_session,
                code=code,
                title=title,
                channel_role_codes=channel,
            )
            seeded_session.flush()
            assert result == 0, f"Second seed call for {code} must be idempotent (got {result})"

            count = len(seeded_session.exec(
                select(ApprovalProcess).where(
                    ApprovalProcess.code == code,
                    ApprovalProcess.is_deleted == False,  # noqa: E712
                )
            ).all())
            assert count == 1, f"Idempotent: must not create duplicate process for {code}"


# ── Phase 5F: 3 OR-set faculty processes ─────────────────────────────────────

_PHASE_5F_PROCESSES = [
    (
        "faculty_fdp",
        "Faculty Development Programme Request",
        ["HOD", "DIRECTOR", "VC"],
        {"director_at_requestor_campus", "dean_at_requestor_campus"},
    ),
    (
        "faculty_conference",
        "Faculty Conference/Symposium/Seminar/Workshop Request",
        ["HOD", "DIRECTOR", "VC"],
        {"director_at_requestor_campus", "dean_at_requestor_campus"},
    ),
    (
        "faculty_inhouse_research_funding",
        "Faculty In-house Research Funding Request",
        ["HOD", "DEAN", "REGISTRAR", "VC"],
        {"dean_at_requestor_campus", "director_at_requestor_campus"},
    ),
]


class TestPhase5FOrSetSeeds:
    @pytest.mark.parametrize("code,title,channel,_", _PHASE_5F_PROCESSES)
    def test_process_seeded(
        self, seeded_session: Session, code: str, title: str, channel: list, _: set
    ) -> None:
        """Each Phase 5F process exists with correct metadata."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()

        assert process is not None, f"{code} process must be seeded"
        assert process.title == title
        assert process.requestor_role_codes == ["FACULTY"]
        assert process.channel_role_codes == channel
        assert not process.is_finance
        assert process.max_upward_attachments == 3
        assert process.allowed_attachment_mime_types_json == ["application/pdf"]
        assert process.max_downward_attachments == 0

    @pytest.mark.parametrize("code,_,__,___", _PHASE_5F_PROCESSES)
    def test_stage_pick_modes_json(
        self, seeded_session: Session, code: str, _: str, __: list, ___: set
    ) -> None:
        """stage_pick_modes_json contains both stage 1 and stage 2 as 'approver'."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert process is not None
        assert process.stage_pick_modes_json is not None
        assert process.stage_pick_modes_json.get("1") == "approver"
        assert process.stage_pick_modes_json.get("2") == "approver"

    @pytest.mark.parametrize("code,_,__,___", _PHASE_5F_PROCESSES)
    def test_stage1_option_seeded(
        self, seeded_session: Session, code: str, _: str, __: list, ___: set
    ) -> None:
        """Each Phase 5F process has exactly one Stage 1 resolver option."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
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

        assert option is not None, f"Stage 1 option must be seeded for {code}"
        assert option.resolver_name == "dept_head_at_requestor_campus"
        assert option.label == "Head of Department"
        assert option.sort_order == 0

    @pytest.mark.parametrize("code,_,__,expected_resolvers", _PHASE_5F_PROCESSES)
    def test_stage2_or_set_options_seeded(
        self,
        seeded_session: Session,
        code: str,
        _: str,
        __: list,
        expected_resolvers: set,
    ) -> None:
        """Each Phase 5F process has exactly two Stage 2 OR-set options."""
        process = seeded_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert process is not None

        options = seeded_session.exec(
            select(ApprovalStageOption).where(
                ApprovalStageOption.approval_process_id == process.id,
                ApprovalStageOption.stage_index == 2,
                ApprovalStageOption.is_deleted == False,  # noqa: E712
            )
        ).all()

        assert len(options) == 2, f"Stage 2 must have exactly 2 options for {code}"
        actual_resolvers = {opt.resolver_name for opt in options}
        assert actual_resolvers == expected_resolvers
        for opt in options:
            assert opt.resolver_name in {"director_at_requestor_campus", "dean_at_requestor_campus"}
            assert opt.label in {"Director", "Dean"}

    def test_phase5f_seeds_idempotent(self, seeded_session: Session) -> None:
        """Calling _seed_faculty_simple_linear_process on already-seeded data returns 0."""
        from scripts.seed import _seed_faculty_simple_linear_process

        fdp_or_set: dict = {2: [("director_at_requestor_campus", "Director"), ("dean_at_requestor_campus", "Dean")]}
        inhouse_or_set: dict = {2: [("dean_at_requestor_campus", "Dean"), ("director_at_requestor_campus", "Director")]}
        per_code_or_set = {
            "faculty_fdp": fdp_or_set,
            "faculty_conference": fdp_or_set,
            "faculty_inhouse_research_funding": inhouse_or_set,
        }

        for code, title, channel, _ in _PHASE_5F_PROCESSES:
            result = _seed_faculty_simple_linear_process(
                seeded_session,
                code=code,
                title=title,
                channel_role_codes=channel,
                or_set_stages=per_code_or_set[code],
                stage_pick_modes_json={"1": "approver", "2": "approver"},
            )
            seeded_session.flush()
            assert result == 0, f"Second seed call for {code} must be idempotent (got {result})"

            count = len(seeded_session.exec(
                select(ApprovalProcess).where(
                    ApprovalProcess.code == code,
                    ApprovalProcess.is_deleted == False,  # noqa: E712
                )
            ).all())
            assert count == 1, f"Idempotent: must not create duplicate process for {code}"
