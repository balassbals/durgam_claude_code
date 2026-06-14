"""TD-068 regression — seeding twice on a fresh DB must yield identical user count.

Distinct from test_seed.py::test_second_run_inserts_zero_rows which checks INSERT
delta counts but explicitly excludes users (because users use on_conflict_do_update,
which always returns a row count). This test checks ACTUAL DB row count equality.
"""

from sqlmodel import Session, func, select

from durgam.models.identity import User


def test_seed_idempotent_user_count(db_engine):
    """User count must be identical after a second seed run.

    The user-create path uses on_conflict_do_update(constraint="uq_users_email")
    so the second run updates each user rather than inserting new rows.
    This test verifies the total user count in the DB is unchanged.
    """
    from scripts.seed import seed

    with Session(db_engine) as s:
        seed(s)
        s.commit()

    with Session(db_engine) as s:
        count_after_first = s.exec(select(func.count()).select_from(User)).one()

    with Session(db_engine) as s:
        seed(s)
        s.commit()

    with Session(db_engine) as s:
        count_after_second = s.exec(select(func.count()).select_from(User)).one()

    assert count_after_first == count_after_second, (
        f"TD-068 regression: user count changed across seed re-runs "
        f"({count_after_first} → {count_after_second}). "
        "Some user-create path is missing on_conflict_do_update/do_nothing."
    )
