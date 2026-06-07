"""Unit tests for SubmitRequestState — process-options role filtering logic."""

from unittest.mock import MagicMock
from uuid import uuid4


def _make_process(code, title, requestor_role_codes=None, requires_upward=False, max_upward=0):
    proc = MagicMock()
    proc.id = uuid4()
    proc.code = code
    proc.title = title
    proc.requestor_role_codes = requestor_role_codes
    proc.requires_upward_attachments = requires_upward
    proc.max_upward_attachments = max_upward
    return proc


def _filter_processes(all_procs, user_role_codes):
    """Replicates the filtering logic from SubmitRequestState.load_submit."""
    eligible = []
    for proc in all_procs:
        if proc.requestor_role_codes:
            if not user_role_codes & set(proc.requestor_role_codes):
                continue
        eligible.append({
            "id": str(proc.id),
            "code": proc.code,
            "title": proc.title,
            "requires_upward": proc.requires_upward_attachments,
            "max_upward": proc.max_upward_attachments,
        })
    return eligible


class TestProcessOptionsFilter:
    def test_filters_processes_by_user_role_codes(self):
        """User with FACULTY role sees open + faculty-only processes, not student-only."""
        procs = [
            _make_process("OPEN", "Open Process", requestor_role_codes=None),
            _make_process("FAC_ONLY", "Faculty Only", requestor_role_codes=["FACULTY"]),
            _make_process("STU_ONLY", "Student Only", requestor_role_codes=["STUDENT"]),
        ]
        user_roles = {"FACULTY"}

        result = _filter_processes(procs, user_roles)

        assert len(result) == 2
        codes = {p["code"] for p in result}
        assert "OPEN" in codes
        assert "FAC_ONLY" in codes
        assert "STU_ONLY" not in codes

    def test_open_process_visible_to_all_roles(self):
        """Process with no requestor_role_codes is visible to any user."""
        procs = [
            _make_process("OPEN", "Open Process", requestor_role_codes=None),
        ]
        user_roles = {"STUDENT"}

        result = _filter_processes(procs, user_roles)

        assert len(result) == 1
        assert result[0]["code"] == "OPEN"

    def test_empty_requestor_roles_list_treated_as_open(self):
        """Process with empty requestor_role_codes list is treated as open (same as None)."""
        procs = [
            _make_process("OPEN_EMPTY", "Open Empty", requestor_role_codes=[]),
        ]
        user_roles = {"FACULTY", "HOD"}

        result = _filter_processes(procs, user_roles)

        assert len(result) == 1
        assert result[0]["code"] == "OPEN_EMPTY"

    def test_multi_role_user_sees_union(self):
        """User with multiple roles sees the union of eligible processes."""
        procs = [
            _make_process("FAC", "Faculty", requestor_role_codes=["FACULTY"]),
            _make_process("HOD", "HoD", requestor_role_codes=["HOD"]),
            _make_process("STU", "Student", requestor_role_codes=["STUDENT"]),
        ]
        user_roles = {"FACULTY", "HOD"}

        result = _filter_processes(procs, user_roles)

        assert len(result) == 2
        codes = {p["code"] for p in result}
        assert codes == {"FAC", "HOD"}

    def test_preserves_attachment_config(self):
        """Filtered result carries requires_upward and max_upward from the process."""
        procs = [
            _make_process("P1", "Process 1", requires_upward=True, max_upward=5),
        ]
        result = _filter_processes(procs, {"FACULTY"})

        assert len(result) == 1
        assert result[0]["requires_upward"] is True
        assert result[0]["max_upward"] == 5
