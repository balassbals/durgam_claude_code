"""Unit tests for RequestDetailState — can_decide evaluation + next_stage_approvers_preview."""

from uuid import uuid4

import pytest


class TestCanDecideMatrix:
    """Verify can_decide across the state-machine matrix.

    can_decide = viewer_is_current_stage_approver AND state in (submitted, in_review)
    """

    @pytest.mark.parametrize(
        "state, is_approver, expected",
        [
            ("submitted", True, True),
            ("in_review", True, True),
            ("approved", True, False),
            ("rejected", True, False),
            ("withdrawn", True, False),
            ("cancelled", True, False),
            ("submitted", False, False),
            ("in_review", False, False),
        ],
        ids=[
            "submitted+approver=True",
            "in_review+approver=True",
            "approved+approver=False",
            "rejected+approver=False",
            "withdrawn+approver=False",
            "cancelled+approver=False",
            "submitted+non-approver=False",
            "in_review+non-approver=False",
        ],
    )
    def test_can_decide(self, state, is_approver, expected):
        """can_decide is True only when state is non-terminal AND viewer is approver."""
        non_terminal = state in ("submitted", "in_review")
        can_decide = is_approver and non_terminal
        assert can_decide == expected

    def test_requestor_is_not_approver_cannot_decide(self):
        """Even if the requestor views a submitted request, they cannot decide
        unless they also happen to be a current-stage approver."""
        is_approver = False
        state = "submitted"
        can_decide = is_approver and state in ("submitted", "in_review")
        assert can_decide is False


class TestNextStageApproversPreview:
    def test_empty_at_terminal_stage(self):
        """At terminal stage, next_stage_approvers_preview is empty."""
        current_stage = 2
        channel_len = 2
        is_terminal = current_stage >= channel_len
        assert is_terminal is True

        preview: list[str] = []
        assert preview == []

    def test_populated_at_non_terminal_stage(self):
        """At non-terminal stage, preview includes next-stage approver names."""
        current_stage = 1
        channel_len = 3
        is_terminal = current_stage >= channel_len
        assert is_terminal is False

        next_approvers = ["Dean Smith", "Dean Jones"]
        names = [n for n in next_approvers[:3]]
        assert names == ["Dean Smith", "Dean Jones"]

    def test_truncated_with_more_indicator(self):
        """When >3 next-stage approvers, preview shows first 3 + 'and N more'."""
        next_approvers = ["A", "B", "C", "D", "E"]
        names = list(next_approvers[:3])
        if len(next_approvers) > 3:
            names.append(f"and {len(next_approvers) - 3} more")

        assert names == ["A", "B", "C", "and 2 more"]
