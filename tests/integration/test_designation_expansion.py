"""Integration tests for M10 Phase 1B designation taxonomy expansion.

Verifies the Alembic data migration (cb2de963f0b8) and seed.py update.
Tests use the seeded_db_engine fixture which creates_all + seeds before
the test session starts, so the migration state is tested via the seed.
Migration round-trip is covered in test_migrations.py.
"""

from sqlmodel import Session, func, select

from durgam.models.config_anchors import Designation, PurchaseCommitteeTemplate

_NEW_CODES = {
    "sr_prof",
    "prof",
    "assoc_prof",
    "asst_prof_l10",
    "asst_prof_l11",
    "asst_prof_l12",
    "instructor",
}

_LEGACY_CODES = {
    "senior_professor",
    "professor",
    "associate_professor",
    "assistant_professor",
}


class TestDesignationExpansion:
    def test_seven_new_codes_active(self, seeded_session: Session) -> None:
        """All 7 new designation codes exist and are active after seeding."""
        rows = seeded_session.exec(
            select(Designation).where(Designation.is_deleted == False)  # noqa: E712
        ).all()
        active_codes = {r.code for r in rows}
        missing = _NEW_CODES - active_codes
        assert not missing, f"Missing active designation codes: {missing}"

    def test_four_legacy_codes_not_active(self, seeded_session: Session) -> None:
        """Legacy codes are absent or soft-deleted — none appear as active.

        On a migrated dev DB, legacy rows are soft-deleted (is_deleted=True).
        On a seed-only test DB, legacy rows simply don't exist.
        Both satisfy the invariant: legacy codes are NOT in the active set.
        The migration round-trip (soft-delete ↔ restore) is verified in test_migrations.py.
        """
        rows = seeded_session.exec(
            select(Designation).where(
                Designation.code.in_(list(_LEGACY_CODES)),  # type: ignore[attr-defined]
                Designation.is_deleted == False,  # noqa: E712
            )
        ).all()
        active_legacy = {r.code for r in rows}
        assert not active_legacy, (
            f"Legacy codes still appear as active after seed: {active_legacy}"
        )

    def test_legacy_codes_not_active(self, seeded_session: Session) -> None:
        """Legacy codes do not appear in active designations."""
        rows = seeded_session.exec(
            select(Designation).where(Designation.is_deleted == False)  # noqa: E712
        ).all()
        active_codes = {r.code for r in rows}
        overlap = _LEGACY_CODES & active_codes
        assert not overlap, f"Legacy codes still active: {overlap}"

    def test_pct_eligible_designations_use_new_codes(
        self, seeded_session: Session
    ) -> None:
        """PurchaseCommitteeTemplate.eligible_designations contain only new codes."""
        templates = seeded_session.exec(
            select(PurchaseCommitteeTemplate).where(
                PurchaseCommitteeTemplate.is_deleted == False  # noqa: E712
            )
        ).all()
        assert len(templates) >= 2, "Expected at least 2 PCT rows"
        for tpl in templates:
            codes_in_array = set(tpl.eligible_designations)
            legacy_in_array = _LEGACY_CODES & codes_in_array
            assert not legacy_in_array, (
                f"PCT {tpl.committee_type!r} still has legacy codes: {legacy_in_array}"
            )
            assert codes_in_array.issubset(_NEW_CODES), (
                f"PCT {tpl.committee_type!r} has unknown codes: "
                f"{codes_in_array - _NEW_CODES}"
            )

    def test_seven_new_codes_correct_ranks(self, seeded_session: Session) -> None:
        """Each new designation has the correct rank per the design freeze."""
        expected_ranks = {
            "sr_prof": 1,
            "prof": 2,
            "assoc_prof": 3,
            "asst_prof_l10": 4,
            "asst_prof_l11": 5,
            "asst_prof_l12": 6,
            "instructor": 7,
        }
        rows = seeded_session.exec(
            select(Designation).where(
                Designation.is_deleted == False,  # noqa: E712
                Designation.code.in_(list(_NEW_CODES)),  # type: ignore[attr-defined]
            )
        ).all()
        actual_ranks = {r.code: r.rank for r in rows}
        assert actual_ranks == expected_ranks, (
            f"Rank mismatch: {actual_ranks} != {expected_ranks}"
        )

    def test_seed_idempotent_designation_count(self, db_engine) -> None:
        """Running seed twice does not change the designation count."""
        from scripts.seed import seed

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            count1 = session.exec(
                select(func.count()).select_from(Designation)
            ).one()

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            count2 = session.exec(
                select(func.count()).select_from(Designation)
            ).one()

        assert count1 == count2, (
            f"Designation count changed on second seed run: {count1} -> {count2}"
        )
