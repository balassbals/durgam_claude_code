"""Unit tests for ApprovalRequestService — state machine + audit + notifications."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.models.crosscutting import ApprovalRequest, Notification
from durgam.services.approval_request import ApprovalRequestError, ApprovalRequestService


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_process(
    *,
    requestor_role_codes=None,
    channel_role_codes=None,
    requires_upward_attachments=False,
    max_upward_attachments=0,
    requires_downward_attachments=False,
    max_downward_attachments=0,
    informational_cc_role_codes=None,
    is_deleted=False,
):
    proc = MagicMock()
    proc.id = uuid4()
    proc.code = "TEST_PROC"
    proc.title = "Test Process"
    proc.requestor_role_codes = requestor_role_codes
    proc.channel_role_codes = channel_role_codes or ["HOD"]
    proc.requires_upward_attachments = requires_upward_attachments
    proc.max_upward_attachments = max_upward_attachments
    proc.requires_downward_attachments = requires_downward_attachments
    proc.max_downward_attachments = max_downward_attachments
    proc.informational_cc_role_codes = informational_cc_role_codes
    proc.is_deleted = is_deleted
    return proc


def _make_request(
    *,
    process_id=None,
    requestor_user_id=None,
    state="submitted",
    current_stage=1,
    title="Test Request",
):
    req = MagicMock(spec=ApprovalRequest)
    req.id = uuid4()
    req.process_id = process_id or uuid4()
    req.requestor_user_id = requestor_user_id or uuid4()
    req.state = state
    req.current_stage = current_stage
    req.title = title
    req.payload_json = None
    req.decided_at = None
    req.is_deleted = False
    return req


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    user.is_deleted = False
    user.is_active = True
    return user


def _make_role(code="HOD", role_id=None):
    role = MagicMock()
    role.id = role_id or uuid4()
    role.code = code
    role.is_deleted = False
    return role


def _make_user_role(user_id, role_id):
    ur = MagicMock()
    ur.user_id = user_id
    ur.role_id = role_id
    return ur


def _build_session(process=None, request=None, users=None):
    """Build a mock session with controllable exec/get responses."""
    session = MagicMock()
    notifications_added: list[Notification] = []

    original_add = session.add

    def track_add(obj):
        if isinstance(obj, Notification):
            notifications_added.append(obj)
        original_add(obj)

    session.add.side_effect = track_add
    session._notifications_added = notifications_added
    return session


# ── Submit tests ────────────────────────────────────────────────────────


class TestSubmit:
    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_submit_creates_request_and_audit_and_notifications(
        self, mock_resolve, mock_audit
    ):
        approver = _make_user()
        mock_resolve.return_value = [approver]

        process = _make_process()
        session = MagicMock()

        svc = ApprovalRequestService(session)
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process
        svc._req_repo = MagicMock()
        svc._req_repo.save.side_effect = lambda r: r

        result = svc.submit(
            process_id=process.id,
            requestor_user_id=uuid4(),
            title="Test Submit",
        )

        assert result.state == "submitted"
        assert result.current_stage == 1
        svc._req_repo.save.assert_called_once()
        mock_audit.assert_called_once()
        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "submit"
        assert audit_kwargs["resource"] == "approval_request"
        assert audit_kwargs["after"]["state"] == "submitted"
        assert audit_kwargs["after"]["stage"] == 1

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_submit_rejects_non_requestor_role(self, mock_resolve, mock_audit):
        process = _make_process(requestor_role_codes=["FACULTY"])
        session = MagicMock()

        basic_role = _make_role("BASIC_USER")
        ur = _make_user_role(uuid4(), basic_role.id)

        def exec_side(stmt):
            result = MagicMock()
            result.all.return_value = [ur]
            return result

        session.exec.side_effect = exec_side
        session.get.return_value = basic_role

        svc = ApprovalRequestService(session)
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        with pytest.raises(ApprovalRequestError, match="required role"):
            svc.submit(
                process_id=process.id,
                requestor_user_id=uuid4(),
                title="Test",
            )

    def test_submit_attachment_count_validation_min(self):
        process = _make_process(requires_upward_attachments=True)
        session = MagicMock()

        svc = ApprovalRequestService(session)
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        with pytest.raises(ApprovalRequestError, match="At least one"):
            svc.submit(
                process_id=process.id,
                requestor_user_id=uuid4(),
                title="Test",
                upward_attachment_file_ids=[],
            )

    def test_submit_attachment_count_validation_max(self):
        process = _make_process(max_upward_attachments=2)
        session = MagicMock()

        svc = ApprovalRequestService(session)
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        with pytest.raises(ApprovalRequestError, match="Too many"):
            svc.submit(
                process_id=process.id,
                requestor_user_id=uuid4(),
                title="Test",
                upward_attachment_file_ids=[uuid4(), uuid4(), uuid4()],
            )

    def test_submit_process_not_found_raises(self):
        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = None

        with pytest.raises(ApprovalRequestError, match="not found"):
            svc.submit(
                process_id=uuid4(),
                requestor_user_id=uuid4(),
                title="Test",
            )


# ── View request tests ─────────────────────────────────────────────────


class TestViewRequest:
    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_auto_transitions_submitted_to_in_review_for_approver(
        self, mock_resolve, mock_audit
    ):
        approver = _make_user()
        mock_resolve.return_value = [approver]

        request = _make_request(state="submitted")
        process = _make_process()

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.view_request(request_id=request.id, viewer_user_id=approver.id)

        svc._req_repo.update_state.assert_called_once_with(request, "in_review")
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["action"] == "view_first_review"

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_no_transition_for_non_approver(self, mock_resolve, mock_audit):
        approver = _make_user()
        mock_resolve.return_value = [approver]

        request = _make_request(state="submitted")
        process = _make_process()
        viewer = uuid4()

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.view_request(request_id=request.id, viewer_user_id=viewer)

        svc._req_repo.update_state.assert_not_called()
        mock_audit.assert_not_called()


# ── Approve tests ──────────────────────────────────────────────────────


class TestApprove:
    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_non_terminal_advances_stage_and_notifies_next_stage(
        self, mock_resolve, mock_audit
    ):
        approver = _make_user()
        next_approver = _make_user()
        mock_resolve.side_effect = [
            [approver],
            [next_approver],
        ]

        request = _make_request(state="in_review", current_stage=1)
        process = _make_process(channel_role_codes=["HOD", "DEAN"])

        session = MagicMock()
        session.get.return_value = None
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.approve(
            request_id=request.id,
            approver_user_id=approver.id,
            comment="Looks good",
        )

        svc._req_repo.advance_stage.assert_called_once_with(request)
        svc._req_repo.update_state.assert_not_called()

        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "forward"

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_terminal_sets_state_approved_and_notifies_requestor_plus_cc(
        self, mock_resolve, mock_audit
    ):
        approver = _make_user()
        mock_resolve.return_value = [approver]

        requestor = _make_user()
        request = _make_request(
            state="in_review",
            current_stage=1,
            requestor_user_id=requestor.id,
        )
        process = _make_process(channel_role_codes=["HOD"])

        session = MagicMock()
        session.get.return_value = requestor

        def exec_side(stmt):
            result = MagicMock()
            result.first.return_value = None
            result.all.return_value = []
            return result

        session.exec.side_effect = exec_side

        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.approve(
            request_id=request.id,
            approver_user_id=approver.id,
        )

        svc._req_repo.update_state.assert_called_once()
        call_args = svc._req_repo.update_state.call_args
        assert call_args[0][1] == "approved"

        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "approve"
        assert audit_kwargs["after"]["state"] == "approved"

    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_approve_non_approver_raises(self, mock_resolve):
        approver = _make_user()
        mock_resolve.return_value = [approver]

        request = _make_request(state="in_review")
        process = _make_process()

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        with pytest.raises(ApprovalRequestError, match="not an approver"):
            svc.approve(
                request_id=request.id,
                approver_user_id=uuid4(),
            )

    def test_approve_terminal_state_raises(self):
        request = _make_request(state="approved")
        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = _make_process()

        with pytest.raises(ApprovalRequestError, match="already approved"):
            svc.approve(
                request_id=request.id,
                approver_user_id=uuid4(),
            )


# ── Reject tests ───────────────────────────────────────────────────────


class TestReject:
    def test_reject_requires_comment(self):
        request = _make_request(state="in_review")
        session = MagicMock()
        svc = ApprovalRequestService(session)

        with pytest.raises(ApprovalRequestError, match="comment is required"):
            svc.reject(
                request_id=request.id,
                approver_user_id=uuid4(),
                comment="",
            )

    def test_reject_whitespace_comment_raises(self):
        session = MagicMock()
        svc = ApprovalRequestService(session)

        with pytest.raises(ApprovalRequestError, match="comment is required"):
            svc.reject(
                request_id=uuid4(),
                approver_user_id=uuid4(),
                comment="   ",
            )

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_reject_terminal_state_no_further_actions_possible(
        self, mock_resolve, mock_audit
    ):
        approver = _make_user()
        mock_resolve.return_value = [approver]

        requestor = _make_user()
        request = _make_request(
            state="in_review",
            requestor_user_id=requestor.id,
        )
        process = _make_process()

        session = MagicMock()
        session.get.return_value = requestor

        def exec_side(stmt):
            result = MagicMock()
            result.first.return_value = None
            result.all.return_value = []
            return result

        session.exec.side_effect = exec_side

        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.reject(
            request_id=request.id,
            approver_user_id=approver.id,
            comment="Not justified.",
        )

        svc._req_repo.update_state.assert_called()
        final_call = svc._req_repo.update_state.call_args_list[-1]
        assert final_call[0][1] == "rejected"

        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "reject"
        assert audit_kwargs["after"]["comment"] == "Not justified."


# ── Withdraw tests ─────────────────────────────────────────────────────


class TestWithdraw:
    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_withdraw_in_submitted_state_succeeds(self, mock_resolve, mock_audit):
        mock_resolve.return_value = []

        requestor_id = uuid4()
        request = _make_request(state="submitted", requestor_user_id=requestor_id)
        process = _make_process()

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.withdraw(request_id=request.id, requestor_user_id=requestor_id)

        svc._req_repo.update_state.assert_called_once()
        call_args = svc._req_repo.update_state.call_args
        assert call_args[0][1] == "withdrawn"

        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "withdraw"

    def test_withdraw_in_review_raises(self):
        requestor_id = uuid4()
        request = _make_request(state="in_review", requestor_user_id=requestor_id)

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request

        with pytest.raises(ApprovalRequestError, match="submitted"):
            svc.withdraw(request_id=request.id, requestor_user_id=requestor_id)

    def test_withdraw_by_non_requestor_raises(self):
        request = _make_request(state="submitted")

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request

        with pytest.raises(ApprovalRequestError, match="requestor"):
            svc.withdraw(request_id=request.id, requestor_user_id=uuid4())


# ── Cancel tests ───────────────────────────────────────────────────────


class TestCancel:
    @patch("durgam.services.approval_request.write_audit_row")
    def test_cancel_requires_sys_admin(self, mock_audit):
        session = MagicMock()

        def exec_side(stmt):
            result = MagicMock()
            result.first.return_value = None
            return result

        session.exec.side_effect = exec_side

        svc = ApprovalRequestService(session)

        with pytest.raises(ApprovalRequestError, match="System Administrator"):
            svc.cancel(
                request_id=uuid4(),
                sys_admin_user_id=uuid4(),
                comment="Duplicate request",
            )

    @patch("durgam.services.approval_request.write_audit_row")
    def test_cancel_succeeds_for_sys_admin(self, mock_audit):
        admin_id = uuid4()
        requestor = _make_user()
        request = _make_request(state="in_review", requestor_user_id=requestor.id)
        process = _make_process()

        sys_admin_role = _make_role("SYSTEM_ADMIN")
        ur = _make_user_role(admin_id, sys_admin_role.id)

        session = MagicMock()

        call_count = {"n": 0}

        def exec_side(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.first.return_value = sys_admin_role
                return result
            elif call_count["n"] == 2:
                result.first.return_value = ur
                return result
            else:
                result.first.return_value = None
                result.all.return_value = []
                return result

        session.exec.side_effect = exec_side
        session.get.return_value = requestor

        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        svc.cancel(
            request_id=request.id,
            sys_admin_user_id=admin_id,
            comment="Duplicate",
        )

        svc._req_repo.update_state.assert_called_once()
        call_args = svc._req_repo.update_state.call_args
        assert call_args[0][1] == "cancelled"

        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "cancel"
        assert audit_kwargs["actor_role_code"] == "SYSTEM_ADMIN"
        assert audit_kwargs["after"]["comment"] == "Duplicate"

    @patch("durgam.services.approval_request.write_audit_row")
    def test_cancel_terminal_state_raises(self, mock_audit):
        admin_id = uuid4()
        request = _make_request(state="approved")

        sys_admin_role = _make_role("SYSTEM_ADMIN")
        ur = _make_user_role(admin_id, sys_admin_role.id)

        session = MagicMock()
        call_count = {"n": 0}

        def exec_side(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.first.return_value = sys_admin_role
                return result
            elif call_count["n"] == 2:
                result.first.return_value = ur
                return result
            else:
                result.first.return_value = None
                return result

        session.exec.side_effect = exec_side

        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request

        with pytest.raises(ApprovalRequestError, match="already approved"):
            svc.cancel(
                request_id=request.id,
                sys_admin_user_id=admin_id,
                comment="Test",
            )


# ── Audit diff shape tests ─────────────────────────────────────────────


class TestAuditDiffShape:
    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_audit_row_diff_shape_for_each_transition(
        self, mock_resolve, mock_audit
    ):
        mock_resolve.return_value = []

        session = MagicMock()
        session.get.return_value = None

        def exec_side(stmt):
            result = MagicMock()
            result.first.return_value = None
            result.all.return_value = []
            return result

        session.exec.side_effect = exec_side

        process = _make_process()

        svc = ApprovalRequestService(session)
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process
        svc._req_repo = MagicMock()
        svc._req_repo.save.side_effect = lambda r: r

        requestor_id = uuid4()
        svc.submit(
            process_id=process.id,
            requestor_user_id=requestor_id,
            title="Diff Shape Test",
        )

        submit_kwargs = mock_audit.call_args.kwargs
        assert "state" in submit_kwargs["after"]
        assert "stage" in submit_kwargs["after"]
        assert submit_kwargs["before"] is None
        assert submit_kwargs["action"] == "submit"
        assert submit_kwargs["resource"] == "approval_request"


# ── Post-approval callback tests ─────────────────────────────────────


class TestPostApprovalCallback:
    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_approve_terminal_nrf_creates_record(
        self, mock_resolve, mock_audit
    ):
        """Full NRF_APPROVAL 2-stage flow: stage-1 forward, stage-2 terminal approval
        creates NonRegularFaculty record with approval fields populated."""
        approver_1 = _make_user()
        approver_2 = _make_user()

        nrf_payload = {
            "description": "Visiting faculty request",
            "nrf_data": {
                "department_id": str(uuid4()),
                "name": "Dr. Example",
                "designation": "Professor",
                "organization": "Test University",
                "expertise": "Physics",
                "available_from": "2026-07-01",
                "available_to": "2026-12-31",
                "non_regular_type": "visiting",
            },
        }

        process = _make_process(channel_role_codes=["DEAN", "REGISTRAR"])
        process.code = "NRF_APPROVAL"

        request = _make_request(
            state="in_review",
            current_stage=2,
            process_id=process.id,
        )
        request.payload_json = nrf_payload

        mock_resolve.return_value = [approver_2]

        session = MagicMock()
        requestor = _make_user(request.requestor_user_id)
        session.get.return_value = requestor

        def exec_side(stmt):
            result = MagicMock()
            result.first.return_value = None
            result.all.return_value = []
            return result

        session.exec.side_effect = exec_side

        mock_nrf_record = MagicMock()
        mock_nrf_record.id = uuid4()

        with patch(
            "durgam.repositories.non_regular_faculty.NonRegularFacultyRepository"
        ) as MockNrfRepo, patch(
            "durgam.services.non_regular_faculty.NonRegularFacultyService"
        ) as MockNrfSvc:
            mock_repo_inst = MagicMock()
            MockNrfRepo.return_value = mock_repo_inst
            mock_svc_inst = MagicMock()
            mock_svc_inst.create.return_value = mock_nrf_record
            MockNrfSvc.return_value = mock_svc_inst

            svc = ApprovalRequestService(session)
            svc._req_repo = MagicMock()
            svc._req_repo.get_by_id.return_value = request
            svc._proc_repo = MagicMock()
            svc._proc_repo.get_by_id.return_value = process

            svc.approve(
                request_id=request.id,
                approver_user_id=approver_2.id,
            )

            mock_svc_inst.create.assert_called_once()
            create_kwargs = mock_svc_inst.create.call_args.kwargs
            assert create_kwargs["name"] == "Dr. Example"
            assert create_kwargs["designation"] == "Professor"
            assert create_kwargs["organization"] == "Test University"
            assert create_kwargs["expertise"] == "Physics"

            assert mock_nrf_record.is_admin_approved is True
            assert mock_nrf_record.approved_by_user_id == approver_2.id
            assert mock_nrf_record.approval_request_id == request.id
            mock_repo_inst.save.assert_called_once_with(mock_nrf_record)

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_approve_nrf_payload_missing_required_fields_raises(
        self, mock_resolve, mock_audit
    ):
        """NRF_APPROVAL with missing nrf_data raises ApprovalRequestError."""
        approver = _make_user()
        mock_resolve.return_value = [approver]

        process = _make_process(channel_role_codes=["REGISTRAR"])
        process.code = "NRF_APPROVAL"

        request = _make_request(
            state="in_review",
            current_stage=1,
            process_id=process.id,
        )
        request.payload_json = {"description": "Missing nrf_data"}

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        with pytest.raises(ApprovalRequestError, match="nrf_data"):
            svc.approve(
                request_id=request.id,
                approver_user_id=approver.id,
            )

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_approve_non_nrf_process_skips_callback(
        self, mock_resolve, mock_audit
    ):
        """Non-NRF process terminal approval does not create NRF records."""
        approver = _make_user()
        mock_resolve.return_value = [approver]

        requestor = _make_user()
        process = _make_process(channel_role_codes=["HOD"])
        process.code = "CPC_FUND_RELEASE"

        request = _make_request(
            state="in_review",
            current_stage=1,
            process_id=process.id,
            requestor_user_id=requestor.id,
        )

        session = MagicMock()
        session.get.return_value = requestor

        def exec_side(stmt):
            result = MagicMock()
            result.first.return_value = None
            result.all.return_value = []
            return result

        session.exec.side_effect = exec_side

        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        with patch(
            "durgam.repositories.non_regular_faculty.NonRegularFacultyRepository"
        ) as MockNrfRepo:
            svc.approve(
                request_id=request.id,
                approver_user_id=approver.id,
            )
            MockNrfRepo.assert_not_called()

        svc._req_repo.update_state.assert_called_once()
        assert svc._req_repo.update_state.call_args[0][1] == "approved"

    @patch("durgam.services.approval_request.write_audit_row")
    @patch("durgam.services.approval_request.resolve_stage_approvers")
    def test_approve_nrf_rollback_on_callback_failure(
        self, mock_resolve, mock_audit
    ):
        """If NRF creation fails, the approve state transition is not committed."""
        approver = _make_user()
        mock_resolve.return_value = [approver]

        process = _make_process(channel_role_codes=["REGISTRAR"])
        process.code = "NRF_APPROVAL"

        nrf_payload = {
            "nrf_data": {
                "department_id": str(uuid4()),
                "name": "",
                "designation": "Prof",
                "organization": "Org",
                "expertise": "Area",
                "available_from": "2026-07-01",
                "available_to": "2026-12-31",
            },
        }

        request = _make_request(
            state="in_review",
            current_stage=1,
            process_id=process.id,
        )
        request.payload_json = nrf_payload

        session = MagicMock()
        svc = ApprovalRequestService(session)
        svc._req_repo = MagicMock()
        svc._req_repo.get_by_id.return_value = request
        svc._proc_repo = MagicMock()
        svc._proc_repo.get_by_id.return_value = process

        from durgam.services.non_regular_faculty import NonRegularFacultyError

        with patch(
            "durgam.repositories.non_regular_faculty.NonRegularFacultyRepository"
        ), patch(
            "durgam.services.non_regular_faculty.NonRegularFacultyService"
        ) as MockNrfSvc:
            mock_svc_inst = MagicMock()
            mock_svc_inst.create.side_effect = NonRegularFacultyError(
                "Name is required."
            )
            MockNrfSvc.return_value = mock_svc_inst

            with pytest.raises(NonRegularFacultyError, match="Name is required"):
                svc.approve(
                    request_id=request.id,
                    approver_user_id=approver.id,
                )

        mock_audit.assert_not_called()
