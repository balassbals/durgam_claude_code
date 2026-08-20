"""Integration tests for the /api/faculty/picker endpoint (M10 Phase 11C).

Proves:
  1. No session cookie → 403
  2. Valid session but no picker permission → 403
  3. Valid session + write on any of the 5 assignment resources → 200
  4. Search by employee_id / name
  5. Filters: department_id, campus_id, designation_id, employee_type
  6. Caps at 50 results
  7. display field formatted "<employee_id> — <title> <first> <last>"
  8. Response carries ONLY picker fields — no aadhaar_enc / pan_enc /
     password_hash / phone / emergency-contact / user_id
"""

import hashlib
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, select
from starlette.testclient import TestClient

import durgam.db as _db_mod
from durgam.models.auth import UserSession
from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from durgam.models.school import School


@pytest.fixture()
def _patch_engine(db_engine, monkeypatch):
    monkeypatch.setattr(_db_mod, "_engine", db_engine)


@pytest.fixture()
def real_api_client() -> TestClient:
    from durgam.durgam import app

    return TestClient(app._api)


def _user(session: Session, *, employee_type="regular_teaching") -> User:
    u = User(
        username=f"fpe_{uuid4().hex[:8]}",
        email=f"fpe_{uuid4().hex[:8]}@dev.local",
        password_hash="not-a-real-hash",
        employee_type=employee_type,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _session_row(session: Session, user_id, raw_token: str) -> None:
    now = datetime.now(UTC)
    session.add(
        UserSession(
            user_id=user_id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            created_at=now,
            last_active_at=now,
            expires_at=now + timedelta(days=7),
            is_invalidated=False,
        )
    )
    session.flush()


def _grant_write(session: Session, user_id, resource: str) -> None:
    role = Role(name=f"FP {resource}", code=f"FP_{uuid4().hex[:8]}", level=999)
    session.add(role)
    session.flush()
    perm = session.exec(
        select(Permission).where(
            Permission.resource == resource,
            Permission.action == "write",
            Permission.scope == "*",
        )
    ).first()
    if perm is None:
        perm = Permission(resource=resource, action="write", scope="*")
        session.add(perm)
        session.flush()
    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.add(UserRole(user_id=user_id, role_id=role.id))
    session.flush()


def _campus(session) -> Campus:
    c = Campus(code=f"C{uuid4().hex[:8]}", name="Campus", address="A")
    session.add(c)
    session.flush()
    return c


def _dept(session, campus) -> Department:
    s = School(code=f"S{uuid4().hex[:8]}", name="School")
    session.add(s)
    session.flush()
    d = Department(
        code=f"D{uuid4().hex[:8]}", name="Dept",
        school_id=s.id, main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    return d


def _faculty(
    session, *, employee_id=None, title="Dr", first_name="Alan",
    last_name="Turing", campus=None, dept=None, designation=None,
    employee_type="regular_teaching",
) -> Faculty:
    campus = campus or _campus(session)
    dept = dept or _dept(session, campus)
    if designation is None:
        designation = Designation(code=f"DG{uuid4().hex[:8]}", name="Prof", rank=50)
        session.add(designation)
        session.flush()
    owner = _user(session, employee_type=employee_type)
    now = datetime.now(UTC)
    f = Faculty(
        user_id=owner.id, employee_id=employee_id or f"FAC-{uuid4().hex[:8]}",
        title=title, first_name=first_name, last_name=last_name,
        designation_id=designation.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2020, 1, 1), phone="9999999999",
        emergency_contact_name="ICE", emergency_contact_relation="P",
        emergency_contact_phone="8888888888", created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _authed(session, resource="faculty_mentor_assignment") -> str:
    user = _user(session)
    raw_token = uuid4().hex
    _session_row(session, user.id, raw_token)
    _grant_write(session, user.id, resource)
    return raw_token


@pytest.mark.usefixtures("_patch_engine")
class TestFacultyPickerEndpoint:
    def test_no_session_returns_403(self, db_engine, real_api_client):
        resp = real_api_client.get("/api/faculty/picker")
        assert resp.status_code == 403

    def test_no_permission_returns_403(self, db_engine, real_api_client):
        with Session(db_engine) as session:
            user = _user(session)
            raw_token = uuid4().hex
            _session_row(session, user.id, raw_token)
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker", cookies={"dsession": raw_token}
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "resource",
        [
            "faculty_mentor_assignment",
            "class_teacher_assignment",
            "non_owned_course",
            "ug_timetable",
        ],
    )
    def test_any_of_four_write_perms_authorizes(
        self, db_engine, real_api_client, resource
    ):
        with Session(db_engine) as session:
            raw_token = _authed(session, resource)
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker", cookies={"dsession": raw_token}
        )
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_search_by_employee_id(self, db_engine, real_api_client):
        with Session(db_engine) as session:
            raw_token = _authed(session)
            _faculty(session, employee_id="EMP-ENDP-77")
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"search": "endp-77"},
            cookies={"dsession": raw_token},
        )
        assert resp.status_code == 200
        emp_ids = {r["employee_id"] for r in resp.json()["results"]}
        assert "EMP-ENDP-77" in emp_ids

    def test_search_by_name(self, db_engine, real_api_client):
        with Session(db_engine) as session:
            raw_token = _authed(session)
            _faculty(session, first_name="Katherine", last_name="Johnson")
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"search": "katherin"},
            cookies={"dsession": raw_token},
        )
        names = {r["first_name"] for r in resp.json()["results"]}
        assert "Katherine" in names

    def test_filter_by_campus_and_department(self, db_engine, real_api_client):
        # Positive-control discrimination: within ONE campus, a faculty in dept_a
        # (matches BOTH filters) must be returned and a faculty in dept_b (matches
        # campus only) must be EXCLUDED — proving the department filter combines
        # with the campus filter rather than passing vacuously on the target alone.
        # High-entropy inline codes (uuid4().hex[:8]) avoid uq-code collisions in the
        # shared, never-rolled-back durgam_test; a unique employee_id tag scopes the
        # query so accumulated committed faculty in the test DB cannot interfere.
        tag = uuid4().hex[:8]
        with Session(db_engine) as session:
            raw_token = _authed(session)
            campus = Campus(code=f"C{uuid4().hex[:8]}", name="Campus", address="A")
            school = School(code=f"S{uuid4().hex[:8]}", name="School")
            session.add_all([campus, school])
            session.flush()
            dept_a = Department(
                code=f"DA{uuid4().hex[:7]}", name="DeptA",
                school_id=school.id, main_campus_id=campus.id,
            )
            dept_b = Department(
                code=f"DB{uuid4().hex[:7]}", name="DeptB",
                school_id=school.id, main_campus_id=campus.id,
            )
            desig = Designation(code=f"DG{uuid4().hex[:8]}", name="Prof", rank=50)
            session.add_all([dept_a, dept_b, desig])
            session.flush()
            target = _faculty(
                session, employee_id=f"MATCH-{tag}",
                campus=campus, dept=dept_a, designation=desig,
            )
            _faculty(
                session, employee_id=f"CAMPUSONLY-{tag}",
                campus=campus, dept=dept_b, designation=desig,
            )
            session.commit()
            campus_id, dept_id, target_id = str(campus.id), str(dept_a.id), str(target.id)
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={
                "campus_id": campus_id, "department_id": dept_id, "search": tag,
            },
            cookies={"dsession": raw_token},
        )
        results = resp.json()["results"]
        ids = {r["id"] for r in results}
        emp_ids = {r["employee_id"] for r in results}
        assert target_id in ids, (
            f"faculty matching campus+dept must be returned; got {sorted(emp_ids)}"
        )
        assert f"CAMPUSONLY-{tag}" not in emp_ids, (
            "faculty in a different department (same campus) must be excluded; "
            f"got {sorted(emp_ids)}"
        )

    def test_filter_by_designation(self, db_engine, real_api_client):
        with Session(db_engine) as session:
            raw_token = _authed(session)
            campus = _campus(session)
            dept = _dept(session, campus)
            desig = Designation(code=f"DG{uuid4().hex[:4]}", name="Reader", rank=40)
            session.add(desig)
            session.flush()
            target = _faculty(session, campus=campus, dept=dept, designation=desig)
            _faculty(session, campus=campus, dept=dept)
            session.commit()
            desig_id, target_id = str(desig.id), str(target.id)
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"designation_id": desig_id},
            cookies={"dsession": raw_token},
        )
        assert {r["id"] for r in resp.json()["results"]} == {target_id}

    def test_filter_by_employee_type(self, db_engine, real_api_client):
        tag = uuid4().hex[:8]
        with Session(db_engine) as session:
            raw_token = _authed(session)
            _faculty(
                session, employee_id=f"ET-T-{tag}",
                employee_type="regular_teaching",
            )
            _faculty(
                session, employee_id=f"ET-N-{tag}",
                employee_type="regular_non_teaching",
            )
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"search": tag, "employee_type": "regular_teaching"},
            cookies={"dsession": raw_token},
        )
        emp_ids = {r["employee_id"] for r in resp.json()["results"]}
        assert f"ET-T-{tag}" in emp_ids
        assert f"ET-N-{tag}" not in emp_ids

    def test_caps_at_50(self, db_engine, real_api_client):
        tag = uuid4().hex[:6]
        with Session(db_engine) as session:
            raw_token = _authed(session)
            campus = _campus(session)
            dept = _dept(session, campus)
            desig = Designation(code=f"DG{uuid4().hex[:4]}", name="Prof", rank=50)
            session.add(desig)
            session.flush()
            for i in range(55):
                _faculty(
                    session, employee_id=f"CAP-{tag}-{i:03d}",
                    campus=campus, dept=dept, designation=desig,
                )
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"search": f"cap-{tag}"},
            cookies={"dsession": raw_token},
        )
        assert len(resp.json()["results"]) == 50

    def test_display_field(self, db_engine, real_api_client):
        with Session(db_engine) as session:
            raw_token = _authed(session)
            _faculty(
                session, employee_id="EMP-DISP-9",
                title="Dr", first_name="Rosalind", last_name="Franklin",
            )
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"search": "EMP-DISP-9"},
            cookies={"dsession": raw_token},
        )
        row = next(
            r for r in resp.json()["results"] if r["employee_id"] == "EMP-DISP-9"
        )
        assert row["display"] == "EMP-DISP-9 — Dr Rosalind Franklin"

    def test_response_excludes_sensitive_fields(self, db_engine, real_api_client):
        with Session(db_engine) as session:
            raw_token = _authed(session)
            _faculty(session, employee_id="EMP-SEC-1")
            session.commit()
        resp = real_api_client.get(
            "/api/faculty/picker",
            params={"search": "EMP-SEC-1"},
            cookies={"dsession": raw_token},
        )
        body = resp.text
        for forbidden in (
            "aadhaar_enc", "pan_enc", "password_hash", "phone",
            "emergency_contact", "user_id",
        ):
            assert forbidden not in body
        for row in resp.json()["results"]:
            assert set(row.keys()) == {
                "id", "employee_id", "title", "first_name", "last_name", "display",
            }
