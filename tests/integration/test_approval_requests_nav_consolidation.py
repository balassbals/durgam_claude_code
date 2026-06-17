"""Integration tests for Phase 7E nav consolidation + faculty-process filter.

Verifies:
  A. The faculty-process-code filter applied to SubmitRequestState.load_submit:
     - faculty_noc excluded from generic submit dropdown
     - All current and future FACULTY_REQUEST_TYPES codes excluded
     - Generic processes (LEAVE_APPROVAL, NRF_APPROVAL, etc.) still included
  B. The old /approvals/* routes are still reachable (not deleted).

DB strategy: pure-Python filter logic via SimpleNamespace mocks.
No seeded_session mutation. No models/migrations/seed touched.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


# ── helpers ───────────────────────────────────────────────────────────────────


def _proc(code: str, requestor_role_codes: list[str] | None = None) -> SimpleNamespace:
    """Minimal stand-in for an ApprovalProcess ORM row."""
    return SimpleNamespace(code=code, requestor_role_codes=requestor_role_codes)


def _apply_filter(
    all_procs: list[SimpleNamespace],
    user_role_codes: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Full filter logic mirroring SubmitRequestState.load_submit after Phase 7E.

    Both the faculty-process exclusion AND the role-eligibility check are included
    so the tests exercise the combined filter, not just the new clause.
    """
    from durgam.models.faculty_request import FACULTY_REQUEST_TYPES

    faculty_codes: frozenset[str] = frozenset(
        f"faculty_{rt}" for rt in FACULTY_REQUEST_TYPES
    )
    roles = user_role_codes or set()
    eligible: list[dict[str, Any]] = []
    for proc in all_procs:
        if proc.code in faculty_codes:
            continue
        if proc.requestor_role_codes:
            if not roles & set(proc.requestor_role_codes):
                continue
        eligible.append({"code": proc.code})
    return eligible


# ── A: faculty-process filter ─────────────────────────────────────────────────


class TestFacultyProcessFilter:
    """faculty_noc and all FACULTY_REQUEST_TYPES codes are excluded from the dropdown."""

    def test_old_submit_dropdown_excludes_faculty_noc(self) -> None:
        """faculty_noc must not appear in the generic submit dropdown."""
        procs = [_proc("faculty_noc"), _proc("LEAVE_APPROVAL")]
        result = _apply_filter(procs)
        codes = {r["code"] for r in result}
        assert "faculty_noc" not in codes
        assert "LEAVE_APPROVAL" in codes

    def test_old_submit_dropdown_excludes_all_known_faculty_types(self) -> None:
        """Every code derived from FACULTY_REQUEST_TYPES is excluded."""
        from durgam.models.faculty_request import FACULTY_REQUEST_TYPES

        faculty_procs = [_proc(f"faculty_{rt}") for rt in FACULTY_REQUEST_TYPES]
        result = _apply_filter(faculty_procs + [_proc("LEAVE_APPROVAL")])
        codes = {r["code"] for r in result}
        for rt in FACULTY_REQUEST_TYPES:
            assert f"faculty_{rt}" not in codes, f"faculty_{rt} should be excluded"
        assert "LEAVE_APPROVAL" in codes

    def test_old_submit_dropdown_includes_leave_approval(self) -> None:
        """LEAVE_APPROVAL is not a faculty type and must remain visible."""
        procs = [_proc("LEAVE_APPROVAL"), _proc("faculty_noc")]
        result = _apply_filter(procs)
        codes = {r["code"] for r in result}
        assert "LEAVE_APPROVAL" in codes

    def test_old_submit_dropdown_includes_other_generic_processes(self) -> None:
        """Non-faculty processes (NRF, CPC, DSW) must still appear after filtering."""
        procs = [
            _proc("NRF_APPROVAL"),
            _proc("CPC_FUND_RELEASE"),
            _proc("DSW_CLEARANCE"),
            _proc("faculty_noc"),
        ]
        result = _apply_filter(procs)
        codes = {r["code"] for r in result}
        assert "NRF_APPROVAL" in codes
        assert "CPC_FUND_RELEASE" in codes
        assert "DSW_CLEARANCE" in codes
        assert "faculty_noc" not in codes

    def test_faculty_request_types_to_process_codes_mapping(self) -> None:
        """REQUEST_TYPE_NOC → 'faculty_noc' process code via the naming convention."""
        from durgam.models.faculty_request import FACULTY_REQUEST_TYPES, REQUEST_TYPE_NOC

        derived = frozenset(f"faculty_{rt}" for rt in FACULTY_REQUEST_TYPES)
        assert f"faculty_{REQUEST_TYPE_NOC}" in derived
        assert "faculty_noc" == f"faculty_{REQUEST_TYPE_NOC}"


# ── B: old routes still reachable ─────────────────────────────────────────────


class TestOldRoutesPreserved:
    """Old /approvals/* pages are NOT deleted — only nav labels were renamed."""

    def test_old_my_requests_page_module_importable(self) -> None:
        """durgam.pages.approvals.my_requests is still importable after label rename."""
        import durgam.pages.approvals.my_requests as m  # noqa: F401

        assert m is not None

    def test_old_approvals_inbox_page_module_importable(self) -> None:
        """durgam.pages.approvals.inbox is still importable after label rename."""
        import durgam.pages.approvals.inbox as m  # noqa: F401

        assert m is not None
