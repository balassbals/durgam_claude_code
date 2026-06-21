"""Phase 10B (Q-P10) — HoD recommend-via live wiring, against real PostgreSQL.

Covers: designation/employee-type-keyed matrix matching with persisted rules
(new columns round-trip), the resolver-stage routing (dept_head_at_requestor_campus
dispatched by the engine), and LeaveRequestService's applicant-designation lookup.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import ApprovalProcess
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import Role, User, UserRole
from durgam.models.leave import LeaveSanctionAuthorityRule
from durgam.models.school import School
from durgam.repositories.leave import LeaveSanctionRuleRepository
from durgam.services.approval_request import ApprovalRequestService
from durgam.services.leave_request import LeaveRequestService
from durgam.services.leave_rules import resolve_channel


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _org(session: Session):
    uid = uuid4().hex[:6]
    campus = Campus(code=f"BC{uid}", name="BC")
    session.add(campus)
    session.flush()
    school = School(code=f"BS{uid}", name="BS")
    session.add(school)
    session.flush()
    dept = Department(code=f"BDP{uid}", name="BD", school_id=school.id, main_campus_id=campus.id)
    session.add(dept)
    session.flush()
    return campus, dept


def _designation(session: Session, code: str) -> Designation:
    existing = session.exec(
        select(Designation).where(Designation.code == code)
    ).first()
    if existing:
        return existing
    d = Designation(code=code, name=code.title(), rank=50)
    session.add(d)
    session.flush()
    return d


def _faculty(session, *, campus, dept, desig, user=None) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)
    if user is None:
        user = User(
            username=f"b10b_{uid}", email=f"b10b_{uid}@dev.local",
            password_hash="x", is_active=True, employee_type="regular_teaching",
        )
        session.add(user)
        session.flush()
    f = Faculty(
        user_id=user.id, employee_id=f"B10B-{uid}", title="Dr",
        first_name="B", last_name="Ten",
        designation_id=desig.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2020, 1, 1), phone="9", emergency_contact_name="E",
        emergency_contact_relation="P", emergency_contact_phone="9",
        created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f, user


def _hod_role(session: Session) -> Role:
    existing = session.exec(select(Role).where(Role.code == "HOD")).first()
    if existing:
        return existing
    r = Role(code="HOD", name="HoD", level=40)
    session.add(r)
    session.flush()
    return r


def _persist_rule(session, **kw) -> LeaveSanctionAuthorityRule:
    now = datetime.now(UTC)
    defaults = dict(
        leave_type="CL", applicant_role_code="FACULTY", sanctioner_role_code="DIRECTOR",
        priority=25, scope_type="campus", requires_in_charge=False, requires_optin=False,
        created_at=now, updated_at=now,
    )
    defaults.update(kw)
    rule = LeaveSanctionAuthorityRule(**defaults)
    return LeaveSanctionRuleRepository(session).save(rule)


# ── Matcher + DB round-trip ────────────────────────────────────────────────────


class TestPersistedDesignationKeying:
    def test_designation_rule_round_trips_and_matches(self, db_session: Session) -> None:
        _persist_rule(
            db_session,
            applicant_designation_codes=["asst_prof_l10", "instructor"],
            recommend_via_resolver="dept_head_at_requestor_campus",
        )
        _persist_rule(db_session, priority=30)  # generic fallback
        rules = LeaveSanctionRuleRepository(db_session).list_active()
        ch = resolve_channel(
            ["FACULTY"], "CL", rules, applicant_designation_code="asst_prof_l10"
        )
        assert ch[0]["resolver_name"] == "dept_head_at_requestor_campus"
        assert ch[0]["recommend_only"] is True
        assert ch[-1]["role_code"] == "DIRECTOR"

    def test_optin_rule_round_trips_and_gates(self, db_session: Session) -> None:
        _persist_rule(
            db_session, priority=27,
            applicant_designation_codes=["prof"],
            recommend_via_resolver="dept_head_at_requestor_campus",
            requires_optin=True,
        )
        _persist_rule(db_session, priority=30)
        rules = LeaveSanctionRuleRepository(db_session).list_active()
        # prof WITHOUT optin → no HoD prepend
        ch_off = resolve_channel(
            ["FACULTY"], "CL", rules, applicant_designation_code="prof", optin=False
        )
        assert len(ch_off) == 1
        # prof WITH optin → HoD prepend
        ch_on = resolve_channel(
            ["FACULTY"], "CL", rules, applicant_designation_code="prof", optin=True
        )
        assert ch_on[0]["resolver_name"] == "dept_head_at_requestor_campus"


# ── Resolver-stage routing (Q-P10.3) ───────────────────────────────────────────


class TestResolverStageRouting:
    def test_engine_dispatches_resolver_to_find_hod(self, db_session: Session) -> None:
        campus, dept = _org(db_session)
        desig = _designation(db_session, f"d10b_{uuid4().hex[:5]}")

        # Requestor faculty (dept D, campus C)
        _req_fac, requestor = _faculty(db_session, campus=campus, dept=dept, desig=desig)
        # HoD: faculty at same campus + HOD role scoped to dept D
        _hod_fac, hod_user = _faculty(db_session, campus=campus, dept=dept, desig=desig)
        hod_role = _hod_role(db_session)
        db_session.add(UserRole(
            user_id=hod_user.id, role_id=hod_role.id,
            scope_type="department", scope_id=dept.id,
        ))
        db_session.flush()

        # Throwaway open process + a resolver-stage channel.
        now = datetime.now(UTC)
        proc = ApprovalProcess(
            code=f"LEAVE_10B_TEST_{uuid4().hex[:6]}",
            title="10B routing test", requestor_role_codes=None,
            created_at=now, updated_at=now,
        )
        db_session.add(proc)
        db_session.flush()

        channel = [
            {"role_code": None, "resolver_name": "dept_head_at_requestor_campus",
             "recommend_only": True, "scope_type": "department"},
            {"role_code": "DIRECTOR", "resolver_name": None,
             "recommend_only": False, "scope_type": None},
        ]
        svc = ApprovalRequestService(db_session)
        req = svc.submit(
            process_id=proc.id, requestor_user_id=requestor.id,
            title="10B routing", payload={"leave_request_id": str(uuid4())},
            resolved_channel=channel,
        )
        # Stage 1 is the resolver stage → engine resolves the HoD as approver.
        approvers = svc._resolve_approvers(req, proc)
        assert hod_user.id in {u.id for u in approvers}


# ── LeaveRequestService applicant-designation lookup ───────────────────────────


class TestApplicantDesignationLookup:
    def _svc(self, session) -> LeaveRequestService:
        # Only _resolve_applicant_designation_code is exercised; it uses _session.
        svc = LeaveRequestService.__new__(LeaveRequestService)
        svc._session = session
        return svc

    def test_faculty_returns_designation_code(self, db_session: Session) -> None:
        campus, dept = _org(db_session)
        desig = _designation(db_session, f"d10x_{uuid4().hex[:5]}")
        _f, user = _faculty(db_session, campus=campus, dept=dept, desig=desig)
        svc = self._svc(db_session)
        assert svc._resolve_applicant_designation_code(user.id) == desig.code

    def test_non_faculty_returns_none(self, db_session: Session) -> None:
        user = User(
            username=f"nf_{uuid4().hex[:8]}", email=f"nf_{uuid4().hex[:8]}@dev.local",
            password_hash="x", is_active=True,
        )
        db_session.add(user)
        db_session.flush()
        svc = self._svc(db_session)
        assert svc._resolve_applicant_designation_code(user.id) is None
