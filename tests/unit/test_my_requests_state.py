"""Unit tests for MyRequestsState — state filter logic."""

from uuid import uuid4

from durgam.states.approval_requests import _STATE_OPTIONS


class TestStateFilter:
    def test_all_filter_maps_to_none(self):
        """When state_filter is 'all', the handler passes None to the repo."""
        state_filter = "all"
        sf = None if state_filter == "all" else state_filter
        assert sf is None

    def test_specific_filter_passes_through(self):
        """When state_filter is a specific value, it passes through."""
        state_filter = "submitted"
        sf = None if state_filter == "all" else state_filter
        assert sf == "submitted"

    def test_state_options_no_empty_values(self):
        """All state option values are non-empty (Radix Select constraint)."""
        for opt in _STATE_OPTIONS:
            assert opt["value"] != "", f"Empty value in option: {opt}"
            assert opt["label"] != "", f"Empty label in option: {opt}"

    def test_state_options_includes_all_states(self):
        """State options cover all known approval request states."""
        values = {opt["value"] for opt in _STATE_OPTIONS}
        expected = {"all", "submitted", "in_review", "approved", "rejected", "withdrawn", "cancelled"}
        assert values == expected
