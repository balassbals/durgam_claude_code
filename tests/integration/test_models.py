"""Integration tests: create, read, soft-delete each M0 model against real Postgres."""

from datetime import date
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.config_anchors import AcademicYear, Holiday, StudentCategoryCount
from durgam.models.crosscutting import (
    ApprovalProcess,
    ApprovalRequest,
    ApprovalStep,
)
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole
from durgam.repositories.base import BaseRepository


class TestSoftDeleteFilter:
    def test_soft_deleted_rows_excluded_from_list_active(self, db_session):
        role = Role(code=f"ROLE_{uuid4().hex[:8]}", name="Test", level=1)
        db_session.add(role)
        db_session.flush()

        repo = BaseRepository(Role, db_session)
        assert repo.get_by_id(role.id) is not None

        repo.soft_delete(role, actor_id=uuid4())
        db_session.flush()

        assert role.is_deleted is True
        assert repo.get_by_id(role.id) is None

        active = repo.list_active()
        assert all(not r.is_deleted for r in active)

    def test_save_updates_updated_at(self, db_session):
        role = Role(code=f"ROLE_{uuid4().hex[:8]}", name="Before", level=1)
        db_session.add(role)
        db_session.flush()

        original_updated_at = role.updated_at
        role.name = "After"
        repo = BaseRepository(Role, db_session)
        updated = repo.save(role)

        assert updated.name == "After"
        assert updated.updated_at >= original_updated_at


class TestIdentityModels:
    def test_user_create_and_read(self, db_session):
        user = User(
            username="testuser",
            email=f"test_{uuid4().hex[:8]}@sssihl.edu.in",
            password_hash="hashed",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
        db_session.refresh(user)

        fetched = db_session.get(User, user.id)
        assert fetched is not None
        assert fetched.username == "testuser"
        assert fetched.is_deleted is False

    def test_role_unique_code_enforced(self, db_session):
        import sqlalchemy as sa

        code = f"UNIQUE_{uuid4().hex[:6]}"
        db_session.add(Role(code=code, name="A", level=1))
        db_session.flush()
        db_session.add(Role(code=code, name="B", level=2))
        with pytest.raises(sa.exc.IntegrityError):
            db_session.flush()

    def test_user_role_relationship(self, db_session):
        user = User(
            username=f"u_{uuid4().hex[:6]}",
            email=f"ur_{uuid4().hex[:8]}@test.com",
            password_hash="x",
            is_active=True,
        )
        role = Role(code=f"R_{uuid4().hex[:6]}", name="R", level=1)
        perm = Permission(resource="r", action="read", scope="*")
        db_session.add_all([user, role, perm])
        db_session.flush()

        db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
        db_session.flush()

        ur = db_session.exec(select(UserRole).where(UserRole.user_id == user.id)).first()
        assert ur is not None
        assert ur.role_id == role.id


class TestCrosscuttingModels:
    def test_audit_log_insert(self, db_session):
        from durgam.models.crosscutting import AuditLog

        row = AuditLog(
            action="test",
            resource="unit",
            diff_json={"x": [None, 1]},
        )
        db_session.add(row)
        db_session.flush()

        fetched = db_session.get(AuditLog, row.id)
        assert fetched is not None
        assert fetched.diff_json == {"x": [None, 1]}

    def test_approval_step_cascades_on_request_delete(self, db_session):
        proc = ApprovalProcess(
            code=f"P_{uuid4().hex[:6]}",
            title="Test Process",
        )
        db_session.add(proc)
        db_session.flush()

        user = User(
            username=f"u_{uuid4().hex[:6]}",
            email=f"ap_{uuid4().hex[:8]}@test.com",
            password_hash="x",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

        req = ApprovalRequest(
            process_id=proc.id,
            requestor_user_id=user.id,
            title="Test",
        )
        db_session.add(req)
        db_session.flush()

        step = ApprovalStep(request_id=req.id, stage=1, approver_role_code="DEAN")
        db_session.add(step)
        db_session.flush()

        step_id = step.id
        db_session.delete(req)
        db_session.flush()
        db_session.expire_all()  # evict identity-map cache

        # Use a fresh select to bypass the identity map
        remaining = db_session.exec(select(ApprovalStep).where(ApprovalStep.id == step_id)).first()
        assert remaining is None, "ON DELETE CASCADE should have removed the step"


class TestConfigAnchorModels:
    def test_academic_year_unique_code(self, db_session):
        import sqlalchemy as sa

        db_session.add(
            AcademicYear(code="2030-31", starts_on=date(2030, 7, 1), ends_on=date(2031, 4, 30))
        )
        db_session.flush()
        db_session.add(
            AcademicYear(code="2030-31", starts_on=date(2030, 7, 1), ends_on=date(2031, 4, 30))
        )
        with pytest.raises(sa.exc.IntegrityError):
            db_session.flush()

    def test_holiday_unique_date_per_ay(self, db_session):
        import sqlalchemy as sa

        ay = AcademicYear(
            code=f"AY_{uuid4().hex[:4]}", starts_on=date(2025, 7, 1), ends_on=date(2026, 4, 30)
        )
        db_session.add(ay)
        db_session.flush()

        db_session.add(
            Holiday(academic_year_id=ay.id, holiday_date=date(2025, 8, 15), name="Independence Day")
        )
        db_session.flush()
        db_session.add(
            Holiday(academic_year_id=ay.id, holiday_date=date(2025, 8, 15), name="Duplicate")
        )
        with pytest.raises(sa.exc.IntegrityError):
            db_session.flush()

    def test_student_category_count_unique_per_ay(self, db_session):
        import sqlalchemy as sa

        ay = AcademicYear(
            code=f"AY_{uuid4().hex[:4]}", starts_on=date(2025, 7, 1), ends_on=date(2026, 4, 30)
        )
        db_session.add(ay)
        db_session.flush()

        db_session.add(
            StudentCategoryCount(
                academic_year_id=ay.id,
                sc_count=10,
                st_count=5,
                obc_count=20,
                ews_count=5,
                general_count=60,
            )
        )
        db_session.flush()
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
        with pytest.raises(sa.exc.IntegrityError):
            db_session.flush()
