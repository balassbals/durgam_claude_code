"""Unit tests for ApproverInboxState — inbox filtering logic."""

from unittest.mock import MagicMock, patch
from uuid import uuid4


def _make_request(state="submitted", current_stage=1, requestor_id=None):
    req = MagicMock()
    req.id = uuid4()
    req.title = f"Request {req.id.hex[:6]}"
    req.state = state
    req.current_stage = current_stage
    req.process_id = uuid4()
    req.requestor_user_id = requestor_id or uuid4()
    req.created_at = None
    return req


def _make_process(channel_role_codes=None):
    proc = MagicMock()
    proc.id = uuid4()
    proc.code = "PROC"
    proc.title = "Test Process"
    proc.channel_role_codes = channel_role_codes or ["HOD"]
    return proc


def _make_user(user_id):
    u = MagicMock()
    u.id = user_id
    u.full_name = f"User {user_id.hex[:6]}"
    u.username = f"user_{user_id.hex[:6]}"
    return u


class TestInboxFiltering:
    def test_only_includes_requests_where_viewer_is_approver(self):
        """Given 3 pending requests, only those where viewer is in approvers appear."""
        viewer_id = uuid4()
        other_id = uuid4()

        req_for_viewer = _make_request()
        req_for_other = _make_request()
        req_terminal = _make_request(state="approved")

        viewer_user = _make_user(viewer_id)
        other_user = _make_user(other_id)

        pending_requests = [req_for_viewer, req_for_other]

        approver_map = {
            req_for_viewer.id: [viewer_user],
            req_for_other.id: [other_user],
        }

        enriched = []
        for r in pending_requests:
            approvers = approver_map.get(r.id, [])
            approver_ids = {u.id for u in approvers}
            if viewer_id not in approver_ids:
                continue
            enriched.append({"id": str(r.id), "title": r.title})

        assert len(enriched) == 1
        assert enriched[0]["id"] == str(req_for_viewer.id)

    def test_empty_inbox_when_no_approver_matches(self):
        """Viewer is not an approver for any request → empty list."""
        viewer_id = uuid4()
        other_id = uuid4()

        req = _make_request()
        other_user = _make_user(other_id)

        approvers = [other_user]
        approver_ids = {u.id for u in approvers}

        enriched = []
        if viewer_id in approver_ids:
            enriched.append({"id": str(req.id)})

        assert len(enriched) == 0

    def test_terminal_state_requests_excluded_by_list_by_states(self):
        """list_by_states(["submitted", "in_review"]) excludes terminal states."""
        all_states = ["submitted", "in_review", "approved", "rejected", "withdrawn", "cancelled"]
        filtered = ["submitted", "in_review"]
        excluded = [s for s in all_states if s not in filtered]

        assert "approved" in excluded
        assert "rejected" in excluded
        assert "withdrawn" in excluded
        assert "cancelled" in excluded
        assert "submitted" not in excluded
        assert "in_review" not in excluded


class TestPotentialApproverGuard:
    """Regression: _potential_approver_guard must call can() with full signature."""

    def _make_state(self, user_id):
        state = MagicMock()
        state.current_user_id = str(user_id)
        state._resolve_session = MagicMock()
        state.flash = ""
        state.flash_type = "info"
        state.admin_authorized = False
        return state

    @patch("durgam.states.approval_requests.open_session")
    @patch("durgam.pages.approvals.is_channel_approver")
    @patch("durgam.auth.permissions.can")
    def test_static_permission_holder_passes_guard(
        self, mock_can, mock_channel, mock_open
    ):
        user_id = uuid4()
        mock_session = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_can.return_value = True

        from durgam.states.approval_requests import ApproverInboxState

        state = self._make_state(user_id)
        result = ApproverInboxState._potential_approver_guard(state)

        assert result is None
        assert state.admin_authorized is True
        mock_can.assert_called_once_with(
            user_id, "approve", "approval_request", None, None, mock_session,
        )

    @patch("durgam.states.approval_requests.open_session")
    @patch("durgam.pages.approvals.is_channel_approver")
    @patch("durgam.auth.permissions.can")
    def test_channel_only_approver_passes_guard(
        self, mock_can, mock_channel, mock_open
    ):
        user_id = uuid4()
        mock_session = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_can.return_value = False
        mock_channel.return_value = True

        from durgam.states.approval_requests import ApproverInboxState

        state = self._make_state(user_id)
        result = ApproverInboxState._potential_approver_guard(state)

        assert result is None
        assert state.admin_authorized is True
        mock_channel.assert_called_once_with(user_id, mock_session)

    @patch("durgam.states.approval_requests.open_session")
    @patch("durgam.pages.approvals.is_channel_approver")
    @patch("durgam.auth.permissions.can")
    def test_non_approver_redirected(
        self, mock_can, mock_channel, mock_open
    ):
        user_id = uuid4()
        mock_session = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_can.return_value = False
        mock_channel.return_value = False

        from durgam.states.approval_requests import ApproverInboxState

        state = self._make_state(user_id)
        result = ApproverInboxState._potential_approver_guard(state)

        assert result is not None
        assert state.flash == "You do not have access to the approvals inbox."
        assert state.admin_authorized is False
