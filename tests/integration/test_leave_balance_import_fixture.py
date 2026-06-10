"""Integration test — fixture CSV vs seeded DB contract (M8.1 Phase 4.1).

Pins the fixture-vs-seed contract: if a future milestone removes a seeded user
referenced by the fixture, this test fails immediately rather than silently
producing a broken walkthrough file.

Uses db_session (function-scoped, rolls back after test) + inline seed call,
matching the pattern in test_seed.py::test_first_run_inserts_expected_rows.
This avoids triggering seeded_db_engine early and corrupting the shared DB for
other db_session tests (seeded_db_engine calls drop_all on the same DB).
"""
from __future__ import annotations

from pathlib import Path

from durgam.services.leave_balance_import import LeaveBalanceImportService

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "leave_balance_import_sample.csv"


def test_sample_fixture_against_fresh_seed(db_session) -> None:
    """Fixture CSV must yield exactly 8 valid rows and 2 invalid rows against seed data."""
    from scripts.seed import seed

    seed(db_session)
    db_session.commit()

    csv_text = _FIXTURE.read_text(encoding="utf-8")
    svc = LeaveBalanceImportService(db_session)
    result = svc.validate(csv_text)

    assert len(result.valid_rows) == 8, (
        f"Expected 8 valid rows, got {len(result.valid_rows)}: "
        + str([(r.employee_username, r.error_reason) for r in result.invalid_rows])
    )
    assert len(result.invalid_rows) == 2, (
        f"Expected 2 invalid rows, got {len(result.invalid_rows)}: "
        + str([(r.employee_username, r.error_reason) for r in result.invalid_rows])
    )

    reasons = {r.employee_username: r.error_reason for r in result.invalid_rows}

    # Row 9: nonexistent username
    assert "nonexistent_import_xyz" in reasons
    assert "unknown employee_username" in reasons["nonexistent_import_xyz"]

    # Row 10: negative opening_balance for ahod_dmacs
    assert "ahod_dmacs" in reasons
    assert "negative value" in reasons["ahod_dmacs"]
