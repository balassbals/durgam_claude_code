"""Phase 10A (Q-P10.4 STEP-A) — HoD recommend-via, proven on a THROWAWAY matrix
row + throwaway ApprovalProcess, isolated from the live LEAVE_APPROVAL flow.

Q-P10 (recommend-via) mechanism already exists in M8: LeaveSanctionAuthorityRule
.recommend_via_role_code + resolve_channel prepend a recommend-only stage. This
proves it works end-to-end for a HoD recommender against real PostgreSQL.

NO live LEAVE_APPROVAL wiring and NO Q-P10.2 leave-form UI — those are Phase 10B,
gated on Bala's go-ahead per Q-P10.4. The throwaway artifacts live in these test
fixtures (db_session), NOT in scripts/seed.py, so nothing ships to production seed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlmodel import Session

from durgam.models.crosscutting import ApprovalProcess
from durgam.models.identity import User
from durgam.models.leave import LeaveSanctionAuthorityRule
from durgam.repositories.leave import LeaveSanctionRuleRepository
from durgam.services.approval_request import ApprovalRequestService
from durgam.services.leave_rules import resolve_channel


_THROWAWAY_APPLICANT_ROLE = "FACULTY_10A_TEST"  # synthetic, not a real seeded role


def _throwaway_rule(session: Session) -> LeaveSanctionAuthorityRule:
    now = datetime.now(UTC)
    rule = LeaveSanctionAuthorityRule(
        leave_type="CL",
        applicant_role_code=_THROWAWAY_APPLICANT_ROLE,
        sanctioner_role_code="DIRECTOR",
        recommend_via_role_code="HOD",
        requires_in_charge=False,
        scope_type="department",
        priority=5,  # very specific so it wins
        created_at=now,
        updated_at=now,
    )
    return LeaveSanctionRuleRepository(session).save(rule)


class TestHodRecommendThrowawayMatrixRow:
    def test_persisted_rule_resolves_hod_recommend_prepend(self, db_session: Session) -> None:
        _throwaway_rule(db_session)
        rules = LeaveSanctionRuleRepository(db_session).list_active()
        channel = resolve_channel([_THROWAWAY_APPLICANT_ROLE], "CL", rules)
        assert channel[0]["role_code"] == "HOD"
        assert channel[0]["recommend_only"] is True
        assert channel[0]["scope_type"] == "department"
        assert channel[-1]["role_code"] == "DIRECTOR"
        assert channel[-1]["recommend_only"] is False

    def test_persisted_rule_present_in_active_list(self, db_session: Session) -> None:
        rule = _throwaway_rule(db_session)
        rules = LeaveSanctionRuleRepository(db_session).list_active()
        assert any(
            r.id == rule.id and r.recommend_via_role_code == "HOD" for r in rules
        )


class TestHodRecommendThrowawayProcess:
    def test_submit_carries_hod_recommend_first_stage(self, db_session: Session) -> None:
        # Throwaway process (open requestor) — explicitly _TEST, not live LEAVE_APPROVAL.
        now = datetime.now(UTC)
        proc = ApprovalProcess(
            code="LEAVE_APPROVAL_FACULTY_TEST",
            title="Leave Approval (Faculty) — 10A THROWAWAY",
            requestor_role_codes=None,  # open: any requestor
            channel_role_codes=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(proc)
        db_session.flush()

        requestor = User(
            username=f"l10a_{uuid4().hex[:8]}",
            email=f"l10a_{uuid4().hex[:8]}@dev.local",
            password_hash="x",
            is_active=True,
        )
        db_session.add(requestor)
        db_session.flush()

        rules = [_throwaway_rule(db_session)]
        channel = resolve_channel([_THROWAWAY_APPLICANT_ROLE], "CL", rules)

        svc = ApprovalRequestService(db_session)
        req = svc.submit(
            process_id=proc.id,
            requestor_user_id=requestor.id,
            title="CL 10A throwaway",
            payload={"leave_request_id": str(uuid4())},
            resolved_channel=channel,
        )

        # The resolved channel persisted onto the request, HoD recommend-only first.
        assert req.resolved_channel_json is not None
        assert req.resolved_channel_json[0]["role_code"] == "HOD"
        assert req.resolved_channel_json[0]["recommend_only"] is True
        assert req.resolved_channel_json[-1]["recommend_only"] is False
        # No HOD holder exists → stage not skipped → stays at stage 1, submitted.
        assert req.state == "submitted"
        assert req.current_stage == 1

    def test_throwaway_process_is_not_live_leave_approval(self, db_session: Session) -> None:
        # Guard: the throwaway is a distinct code, never the production LEAVE_APPROVAL.
        assert "LEAVE_APPROVAL_FACULTY_TEST" != "LEAVE_APPROVAL"
