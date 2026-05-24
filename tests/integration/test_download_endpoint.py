"""Integration tests for the authenticated download endpoint.

Proves six behaviours:
  1. Permitted session → 200 + file bytes
  2. No session cookie → 403
  3. Valid session but no file_asset:read permission → 403
  4. Valid session + permission but file_id not found → 404
  5. Non-Registrar with file_asset:read but no letterhead_asset:read → 403 on letterhead
  6. Registrar with letterhead_asset:read → 200 on same letterhead
"""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, select
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

import durgam.db as _db_mod
from durgam.api.download import download_file
from durgam.models.auth import UserSession
from durgam.models.crosscutting import FileAsset
from durgam.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from durgam.storage import get_storage_backend


@pytest.fixture()
def _patch_engine(db_engine, monkeypatch):
    """Route open_session() to the test DB so the endpoint sees test data."""
    monkeypatch.setattr(_db_mod, "_engine", db_engine)


def _create_user(session: Session, username: str) -> User:
    u = User(
        username=username,
        email=f"{username}@test.dev",
        password_hash="not-a-real-hash",
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _create_session_row(session: Session, user_id, raw_token: str) -> UserSession:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(UTC)
    us = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_active_at=now,
        expires_at=now + timedelta(days=7),
        is_invalidated=False,
    )
    session.add(us)
    session.flush()
    session.refresh(us)
    return us


def _grant_file_read(session: Session, user_id) -> None:
    role = Role(name="DL Test FileReader", code=f"DL_FR_{uuid4().hex[:6]}", level=999)
    session.add(role)
    session.flush()
    session.refresh(role)

    perm = session.exec(
        select(Permission).where(
            Permission.resource == "file_asset",
            Permission.action == "read",
            Permission.scope == "*",
        )
    ).first()
    if perm is None:
        perm = Permission(resource="file_asset", action="read", scope="*")
        session.add(perm)
        session.flush()
        session.refresh(perm)

    rp = RolePermission(role_id=role.id, permission_id=perm.id)
    session.add(rp)
    session.flush()

    ur = UserRole(user_id=user_id, role_id=role.id)
    session.add(ur)
    session.flush()


def _grant_permission(session: Session, user_id, resource: str, action: str) -> None:
    role = Role(name=f"DL Test {resource}_{action}", code=f"DL_{uuid4().hex[:8]}", level=999)
    session.add(role)
    session.flush()
    session.refresh(role)

    perm = session.exec(
        select(Permission).where(
            Permission.resource == resource,
            Permission.action == action,
            Permission.scope == "*",
        )
    ).first()
    if perm is None:
        perm = Permission(resource=resource, action=action, scope="*")
        session.add(perm)
        session.flush()
        session.refresh(perm)

    rp = RolePermission(role_id=role.id, permission_id=perm.id)
    session.add(rp)
    session.flush()

    ur = UserRole(user_id=user_id, role_id=role.id)
    session.add(ur)
    session.flush()


def _create_file_asset(
    session: Session, owner_id, storage_key: str, *, purpose: str = "test",
) -> FileAsset:
    fa = FileAsset(
        storage_key=storage_key,
        original_name="test.png",
        mime_type="image/png",
        size_bytes=4,
        sha256=hashlib.sha256(b"test").hexdigest(),
        owner_user_id=owner_id,
        purpose=purpose,
    )
    session.add(fa)
    session.flush()
    session.refresh(fa)
    return fa


def _test_client() -> TestClient:
    app = Starlette(routes=[
        Route("/api/files/{file_id}", download_file, methods=["GET"]),
    ])
    return TestClient(app)


@pytest.mark.usefixtures("_patch_engine")
class TestDownloadEndpoint:
    def test_permitted_returns_bytes(self, db_engine):
        backend = get_storage_backend()
        key = f"test_{uuid4().hex}"
        backend.put(key, b"test", "image/png")

        try:
            with Session(db_engine) as session:
                user = _create_user(session, f"dl_ok_{uuid4().hex[:6]}")
                raw_token = uuid4().hex
                _create_session_row(session, user.id, raw_token)
                _grant_file_read(session, user.id)
                fa = _create_file_asset(session, user.id, key)
                file_id = fa.id
                session.commit()

            client = _test_client()
            resp = client.get(
                f"/api/files/{file_id}",
                cookies={"dsession": raw_token},
            )

            assert resp.status_code == 200
            assert resp.content == b"test"
            assert resp.headers["content-type"] == "image/png"
            assert "test.png" in resp.headers.get("content-disposition", "")
        finally:
            backend.delete(key)

    def test_no_session_returns_403(self, db_engine):
        client = _test_client()
        resp = client.get(f"/api/files/{uuid4()}")
        assert resp.status_code == 403

    def test_no_permission_returns_403(self, db_engine):
        with Session(db_engine) as session:
            user = _create_user(session, f"dl_nop_{uuid4().hex[:6]}")
            raw_token = uuid4().hex
            _create_session_row(session, user.id, raw_token)
            session.commit()

        client = _test_client()
        resp = client.get(
            f"/api/files/{uuid4()}",
            cookies={"dsession": raw_token},
        )
        assert resp.status_code == 403

    def test_missing_file_returns_404(self, db_engine):
        with Session(db_engine) as session:
            user = _create_user(session, f"dl_nf_{uuid4().hex[:6]}")
            raw_token = uuid4().hex
            _create_session_row(session, user.id, raw_token)
            _grant_file_read(session, user.id)
            session.commit()

        client = _test_client()
        resp = client.get(
            f"/api/files/{uuid4()}",
            cookies={"dsession": raw_token},
        )
        assert resp.status_code == 404

    def test_non_registrar_cannot_download_letterhead(self, db_engine):
        """§9.3 regression: user with file_asset:read but no letterhead_asset:read
        must be denied access to files with purpose='letterhead'."""
        backend = get_storage_backend()
        key = f"test_lh_{uuid4().hex}"
        backend.put(key, b"letterhead-bytes", "image/png")

        try:
            with Session(db_engine) as session:
                user = _create_user(session, f"dl_stu_{uuid4().hex[:6]}")
                raw_token = uuid4().hex
                _create_session_row(session, user.id, raw_token)
                _grant_file_read(session, user.id)
                fa = _create_file_asset(session, user.id, key, purpose="letterhead")
                file_id = fa.id
                session.commit()

            client = _test_client()
            resp = client.get(
                f"/api/files/{file_id}",
                cookies={"dsession": raw_token},
            )
            assert resp.status_code == 403
        finally:
            backend.delete(key)

    def test_registrar_can_download_letterhead(self, db_engine):
        """Registrar with letterhead_asset:read passes the escalation check."""
        backend = get_storage_backend()
        key = f"test_lhr_{uuid4().hex}"
        backend.put(key, b"letterhead-bytes", "image/png")

        try:
            with Session(db_engine) as session:
                user = _create_user(session, f"dl_reg_{uuid4().hex[:6]}")
                raw_token = uuid4().hex
                _create_session_row(session, user.id, raw_token)
                _grant_file_read(session, user.id)
                _grant_permission(session, user.id, "letterhead_asset", "read")
                fa = _create_file_asset(session, user.id, key, purpose="letterhead")
                file_id = fa.id
                session.commit()

            client = _test_client()
            resp = client.get(
                f"/api/files/{file_id}",
                cookies={"dsession": raw_token},
            )
            assert resp.status_code == 200
            assert resp.content == b"letterhead-bytes"
        finally:
            backend.delete(key)
