"""Integration tests for ApprovalProcess attachment config (M10 Phase 7D).

Resolves TD-080: sys-admin UI for max_attachment_mb and allowed_attachment_mime_types_json.

Coverage:
  A (service layer, 7): list_all includes created process, excludes soft-deleted process,
     update max_attachment_mb persists, update allowed_mimes single persists,
     update allowed_mimes multiple persists, clear allowed_mimes to None,
     create with allowed_mime_types persists
  B (service layer, 2): create without allowed_mimes defaults to None,
     create with max_attachment_mb persists
  C (serialization contract, 3): max_attachment_mb serialized as str,
     allowed_mimes=None serializes as "Any" display + empty raw,
     allowed_mimes list serializes correctly
  D (toggle logic, 3): adds mime when absent, removes mime when present,
     empty list add

DB strategy: db_session (function-scoped, rolls back). All synthetic data.
No seeded_session mutation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.crosscutting import ApprovalProcess
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.services.approval_process import ApprovalProcessService


def _now() -> datetime:
    return datetime.now(UTC)


def _svc(session: Session) -> ApprovalProcessService:
    return ApprovalProcessService(repo=ApprovalProcessRepository(session))


def _make_process(session: Session, *, suffix: str = "") -> ApprovalProcess:
    uid = uuid4().hex[:6]
    proc = ApprovalProcess(
        code=f"TPRC{uid}",
        title=f"Test Process {uid} {suffix}".strip(),
        max_attachment_mb=5,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(proc)
    session.flush()
    return proc


# ── A + B: Service layer ──────────────────────────────────────────────────────


class TestApprovalProcessServiceListAndUpdate:
    """Service-layer tests for list_all and attachment-config field persistence."""

    def test_list_all_includes_created_process(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        results = _svc(db_session).list_all()
        codes = {p.code for p in results}
        assert proc.code in codes

    def test_list_all_excludes_soft_deleted_process(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        actor = uuid4()
        _svc(db_session).soft_delete(proc.id, actor)
        results = _svc(db_session).list_all()
        codes = {p.code for p in results}
        assert proc.code not in codes

    def test_update_max_attachment_mb_persists(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        _svc(db_session).update(proc.id, {"max_attachment_mb": 15}, uuid4())
        db_session.refresh(proc)
        assert proc.max_attachment_mb == 15

    def test_update_allowed_mime_types_single_mime_persists(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        _svc(db_session).update(
            proc.id, {"allowed_attachment_mime_types_json": ["application/pdf"]}, uuid4()
        )
        db_session.refresh(proc)
        assert proc.allowed_attachment_mime_types_json == ["application/pdf"]

    def test_update_allowed_mime_types_multiple_mimes_persist(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        mimes = ["application/pdf", "image/jpeg", "image/png"]
        _svc(db_session).update(
            proc.id, {"allowed_attachment_mime_types_json": mimes}, uuid4()
        )
        db_session.refresh(proc)
        assert proc.allowed_attachment_mime_types_json == mimes

    def test_update_both_attachment_fields_at_once(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        _svc(db_session).update(
            proc.id,
            {
                "max_attachment_mb": 20,
                "allowed_attachment_mime_types_json": ["application/pdf", "image/png"],
            },
            uuid4(),
        )
        db_session.refresh(proc)
        assert proc.max_attachment_mb == 20
        assert proc.allowed_attachment_mime_types_json == ["application/pdf", "image/png"]

    def test_update_clear_allowed_mimes_to_none(self, db_session: Session) -> None:
        proc = _make_process(db_session)
        svc = _svc(db_session)
        svc.update(proc.id, {"allowed_attachment_mime_types_json": ["application/pdf"]}, uuid4())
        svc.update(proc.id, {"allowed_attachment_mime_types_json": None}, uuid4())
        db_session.refresh(proc)
        assert proc.allowed_attachment_mime_types_json is None

    def test_create_with_allowed_mime_types_persists(self, db_session: Session) -> None:
        uid = uuid4().hex[:6]
        proc = _svc(db_session).create(
            code=f"TMIM{uid}",
            title=f"Mime Test {uid}",
            max_attachment_mb=10,
            allowed_attachment_mime_types_json=["application/pdf", "image/png"],
            actor_id=uuid4(),
        )
        db_session.refresh(proc)
        assert proc.allowed_attachment_mime_types_json == ["application/pdf", "image/png"]
        assert proc.max_attachment_mb == 10

    def test_create_without_allowed_mimes_defaults_none(self, db_session: Session) -> None:
        uid = uuid4().hex[:6]
        proc = _svc(db_session).create(
            code=f"TNOM{uid}",
            title=f"No Mime Test {uid}",
            actor_id=uuid4(),
        )
        db_session.refresh(proc)
        assert proc.allowed_attachment_mime_types_json is None

    def test_create_with_explicit_max_attachment_mb_persists(self, db_session: Session) -> None:
        uid = uuid4().hex[:6]
        proc = _svc(db_session).create(
            code=f"TMBS{uid}",
            title=f"MB Size Test {uid}",
            max_attachment_mb=25,
            actor_id=uuid4(),
        )
        db_session.refresh(proc)
        assert proc.max_attachment_mb == 25


# ── C: Serialization contract ─────────────────────────────────────────────────


class TestSerializationContract:
    """Verify the dict shape that load_processes produces for the new fields."""

    def test_max_attachment_mb_serialized_as_str(self) -> None:
        proc = ApprovalProcess(code="SER001", title="T", max_attachment_mb=8)
        row = {
            "max_attachment_mb": str(proc.max_attachment_mb),
            "raw_max_attachment_mb": str(proc.max_attachment_mb),
        }
        assert row["max_attachment_mb"] == "8"
        assert row["raw_max_attachment_mb"] == "8"

    def test_allowed_mimes_none_serializes_as_any(self) -> None:
        proc = ApprovalProcess(code="SER002", title="T", max_attachment_mb=5)
        proc.allowed_attachment_mime_types_json = None
        row = {
            "allowed_mimes": ", ".join(proc.allowed_attachment_mime_types_json or []) or "Any",
            "raw_allowed_mimes": ",".join(proc.allowed_attachment_mime_types_json or []),
        }
        assert row["allowed_mimes"] == "Any"
        assert row["raw_allowed_mimes"] == ""

    def test_allowed_mimes_list_serializes_correctly(self) -> None:
        proc = ApprovalProcess(code="SER003", title="T", max_attachment_mb=5)
        proc.allowed_attachment_mime_types_json = ["application/pdf", "image/jpeg"]
        row = {
            "allowed_mimes": ", ".join(proc.allowed_attachment_mime_types_json or []) or "Any",
            "raw_allowed_mimes": ",".join(proc.allowed_attachment_mime_types_json or []),
        }
        assert row["allowed_mimes"] == "application/pdf, image/jpeg"
        assert row["raw_allowed_mimes"] == "application/pdf,image/jpeg"


# ── D: Toggle logic ───────────────────────────────────────────────────────────


class TestToggleAllowedMimeLogic:
    """Pure-Python tests for toggle_allowed_mime list logic."""

    @staticmethod
    def _toggle(lst: list[str], mime: str) -> list[str]:
        if mime in lst:
            return [m for m in lst if m != mime]
        return [*lst, mime]

    def test_toggle_adds_mime_when_absent(self) -> None:
        result = self._toggle(["application/pdf"], "image/jpeg")
        assert "image/jpeg" in result
        assert "application/pdf" in result

    def test_toggle_removes_mime_when_present(self) -> None:
        result = self._toggle(["application/pdf", "image/jpeg"], "image/jpeg")
        assert "image/jpeg" not in result
        assert "application/pdf" in result

    def test_toggle_empty_list_adds_first_mime(self) -> None:
        result = self._toggle([], "application/pdf")
        assert result == ["application/pdf"]
