"""Integration tests for the M10 Phase 11C faculty picker query path.

Covers FacultyRepository.list_for_picker + FacultyPickerService.search:
search by employee_id / name / title, the four optional filters
(department_id, campus_id, designation_id, employee_type), the 50-row cap,
the display format, active-only filtering, and that NO sensitive/PII column
ever appears in a picker row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.faculty import FacultyRepository
from durgam.services.faculty_picker import PICKER_FIELDS, FacultyPickerService


def _campus(session, code_prefix="C") -> Campus:
    c = Campus(code=f"{code_prefix}{uuid4().hex[:4]}", name="Campus", address="A")
    session.add(c)
    session.flush()
    return c


def _dept(session, campus) -> Department:
    s = School(code=f"S{uuid4().hex[:4]}", name="School")
    session.add(s)
    session.flush()
    d = Department(
        code=f"D{uuid4().hex[:4]}", name="Dept",
        school_id=s.id, main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    return d


def _designation(session, name="Professor") -> Designation:
    d = Designation(code=f"DG{uuid4().hex[:4]}", name=name, rank=50)
    session.add(d)
    session.flush()
    return d


def _faculty(
    session,
    *,
    employee_id=None,
    title="Dr",
    first_name="Alan",
    last_name="Turing",
    campus=None,
    dept=None,
    designation=None,
    employee_type="regular_teaching",
    is_deleted=False,
) -> Faculty:
    campus = campus or _campus(session)
    dept = dept or _dept(session, campus)
    designation = designation or _designation(session)
    user = User(
        username=f"fp_{uuid4().hex[:8]}",
        email=f"fp_{uuid4().hex[:8]}@dev.local",
        password_hash="x",
        employee_type=employee_type,
    )
    session.add(user)
    session.flush()
    now = datetime.now(UTC)
    f = Faculty(
        user_id=user.id,
        employee_id=employee_id or f"FAC-{uuid4().hex[:8]}",
        title=title, first_name=first_name, last_name=last_name,
        designation_id=designation.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2020, 1, 1), phone="9999999999",
        emergency_contact_name="E", emergency_contact_relation="P",
        emergency_contact_phone="8888888888",
        is_deleted=is_deleted, created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _svc(session) -> FacultyPickerService:
    return FacultyPickerService(FacultyRepository(session))


class TestPickerSearch:
    def test_search_by_employee_id_partial_ci(self, db_session):
        _faculty(db_session, employee_id="EMP-ZEBRA-01")
        rows = _svc(db_session).search(search="zebra")
        assert any(r["employee_id"] == "EMP-ZEBRA-01" for r in rows)

    def test_search_by_first_name_partial(self, db_session):
        _faculty(db_session, first_name="Grace", last_name="Hopper")
        rows = _svc(db_session).search(search="grac")
        assert any(r["first_name"] == "Grace" for r in rows)

    def test_search_by_last_name_partial(self, db_session):
        _faculty(db_session, first_name="Edsger", last_name="Dijkstra")
        rows = _svc(db_session).search(search="dijks")
        assert any(r["last_name"] == "Dijkstra" for r in rows)

    def test_search_by_title_partial(self, db_session):
        _faculty(db_session, title="Professor", first_name="Ada", last_name="Lovelace")
        rows = _svc(db_session).search(search="profess")
        assert any(r["first_name"] == "Ada" for r in rows)

    def test_empty_search_returns_rows(self, db_session):
        _faculty(db_session)
        rows = _svc(db_session).search(search=None)
        assert len(rows) >= 1


class TestPickerFilters:
    def test_filter_by_department_id(self, db_session):
        campus = _campus(db_session)
        dept_a = _dept(db_session, campus)
        dept_b = _dept(db_session, campus)
        fa = _faculty(db_session, campus=campus, dept=dept_a)
        _faculty(db_session, campus=campus, dept=dept_b)
        rows = _svc(db_session).search(department_id=dept_a.id)
        ids = {r["id"] for r in rows}
        assert str(fa.id) in ids
        assert all(r["id"] != "" for r in rows)
        # Only dept_a faculty returned.
        from uuid import UUID
        for r in rows:
            fac = db_session.get(Faculty, UUID(r["id"]))
            assert fac.department_id == dept_a.id

    def test_filter_by_campus_id(self, db_session):
        campus_a = _campus(db_session)
        campus_b = _campus(db_session)
        fa = _faculty(db_session, campus=campus_a)
        _faculty(db_session, campus=campus_b)
        rows = _svc(db_session).search(campus_id=campus_a.id)
        assert str(fa.id) in {r["id"] for r in rows}
        from uuid import UUID
        for r in rows:
            assert db_session.get(Faculty, UUID(r["id"])).campus_id == campus_a.id

    def test_filter_by_designation_id(self, db_session):
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig_a = _designation(db_session, name="Assoc Prof")
        desig_b = _designation(db_session, name="Asst Prof")
        fa = _faculty(db_session, campus=campus, dept=dept, designation=desig_a)
        _faculty(db_session, campus=campus, dept=dept, designation=desig_b)
        rows = _svc(db_session).search(designation_id=desig_a.id)
        assert str(fa.id) in {r["id"] for r in rows}
        from uuid import UUID
        for r in rows:
            assert db_session.get(Faculty, UUID(r["id"])).designation_id == desig_a.id

    def test_filter_by_employee_type(self, db_session):
        tag = uuid4().hex[:8]
        teaching = _faculty(
            db_session, employee_id=f"ET-T-{tag}", employee_type="regular_teaching"
        )
        _faculty(
            db_session, employee_id=f"ET-N-{tag}", employee_type="regular_non_teaching"
        )
        rows = _svc(db_session).search(
            search=tag, employee_type="regular_teaching"
        )
        emp_ids = {r["employee_id"] for r in rows}
        assert teaching.employee_id in emp_ids
        assert f"ET-N-{tag}" not in emp_ids


class TestPickerCapAndShape:
    def test_caps_at_50(self, db_session):
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _designation(db_session)
        tag = uuid4().hex[:6]
        for i in range(55):
            _faculty(
                db_session, employee_id=f"CAP-{tag}-{i:03d}",
                campus=campus, dept=dept, designation=desig,
            )
        rows = _svc(db_session).search(search=f"cap-{tag}", limit=1000)
        assert len(rows) == 50

    def test_display_format(self, db_session):
        f = _faculty(
            db_session, employee_id="EMP-DISP-1",
            title="Dr", first_name="Marie", last_name="Curie",
        )
        rows = _svc(db_session).search(search="EMP-DISP-1")
        match = next(r for r in rows if r["employee_id"] == "EMP-DISP-1")
        assert match["display"] == "EMP-DISP-1 — Dr Marie Curie"
        assert match["id"] == str(f.id)

    def test_active_only(self, db_session):
        tag = uuid4().hex[:8]
        _faculty(db_session, employee_id=f"DEL-{tag}", is_deleted=True)
        rows = _svc(db_session).search(search=tag)
        assert all(r["employee_id"] != f"DEL-{tag}" for r in rows)

    def test_rows_carry_only_picker_fields(self, db_session):
        _faculty(db_session, employee_id="EMP-SHAPE-1")
        rows = _svc(db_session).search(search="EMP-SHAPE-1")
        assert rows
        for r in rows:
            assert set(r.keys()) == set(PICKER_FIELDS)

    def test_no_pii_in_rows(self, db_session):
        """Picker rows must never carry phone / emergency-contact / PII fields."""
        _faculty(db_session, employee_id="EMP-PII-1", first_name="Secret")
        rows = _svc(db_session).search(search="EMP-PII-1")
        forbidden = {
            "phone", "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation", "aadhaar_enc", "pan_enc",
            "password_hash", "user_id",
        }
        for r in rows:
            assert forbidden.isdisjoint(r.keys())
