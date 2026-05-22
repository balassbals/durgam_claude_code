"""Integration tests for M4 repositories against real PostgreSQL.

Covers: AcademicYear CRUD and lock methods, CalendarEntry/Holiday/StudentCategoryCount
CRUD with AY-locked enforcement, FK constraints, soft-delete filtering, unique constraints.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from durgam.models.config_anchors import (
    AcademicYear,
    CalendarEntry,
    Holiday,
    StudentCategoryCount,
)
from durgam.models.identity import User
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.calendar_entry import CalendarEntryRepository
from durgam.repositories.holiday import HolidayRepository
from durgam.repositories.student_category_count import StudentCategoryCountRepository
from durgam.services.org_exceptions import AcademicYearLockedError


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ay(session, *, code: str | None = None, locked: bool = False) -> AcademicYear:
    uid = code or f"T{uuid4().hex[:4]}"
    ay = AcademicYear(
        code=uid,
        starts_on=date(2025, 7, 1),
        ends_on=date(2026, 4, 30),
        is_locked=locked,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _user(session) -> User:
    from durgam.services.password import hash_password

    u = User(
        username=f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.com",
        full_name="Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _entry(session, ay: AcademicYear, user: User) -> CalendarEntry:
    now = datetime.now(UTC)
    e = CalendarEntry(
        academic_year_id=ay.id,
        title=f"Entry {uuid4().hex[:6]}",
        entry_type="master",
        starts_at=now,
        ends_at=now + timedelta(hours=2),
        owner_user_id=user.id,
        owner_role_code="REGISTRAR",
    )
    session.add(e)
    session.flush()
    session.refresh(e)
    return e


def _holiday(session, ay: AcademicYear) -> Holiday:
    h = Holiday(
        academic_year_id=ay.id,
        holiday_date=date(2025, 8, 15),
        name=f"Holiday {uuid4().hex[:6]}",
    )
    session.add(h)
    session.flush()
    session.refresh(h)
    return h


def _scc(session, ay: AcademicYear) -> StudentCategoryCount:
    s = StudentCategoryCount(
        academic_year_id=ay.id,
        sc_count=10,
        st_count=5,
        obc_count=20,
        ews_count=8,
        general_count=100,
    )
    session.add(s)
    session.flush()
    session.refresh(s)
    return s


# ── AcademicYear ─────────────────────────────────────────────────────────────


class TestAcademicYearRepository:
    def test_list_active_ordered_by_starts_on_desc(self, db_session):
        ay1 = AcademicYear(
            code="AY-A", starts_on=date(2024, 7, 1), ends_on=date(2025, 4, 30)
        )
        ay2 = AcademicYear(
            code="AY-B", starts_on=date(2025, 7, 1), ends_on=date(2026, 4, 30)
        )
        db_session.add_all([ay1, ay2])
        db_session.flush()

        repo = AcademicYearRepository(db_session)
        result = repo.list_active()
        codes = [a.code for a in result]
        assert codes.index("AY-B") < codes.index("AY-A")

    def test_get_by_code(self, db_session):
        ay = _ay(db_session, code="GBC-1")
        repo = AcademicYearRepository(db_session)
        assert repo.get_by_code("GBC-1") is not None
        assert repo.get_by_code("GBC-1").id == ay.id
        assert repo.get_by_code("NONEXISTENT") is None

    def test_get_by_code_excludes_deleted(self, db_session):
        ay = _ay(db_session, code="GBD-1")
        repo = AcademicYearRepository(db_session)
        repo.soft_delete(ay, actor_id=uuid4())
        assert repo.get_by_code("GBD-1") is None

    def test_lock_master_calendar(self, db_session):
        ay = _ay(db_session)
        assert ay.master_calendar_locked is False
        repo = AcademicYearRepository(db_session)
        updated = repo.lock_master_calendar(ay.id)
        assert updated.master_calendar_locked is True

    def test_lock_for_rollover(self, db_session):
        ay = _ay(db_session)
        assert ay.is_locked is False
        repo = AcademicYearRepository(db_session)
        updated = repo.lock_for_rollover(ay.id)
        assert updated.is_locked is True

    def test_list_expired_unlocked(self, db_session):
        past = AcademicYear(
            code="EXP-1", starts_on=date(2023, 7, 1), ends_on=date(2024, 4, 30)
        )
        future = AcademicYear(
            code="FUT-1", starts_on=date(2025, 7, 1), ends_on=date(2026, 4, 30)
        )
        locked = AcademicYear(
            code="LCK-1",
            starts_on=date(2022, 7, 1),
            ends_on=date(2023, 4, 30),
            is_locked=True,
        )
        db_session.add_all([past, future, locked])
        db_session.flush()

        repo = AcademicYearRepository(db_session)
        expired = repo.list_expired_unlocked(as_of=date(2025, 5, 1))
        codes = [a.code for a in expired]
        assert "EXP-1" in codes
        assert "FUT-1" not in codes
        assert "LCK-1" not in codes

    def test_unique_code_enforced(self, db_session):
        _ay(db_session, code="UNQ-1")
        with pytest.raises(Exception):
            db_session.add(
                AcademicYear(
                    code="UNQ-1", starts_on=date(2024, 7, 1), ends_on=date(2025, 4, 30)
                )
            )
            db_session.flush()

    def test_lock_nonexistent_raises(self, db_session):
        repo = AcademicYearRepository(db_session)
        with pytest.raises(ValueError, match="not found"):
            repo.lock_master_calendar(uuid4())


# ── CalendarEntry ────────────────────────────────────────────────────────────


class TestCalendarEntryRepository:
    def test_list_by_ay_ordered_by_starts_at(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        now = datetime.now(UTC)

        e1 = CalendarEntry(
            academic_year_id=ay.id,
            title="Later",
            entry_type="master",
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=4),
            owner_user_id=user.id,
            owner_role_code="REGISTRAR",
        )
        e2 = CalendarEntry(
            academic_year_id=ay.id,
            title="Earlier",
            entry_type="master",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            owner_user_id=user.id,
            owner_role_code="REGISTRAR",
        )
        db_session.add_all([e1, e2])
        db_session.flush()

        repo = CalendarEntryRepository(db_session)
        result = repo.list_by_ay(ay.id)
        assert len(result) == 2
        assert result[0].title == "Earlier"
        assert result[1].title == "Later"

    def test_list_by_ay_and_type(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        now = datetime.now(UTC)

        for etype in ("master", "activity", "sports"):
            db_session.add(
                CalendarEntry(
                    academic_year_id=ay.id,
                    title=f"{etype} entry",
                    entry_type=etype,
                    starts_at=now,
                    ends_at=now + timedelta(hours=1),
                    owner_user_id=user.id,
                    owner_role_code="REGISTRAR",
                )
            )
        db_session.flush()

        repo = CalendarEntryRepository(db_session)
        masters = repo.list_by_ay_and_type(ay.id, "master")
        assert len(masters) == 1
        assert masters[0].entry_type == "master"

    def test_list_by_ay_and_owner(self, db_session):
        ay = _ay(db_session)
        u1 = _user(db_session)
        u2 = _user(db_session)

        _entry(db_session, ay, u1)
        _entry(db_session, ay, u2)

        repo = CalendarEntryRepository(db_session)
        u1_entries = repo.list_by_ay_and_owner(ay.id, u1.id)
        assert len(u1_entries) == 1
        assert u1_entries[0].owner_user_id == u1.id

    def test_soft_delete_excludes_from_list(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        entry = _entry(db_session, ay, user)

        repo = CalendarEntryRepository(db_session)
        repo.soft_delete(entry, actor_id=user.id)
        assert len(repo.list_by_ay(ay.id)) == 0

    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        user = _user(db_session)
        now = datetime.now(UTC)

        entry = CalendarEntry(
            academic_year_id=ay.id,
            title="Should fail",
            entry_type="master",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            owner_user_id=user.id,
            owner_role_code="REGISTRAR",
        )
        repo = CalendarEntryRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(entry)

    def test_soft_delete_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        entry = _entry(db_session, ay, user)

        # Lock the AY after creating the entry
        ay.is_locked = True
        db_session.flush()

        repo = CalendarEntryRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.soft_delete(entry, actor_id=user.id)

    def test_save_on_unlocked_ay_succeeds(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        now = datetime.now(UTC)

        entry = CalendarEntry(
            academic_year_id=ay.id,
            title="Should succeed",
            entry_type="activity",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            owner_user_id=user.id,
            owner_role_code="IQAC_COORDINATOR",
        )
        repo = CalendarEntryRepository(db_session)
        saved = repo.save(entry)
        assert saved.id is not None
        assert saved.title == "Should succeed"

    def test_fk_requires_valid_ay(self, db_session):
        user = _user(db_session)
        now = datetime.now(UTC)
        with pytest.raises(Exception):
            db_session.add(
                CalendarEntry(
                    academic_year_id=uuid4(),
                    title="Bad FK",
                    entry_type="master",
                    starts_at=now,
                    ends_at=now + timedelta(hours=1),
                    owner_user_id=user.id,
                    owner_role_code="REGISTRAR",
                )
            )
            db_session.flush()

    def test_fk_requires_valid_user(self, db_session):
        ay = _ay(db_session)
        now = datetime.now(UTC)
        with pytest.raises(Exception):
            db_session.add(
                CalendarEntry(
                    academic_year_id=ay.id,
                    title="Bad FK",
                    entry_type="master",
                    starts_at=now,
                    ends_at=now + timedelta(hours=1),
                    owner_user_id=uuid4(),
                    owner_role_code="REGISTRAR",
                )
            )
            db_session.flush()


# ── Holiday ──────────────────────────────────────────────────────────────────


class TestHolidayRepository:
    def test_list_by_ay_ordered_by_date(self, db_session):
        ay = _ay(db_session)
        h1 = Holiday(
            academic_year_id=ay.id, holiday_date=date(2025, 10, 2), name="Gandhi Jayanti"
        )
        h2 = Holiday(
            academic_year_id=ay.id, holiday_date=date(2025, 8, 15), name="Independence Day"
        )
        db_session.add_all([h1, h2])
        db_session.flush()

        repo = HolidayRepository(db_session)
        result = repo.list_by_ay(ay.id)
        assert len(result) == 2
        assert result[0].name == "Independence Day"
        assert result[1].name == "Gandhi Jayanti"

    def test_get_by_date_and_ay(self, db_session):
        ay = _ay(db_session)
        h = _holiday(db_session, ay)
        repo = HolidayRepository(db_session)
        found = repo.get_by_date_and_ay(h.holiday_date, ay.id)
        assert found is not None
        assert found.id == h.id

    def test_get_by_date_and_ay_returns_none_for_wrong_date(self, db_session):
        ay = _ay(db_session)
        _holiday(db_session, ay)
        repo = HolidayRepository(db_session)
        assert repo.get_by_date_and_ay(date(2099, 1, 1), ay.id) is None

    def test_soft_delete_excludes(self, db_session):
        ay = _ay(db_session)
        h = _holiday(db_session, ay)
        repo = HolidayRepository(db_session)
        repo.soft_delete(h, actor_id=uuid4())
        assert len(repo.list_by_ay(ay.id)) == 0

    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        h = Holiday(
            academic_year_id=ay.id,
            holiday_date=date(2025, 12, 25),
            name="Christmas",
        )
        repo = HolidayRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(h)

    def test_soft_delete_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        h = _holiday(db_session, ay)
        ay.is_locked = True
        db_session.flush()

        repo = HolidayRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.soft_delete(h, actor_id=uuid4())

    def test_unique_date_ay_enforced(self, db_session):
        ay = _ay(db_session)
        db_session.add(
            Holiday(
                academic_year_id=ay.id, holiday_date=date(2025, 8, 15), name="Holiday A"
            )
        )
        db_session.flush()
        with pytest.raises(Exception):
            db_session.add(
                Holiday(
                    academic_year_id=ay.id,
                    holiday_date=date(2025, 8, 15),
                    name="Holiday B",
                )
            )
            db_session.flush()

    def test_fk_requires_valid_ay(self, db_session):
        with pytest.raises(Exception):
            db_session.add(
                Holiday(
                    academic_year_id=uuid4(),
                    holiday_date=date(2025, 8, 15),
                    name="Bad FK",
                )
            )
            db_session.flush()


# ── StudentCategoryCount ─────────────────────────────────────────────────────


class TestStudentCategoryCountRepository:
    def test_get_by_ay(self, db_session):
        ay = _ay(db_session)
        scc = _scc(db_session, ay)
        repo = StudentCategoryCountRepository(db_session)
        found = repo.get_by_ay(ay.id)
        assert found is not None
        assert found.id == scc.id
        assert found.sc_count == 10

    def test_get_by_ay_returns_none_when_missing(self, db_session):
        ay = _ay(db_session)
        repo = StudentCategoryCountRepository(db_session)
        assert repo.get_by_ay(ay.id) is None

    def test_save_on_unlocked_ay_succeeds(self, db_session):
        ay = _ay(db_session)
        scc = StudentCategoryCount(
            academic_year_id=ay.id,
            sc_count=5,
            st_count=3,
            obc_count=10,
            ews_count=2,
            general_count=50,
        )
        repo = StudentCategoryCountRepository(db_session)
        saved = repo.save(scc)
        assert saved.id is not None

    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        scc = StudentCategoryCount(
            academic_year_id=ay.id,
            sc_count=5,
            st_count=3,
            obc_count=10,
            ews_count=2,
            general_count=50,
        )
        repo = StudentCategoryCountRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(scc)

    def test_update_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        scc = _scc(db_session, ay)
        ay.is_locked = True
        db_session.flush()

        scc.sc_count = 999
        repo = StudentCategoryCountRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(scc)

    def test_unique_ay_enforced(self, db_session):
        ay = _ay(db_session)
        _scc(db_session, ay)
        with pytest.raises(Exception):
            db_session.add(
                StudentCategoryCount(
                    academic_year_id=ay.id,
                    sc_count=0,
                    st_count=0,
                    obc_count=0,
                    ews_count=0,
                    general_count=0,
                )
            )
            db_session.flush()

    def test_get_by_ay_excludes_deleted(self, db_session):
        ay = _ay(db_session)
        scc = _scc(db_session, ay)
        scc.is_deleted = True
        db_session.flush()

        repo = StudentCategoryCountRepository(db_session)
        assert repo.get_by_ay(ay.id) is None
