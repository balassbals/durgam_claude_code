"""Unit tests for durgam/audit/labels.py — resource label resolver."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest

from durgam.audit.labels import (
    FK_FIELDS,
    _RESOURCE_RESOLVERS,
    bulk_resolve_labels,
)
from durgam.models.campus import Campus
from durgam.models.centre import CentreOfExcellence
from durgam.models.config_anchors import (
    AcademicYear,
    CalendarEntry,
    ClassTeacherAssignment,
    ClassTimingsConfig,
    Designation,
    DocumentTemplate,
    FacultyMentorAssignment,
    Holiday,
    MentalHealthCounsellor,
    NonOwnedCourse,
    NonRegularFaculty,
    PurchaseCommitteeTemplate,
    PurchaseProcedureRule,
    RoleEmail,
    StudentCategoryCount,
    UGTimetable,
    WorkingDaysConfig,
)
from durgam.models.course import Course
from durgam.models.crosscutting import AuditLog, FileAsset
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import Role, User
from durgam.models.program import Program
from durgam.models.school import School
from durgam.models.vision_mission import (
    DepartmentVisionMission,
    UniversityVisionMission,
)


# ── Helper ───────────────────────────────────────────────────────────────────


def _mk_faculty(session, campus, dept):
    """Minimal Faculty to satisfy assignment.faculty_id FK (M10 Phase 11A)."""
    desig = Designation(code=f"DG{uuid4().hex[:4]}", name="Prof", rank=50)
    session.add(desig)
    session.flush()
    user = User(
        username=f"alr_{uuid4().hex[:8]}",
        email=f"alr_{uuid4().hex[:8]}@dev.local",
        password_hash="x",
    )
    session.add(user)
    session.flush()
    now = datetime.now(UTC)
    f = Faculty(
        user_id=user.id, employee_id=f"FAC-{uuid4().hex[:8]}", title="Dr",
        first_name="F", last_name="A", designation_id=desig.id,
        department_id=dept.id, campus_id=campus.id, joining_date=date(2020, 1, 1),
        phone="9", emergency_contact_name="E", emergency_contact_relation="P",
        emergency_contact_phone="9", created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _make_audit_row(**kwargs: Any) -> AuditLog:
    defaults: dict[str, Any] = {
        "occurred_at": datetime.now(UTC),
        "actor_user_id": None,
        "actor_role_code": None,
        "action": "write",
        "resource": "campus",
        "resource_id": None,
        "request_id": None,
        "ip": None,
        "user_agent": None,
        "diff_json": None,
        "actor_roles_json": None,
    }
    defaults.update(kwargs)
    return AuditLog(id=kwargs.get("id", 1), **{k: v for k, v in defaults.items() if k != "id"})


# ── Per-resolver tests ───────────────────────────────────────────────────────


class TestUserResolver:
    def test_with_full_name(self, db_session):
        u = User(username="jdoe", full_name="John Doe", email="jdoe@test.dev",
                 password_hash="x")
        db_session.add(u)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["user"]([str(u.id)], db_session)
        assert result[str(u.id)] == "jdoe — John Doe"

    def test_without_full_name(self, db_session):
        u = User(username="nofull", email="nofull@test.dev", password_hash="x")
        db_session.add(u)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["user"]([str(u.id)], db_session)
        assert result[str(u.id)] == "nofull"


class TestRoleResolver:
    def test_label(self, db_session):
        r = Role(code="TEST_ROLE", name="Test Role", level=0)
        db_session.add(r)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["role"]([str(r.id)], db_session)
        assert result[str(r.id)] == "TEST_ROLE"


class TestCampusResolver:
    def test_label(self, db_session):
        c = Campus(code="PSN", name="Prasanthi Nilayam")
        db_session.add(c)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["campus"]([str(c.id)], db_session)
        assert result[str(c.id)] == "PSN — Prasanthi Nilayam"


class TestSchoolResolver:
    def test_label(self, db_session):
        s = School(code="SCI", name="Sciences")
        db_session.add(s)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["school"]([str(s.id)], db_session)
        assert result[str(s.id)] == "SCI — Sciences"


class TestDepartmentResolver:
    def test_label(self, db_session):
        s = School(code="TST_SCH", name="Test School")
        db_session.add(s)
        db_session.flush()
        c = Campus(code="TST_C", name="Test Campus")
        db_session.add(c)
        db_session.flush()
        d = Department(code="DMACS", name="Maths & CS", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["department"]([str(d.id)], db_session)
        assert result[str(d.id)] == "DMACS — Maths & CS"


class TestCentreResolver:
    def test_label(self, db_session):
        c = Campus(code="TST_C2", name="Camp")
        db_session.add(c)
        db_session.flush()
        coe = CentreOfExcellence(code="CMB", name="Mol Bio", campus_id=c.id)
        db_session.add(coe)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["centre"]([str(coe.id)], db_session)
        assert result[str(coe.id)] == "CMB — Mol Bio"


class TestCourseResolver:
    def test_label(self, db_session):
        s = School(code="TST_SC3", name="S")
        db_session.add(s)
        db_session.flush()
        c = Campus(code="TST_C3", name="C")
        db_session.add(c)
        db_session.flush()
        d = Department(code="TST_D3", name="D", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        p = Program(code="BSCM", name="BSc Math", department_id=d.id,
                    degree_type="BSc", duration_years=3)
        db_session.add(p)
        db_session.flush()
        co = Course(code="MAT101", name="Calculus", program_id=p.id,
                    department_id=d.id, credits=4, evaluation="IE")
        db_session.add(co)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["course"]([str(co.id)], db_session)
        assert result[str(co.id)] == "MAT101 — Calculus"


class TestAcademicYearResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-26", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        db_session.add(ay)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["academic_year"]([str(ay.id)], db_session)
        assert result[str(ay.id)] == "2025-26"


class TestHolidayResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-27", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        db_session.add(ay)
        db_session.flush()
        h = Holiday(academic_year_id=ay.id, holiday_date=date(2025, 8, 15),
                    name="Independence Day")
        db_session.add(h)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["holiday"]([str(h.id)], db_session)
        assert result[str(h.id)] == "Independence Day (2025-08-15)"


class TestCalendarEntryResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-28", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        u = User(username="cal_owner", email="cal@test.dev", password_hash="x")
        db_session.add_all([ay, u])
        db_session.flush()
        ce = CalendarEntry(
            academic_year_id=ay.id, title="Orientation", entry_type="academic",
            starts_at=datetime(2025, 7, 1, tzinfo=UTC),
            ends_at=datetime(2025, 7, 2, tzinfo=UTC),
            owner_user_id=u.id, owner_role_code="REGISTRAR",
        )
        db_session.add(ce)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["calendar_entry"]([str(ce.id)], db_session)
        assert result[str(ce.id)] == "Orientation"


class TestDesignationResolver:
    def test_label(self, db_session):
        d = Designation(code="PROF", name="Professor", rank=1)
        db_session.add(d)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["designation"]([str(d.id)], db_session)
        assert result[str(d.id)] == "PROF — Professor"


class TestApprovalProcessResolver:
    def test_label(self, db_session):
        from durgam.models.crosscutting import ApprovalProcess
        ap = ApprovalProcess(code="LEAVE_HOD", title="Leave via HoD")
        db_session.add(ap)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["approval_process"]([str(ap.id)], db_session)
        assert result[str(ap.id)] == "LEAVE_HOD — Leave via HoD"


class TestRoleEmailResolver:
    def test_label(self, db_session):
        re = RoleEmail(role_code="REGISTRAR", email="reg@test.dev")
        db_session.add(re)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["role_email"]([str(re.id)], db_session)
        assert result[str(re.id)] == "REGISTRAR: reg@test.dev"


class TestMentalHealthCounsellorResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-29", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        c = Campus(code="TST_C5", name="C5")
        db_session.add_all([ay, c])
        db_session.flush()
        m = MentalHealthCounsellor(
            academic_year_id=ay.id, campus_id=c.id, name="Dr. Sharma",
            qualification="PhD", specialisation="Clinical",
            mode_of_appointment="full_time",
            appointment_start=date(2025, 7, 1), appointment_end=date(2026, 5, 31),
        )
        db_session.add(m)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["mental_health_counsellor"]([str(m.id)], db_session)
        assert result[str(m.id)] == "Dr. Sharma"


class TestFacultyResolver:
    def test_label(self, db_session):
        s = School(code="TST_SF1", name="SF1")
        c = Campus(code="TST_CF1", name="CF1")
        db_session.add_all([s, c])
        db_session.flush()
        d = Department(code="TST_DF1", name="DF1", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        fac = _mk_faculty(db_session, c, d)
        result = _RESOURCE_RESOLVERS["faculty"]([str(fac.id)], db_session)
        expected = f"{fac.employee_id} — {fac.title} {fac.first_name} {fac.last_name}"
        assert result[str(fac.id)] == expected


class TestFacultyMentorAssignmentResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-30", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        c = Campus(code="TST_C6", name="C6")
        s = School(code="TST_S6", name="S6")
        db_session.add_all([ay, c, s])
        db_session.flush()
        d = Department(code="TST_D6", name="D6", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        fac = _mk_faculty(db_session, c, d)
        f = FacultyMentorAssignment(
            academic_year_id=ay.id, campus_id=c.id,
            faculty_id=fac.id, student_id_placeholder="Student B",
        )
        db_session.add(f)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["faculty_mentor_assignment"]([str(f.id)], db_session)
        expected_fac = f"{fac.employee_id} — {fac.title} {fac.first_name} {fac.last_name}"
        assert result[str(f.id)] == f"{expected_fac} → Student B"


class TestClassTeacherAssignmentResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-31", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        s = School(code="TST_S7", name="S7")
        c = Campus(code="TST_C7", name="C7")
        db_session.add_all([ay, s, c])
        db_session.flush()
        d = Department(code="TST_D7", name="D7", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        fac = _mk_faculty(db_session, c, d)
        ct = ClassTeacherAssignment(
            academic_year_id=ay.id, department_id=d.id,
            faculty_id=fac.id, class_identifier="MSc-I",
        )
        db_session.add(ct)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["class_teacher_assignment"]([str(ct.id)], db_session)
        expected_fac = f"{fac.employee_id} — {fac.title} {fac.first_name} {fac.last_name}"
        assert result[str(ct.id)] == f"{expected_fac} (MSc-I)"


class TestNonRegularFacultyResolver:
    def test_label(self, db_session):
        s = School(code="TST_S9", name="S9")
        c = Campus(code="TST_C9", name="C9")
        db_session.add_all([s, c])
        db_session.flush()
        d = Department(code="TST_D9", name="D9", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        nrf = NonRegularFaculty(
            department_id=d.id, name="Guest Lecturer", designation="Visiting",
            organization="IISc", expertise="ML",
            available_from=date(2025, 7, 1), available_to=date(2025, 12, 31),
        )
        db_session.add(nrf)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["non_regular_faculty"]([str(nrf.id)], db_session)
        assert result[str(nrf.id)] == "Guest Lecturer (IISc)"


class TestNonOwnedCourseResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-33", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        c = Campus(code="TST_C33", name="C33")
        s = School(code="TST_S33", name="S33")
        db_session.add_all([ay, c, s])
        db_session.flush()
        d = Department(code="TST_D33", name="D33", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        fac = _mk_faculty(db_session, c, d)
        noc = NonOwnedCourse(
            academic_year_id=ay.id, course_code="MDC01", course_name="Value Ed",
            credits=2, semester="Odd", faculty_id=fac.id,
        )
        db_session.add(noc)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["non_owned_course"]([str(noc.id)], db_session)
        assert result[str(noc.id)] == "MDC01 — Value Ed"


class TestUGTimetableResolver:
    def test_label(self, db_session):
        ay = AcademicYear(code="2025-34", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        c = Campus(code="TST_C34", name="C34")
        s = School(code="TST_S34", name="S34")
        db_session.add_all([ay, c, s])
        db_session.flush()
        d = Department(code="TST_D34", name="D34", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        fac = _mk_faculty(db_session, c, d)
        ugt = UGTimetable(
            academic_year_id=ay.id, semester="Odd", year_of_study=1,
            day_of_week=1, period_number=3, course_code="MAT101",
            course_name="Calc", faculty_id=fac.id,
        )
        db_session.add(ugt)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["ug_timetable"]([str(ugt.id)], db_session)
        assert result[str(ugt.id)] == "MAT101 D1P3"


class TestPurchaseProcedureRuleResolver:
    def test_label(self, db_session):
        ppr = PurchaseProcedureRule(
            fund_source="university", tier=1, floor_amount=0,
            approving_authority_role_codes=["HOD"],
        )
        db_session.add(ppr)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["purchase_procedure_rule"]([str(ppr.id)], db_session)
        assert result[str(ppr.id)] == "university T1"


class TestPurchaseCommitteeTemplateResolver:
    def test_label(self, db_session):
        pct = PurchaseCommitteeTemplate(
            committee_type="campus_purchase",
            eligible_designations=["PROF"], faculty_member_count=3,
            fixed_role_members=["FINANCE_OFFICER"],
        )
        db_session.add(pct)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["purchase_committee_template"]([str(pct.id)], db_session)
        assert result[str(pct.id)] == "campus_purchase"


class TestStudentCategoryCountResolver:
    def test_label_with_ay_join(self, db_session):
        ay = AcademicYear(code="2025-35", starts_on=date(2025, 6, 1),
                          ends_on=date(2026, 5, 31))
        db_session.add(ay)
        db_session.flush()
        scc = StudentCategoryCount(academic_year_id=ay.id)
        db_session.add(scc)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["student_category_count"]([str(scc.id)], db_session)
        assert result[str(scc.id)] == "AY 2025-35"


class TestLetterheadAssetResolver:
    def test_label(self, db_session):
        fa = FileAsset(storage_key="k", original_name="f.png", mime_type="image/png",
                       size_bytes=100, sha256="a" * 64)
        db_session.add(fa)
        db_session.flush()
        dt = DocumentTemplate(purpose="letterhead", role_code="REGISTRAR", file_id=fa.id)
        db_session.add(dt)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["letterhead_asset"]([str(dt.id)], db_session)
        assert result[str(dt.id)] == "Letterhead (REGISTRAR)"


class TestTemplateAssetResolver:
    def test_label(self, db_session):
        fa = FileAsset(storage_key="k2", original_name="t.docx", mime_type="application/docx",
                       size_bytes=200, sha256="b" * 64)
        db_session.add(fa)
        db_session.flush()
        dt = DocumentTemplate(purpose="certificate", file_id=fa.id)
        db_session.add(dt)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["template_asset"]([str(dt.id)], db_session)
        assert result[str(dt.id)] == "Template (certificate)"


class TestUniversityVisionMissionResolver:
    def test_label(self, db_session):
        uvm = UniversityVisionMission(vision="Excellence in all")
        db_session.add(uvm)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["university_vision_mission"]([str(uvm.id)], db_session)
        assert result[str(uvm.id)] == "(university singleton)"


class TestDepartmentVisionMissionResolver:
    def test_label_with_dept_join(self, db_session):
        s = School(code="TST_SA", name="SA")
        c = Campus(code="TST_CA", name="CA")
        db_session.add_all([s, c])
        db_session.flush()
        d = Department(code="TST_DA", name="Dept A", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        dvm = DepartmentVisionMission(department_id=d.id, vision="Excellence")
        db_session.add(dvm)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["department_vision_mission"]([str(dvm.id)], db_session)
        assert result[str(dvm.id)] == "TST_DA — Dept A"


class TestClassTimingsConfigResolver:
    def test_label(self, db_session):
        ctc = ClassTimingsConfig(periods_per_day=6, period_duration_minutes=50,
                                 first_period_start="08:00")
        db_session.add(ctc)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["class_timings_config"]([str(ctc.id)], db_session)
        assert result[str(ctc.id)] == "(singleton)"


class TestWorkingDaysConfigResolver:
    def test_label(self, db_session):
        wdc = WorkingDaysConfig(days_per_week=6)
        db_session.add(wdc)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["working_days_config"]([str(wdc.id)], db_session)
        assert result[str(wdc.id)] == "(singleton)"


class TestSessionResolver:
    def test_returns_empty(self, db_session):
        result = _RESOURCE_RESOLVERS["session"](["alice", "bob"], db_session)
        assert result == {}


class TestProgramResolver:
    def test_label(self, db_session):
        s = School(code="TST_SB", name="SB")
        c = Campus(code="TST_CB", name="CB")
        db_session.add_all([s, c])
        db_session.flush()
        d = Department(code="TST_DB", name="DB", school_id=s.id, main_campus_id=c.id)
        db_session.add(d)
        db_session.flush()
        p = Program(code="MSCPHY", name="MSc Physics", department_id=d.id,
                    degree_type="MSc", duration_years=2)
        db_session.add(p)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["program"]([str(p.id)], db_session)
        assert result[str(p.id)] == "MSCPHY — MSc Physics"


class TestFileAssetResolver:
    def test_label(self, db_session):
        fa = FileAsset(storage_key="k3", original_name="report.pdf",
                       mime_type="application/pdf", size_bytes=300, sha256="c" * 64)
        db_session.add(fa)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["file_asset"]([str(fa.id)], db_session)
        assert result[str(fa.id)] == "report.pdf"


# ── Generic resolver behaviour tests ────────────────────────────────────────


class TestResolverMissingIdOmitted:
    def test_unknown_uuid_returns_empty(self, db_session):
        unknown = str(uuid4())
        result = _RESOURCE_RESOLVERS["campus"]([unknown], db_session)
        assert unknown not in result

    def test_empty_ids_returns_empty(self, db_session):
        result = _RESOURCE_RESOLVERS["campus"]([], db_session)
        assert result == {}


class TestResolverSoftDeletedStillResolves:
    def test_soft_deleted_campus(self, db_session):
        c = Campus(code="TST_DEL", name="Deleted Campus",
                   is_deleted=True, deleted_at=datetime.now(UTC))
        db_session.add(c)
        db_session.flush()
        result = _RESOURCE_RESOLVERS["campus"]([str(c.id)], db_session)
        assert str(c.id) in result
        assert result[str(c.id)] == "TST_DEL — Deleted Campus"


# ── bulk_resolve_labels tests ────────────────────────────────────────────────


class TestBulkResolveCollectsFromThreeSources:
    def test_all_three_sources(self, db_session):
        u = User(username="audit_actor", full_name="Actor Name",
                 email="actor@test.dev", password_hash="x")
        c1 = Campus(code="TST_B1", name="Before Campus")
        c2 = Campus(code="TST_B2", name="After Campus")
        s = School(code="TST_SG", name="SG")
        db_session.add_all([u, c1, c2, s])
        db_session.flush()
        d = Department(code="TST_DG", name="DG", school_id=s.id, main_campus_id=c1.id)
        db_session.add(d)
        db_session.flush()

        row = _make_audit_row(
            actor_user_id=u.id,
            resource="department",
            resource_id=str(d.id),
            diff_json={"main_campus_id": [str(c1.id), str(c2.id)]},
            actor_roles_json=[
                {"role_code": "HOD", "scope_type": "department", "scope_id": str(d.id)},
            ],
        )
        enriched = bulk_resolve_labels([row], db_session)
        assert len(enriched) == 1
        e = enriched[0]
        assert e["actor_label"] == "audit_actor — Actor Name"
        assert e["resource_label"] == "TST_DG — DG"
        assert e["diff_labels"]["main_campus_id"] == [
            "TST_B1 — Before Campus", "TST_B2 — After Campus",
        ]
        assert len(e["actor_roles_resolved"]) == 1
        assert e["actor_roles_resolved"][0]["scope_label"] == "TST_DG — DG"


class TestBulkResolveActorLabel:
    def test_actor_with_user(self, db_session):
        u = User(username="actor2", full_name="Full Name",
                 email="actor2@test.dev", password_hash="x")
        db_session.add(u)
        db_session.flush()
        row = _make_audit_row(actor_user_id=u.id)
        enriched = bulk_resolve_labels([row], db_session)
        assert enriched[0]["actor_label"] == "actor2 — Full Name"

    def test_null_actor_yields_none(self, db_session):
        row = _make_audit_row(actor_user_id=None)
        enriched = bulk_resolve_labels([row], db_session)
        assert enriched[0]["actor_label"] is None


class TestBulkResolveActorRolesUniversitywide:
    def test_null_scope_type(self, db_session):
        row = _make_audit_row(
            actor_roles_json=[
                {"role_code": "SYSTEM_ADMIN", "scope_type": None, "scope_id": None},
            ],
        )
        enriched = bulk_resolve_labels([row], db_session)
        roles = enriched[0]["actor_roles_resolved"]
        assert len(roles) == 1
        assert roles[0]["scope_label"] == "universitywide"


class TestBulkResolveSessionResourceSkipped:
    def test_non_uuid_resource_id(self, db_session):
        row = _make_audit_row(
            resource="session",
            resource_id="baduser",
            action="login_failed",
        )
        enriched = bulk_resolve_labels([row], db_session)
        assert enriched[0]["resource_label"] is None


class TestDiffLabelsForFkField:
    def test_department_main_campus_change(self, db_session):
        c1 = Campus(code="TST_FK1", name="FK Before")
        c2 = Campus(code="TST_FK2", name="FK After")
        db_session.add_all([c1, c2])
        db_session.flush()
        row = _make_audit_row(
            resource="department",
            diff_json={"main_campus_id": [str(c1.id), str(c2.id)]},
        )
        enriched = bulk_resolve_labels([row], db_session)
        dl = enriched[0]["diff_labels"]
        assert "main_campus_id" in dl
        assert dl["main_campus_id"] == ["TST_FK1 — FK Before", "TST_FK2 — FK After"]

    def test_base_model_created_by(self, db_session):
        u = User(username="creator", email="creator@test.dev", password_hash="x")
        db_session.add(u)
        db_session.flush()
        row = _make_audit_row(
            resource="campus",
            diff_json={"created_by": [None, str(u.id)]},
        )
        enriched = bulk_resolve_labels([row], db_session)
        dl = enriched[0]["diff_labels"]
        assert "created_by" in dl
        assert dl["created_by"] == [None, "creator"]
