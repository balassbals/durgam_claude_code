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


# ── Phase 6: deep-link process pre-selection ──────────────────────────────────


def _preselect_process_id(process_options, requested_code, default="none"):
    """Replicates the ?process=<code> pre-selection logic from load_submit.

    Returns the matching process's id, or `default` ("none") when the param is
    absent or matches no eligible process — preserving manual-selection behaviour.
    """
    selected = default
    if requested_code:
        for opt in process_options:
            if opt["code"] == requested_code:
                selected = opt["id"]
                break
    return selected


class TestDeepLinkPreselection:
    def _options(self):
        return _filter_processes(
            [
                _make_process("faculty_noc", "Faculty NOC"),
                _make_process("faculty_fdp", "Faculty FDP"),
            ],
            {"FACULTY"},
        )

    def test_matching_param_preselects_process_id(self):
        opts = self._options()
        fdp_id = next(o["id"] for o in opts if o["code"] == "faculty_fdp")
        assert _preselect_process_id(opts, "faculty_fdp") == fdp_id

    def test_absent_param_falls_through_to_none(self):
        opts = self._options()
        assert _preselect_process_id(opts, "") == "none"

    def test_unmatched_param_falls_through_to_none(self):
        opts = self._options()
        assert _preselect_process_id(opts, "faculty_does_not_exist") == "none"


# ── Phase 8B: ?type=faculty deep-link row filter ──────────────────────────────


def _filter_faculty_rows(rows, type_param):
    """Replicates the ?type=faculty filter applied in load_my_requests /
    load_inbox: when type_param == 'faculty', keep only rows whose process_code
    starts with 'faculty_'; otherwise leave the list unchanged.
    """
    if type_param == "faculty":
        return [r for r in rows if r["process_code"].startswith("faculty_")]
    return rows


class TestFacultyTypeFilter:
    def _rows(self):
        return [
            {"id": "1", "process_code": "faculty_fdp"},
            {"id": "2", "process_code": "faculty_noc"},
            {"id": "3", "process_code": "NRF_APPROVAL"},
            {"id": "4", "process_code": "CPC_FUND_RELEASE"},
        ]

    def test_type_faculty_keeps_only_faculty_processes(self):
        out = _filter_faculty_rows(self._rows(), "faculty")
        assert {r["id"] for r in out} == {"1", "2"}

    def test_absent_type_leaves_list_unchanged(self):
        out = _filter_faculty_rows(self._rows(), "")
        assert len(out) == 4

    def test_other_type_leaves_list_unchanged(self):
        out = _filter_faculty_rows(self._rows(), "student")
        assert len(out) == 4
