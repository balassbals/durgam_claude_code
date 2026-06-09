"""M8 Phase 4: unit/integration tests for LeaveSanctionRuleService + YAML loader.

All tests use db_session (clean DB) for isolation — no seeded_session, to avoid
triggering seeded_db_engine before integration tests that expect an empty database.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from sqlmodel import select

from durgam.models.crosscutting import AuditLog
from durgam.models.leave import LeaveSanctionAuthorityRule
from durgam.repositories.leave import LeaveSanctionRuleRepository
from durgam.services.leave_sanction_rule import LeaveSanctionRuleService

_YAML_PATH = Path(__file__).parent.parent.parent / "seeds" / "leave_sanction_matrix.yaml"
_EXPECTED_RULE_COUNT = 73  # 14 CL + 1 SCL + 56 EL/HPL/CML/ML + 2 EOL/SL


def _svc(session):
    repo = LeaveSanctionRuleRepository(session)
    return LeaveSanctionRuleService(session, repo)


def _count_active(session) -> int:
    return len(
        session.exec(
            select(LeaveSanctionAuthorityRule).where(
                LeaveSanctionAuthorityRule.is_deleted == False  # noqa: E712
            )
        ).all()
    )


# ── YAML loader tests (use db_session — clean DB) ─────────────────────────────

def test_load_from_yaml_inserts_all_rules(db_session, tmp_path) -> None:
    """Loading the YAML into an empty DB inserts exactly _EXPECTED_RULE_COUNT rows."""
    # Use a fake actor UUID — no permission check on load_from_yaml
    from uuid import uuid4
    actor = uuid4()

    result = _svc(db_session).load_from_yaml(_YAML_PATH, actor_id=actor)
    db_session.flush()

    assert result["inserted"] == _EXPECTED_RULE_COUNT, (
        f"Expected {_EXPECTED_RULE_COUNT} insertions; got {result['inserted']}"
    )
    assert result["updated"] == 0
    assert result["orphaned_soft_deleted"] == 0
    assert _count_active(db_session) == _EXPECTED_RULE_COUNT


def test_load_from_yaml_idempotent(db_session) -> None:
    """Loading twice: first run inserts; second run inserts 0, updates 0."""
    from uuid import uuid4
    actor = uuid4()
    svc = _svc(db_session)

    r1 = svc.load_from_yaml(_YAML_PATH, actor_id=actor)
    db_session.flush()
    assert r1["inserted"] == _EXPECTED_RULE_COUNT

    r2 = svc.load_from_yaml(_YAML_PATH, actor_id=actor)
    db_session.flush()
    assert r2["inserted"] == 0
    assert r2["updated"] == 0
    assert r2["orphaned_soft_deleted"] == 0
    assert _count_active(db_session) == _EXPECTED_RULE_COUNT


def test_load_from_yaml_updates_changed_rule(db_session, tmp_path) -> None:
    """Mutating one rule's notes field triggers updated == 1 on reload."""
    from uuid import uuid4
    actor = uuid4()
    svc = _svc(db_session)

    svc.load_from_yaml(_YAML_PATH, actor_id=actor)
    db_session.flush()

    # Copy YAML to tmp and modify one notes field
    mutated = tmp_path / "mutated.yaml"
    data = yaml.safe_load(_YAML_PATH.read_text())
    data["rules"][0]["notes"] = "CHANGED NOTE FOR TEST"
    mutated.write_text(yaml.dump(data))

    r2 = svc.load_from_yaml(mutated, actor_id=actor)
    db_session.flush()
    assert r2["updated"] == 1


def test_load_from_yaml_soft_deletes_orphan(db_session, tmp_path) -> None:
    """Reloading with one rule removed causes orphaned_soft_deleted == 1."""
    from uuid import uuid4
    actor = uuid4()
    svc = _svc(db_session)

    svc.load_from_yaml(_YAML_PATH, actor_id=actor)
    db_session.flush()

    # Build trimmed YAML missing the first rule
    trimmed = tmp_path / "trimmed.yaml"
    data = yaml.safe_load(_YAML_PATH.read_text())
    data["rules"] = data["rules"][1:]  # remove first rule
    trimmed.write_text(yaml.dump(data))

    r2 = svc.load_from_yaml(trimmed, actor_id=actor)
    db_session.flush()
    assert r2["orphaned_soft_deleted"] == 1
    assert _count_active(db_session) == _EXPECTED_RULE_COUNT - 1


# ── CRUD audit test ───────────────────────────────────────────────────────────

def test_create_rule_audited(db_session) -> None:
    """create_rule writes an AuditLog row with action='create' and non-null diff_json."""
    # Uses db_session (not seeded_session) to avoid triggering seeded_db_engine early,
    # which would pollute db_session integration tests that expect an empty database.
    from uuid import uuid4

    from durgam.models.identity import Permission, Role, RolePermission, User, UserRole

    actor = User(
        username=f"lsr_audit_{uuid4().hex[:8]}",
        email=f"lsr_audit_{uuid4().hex[:8]}@test.local",
        password_hash="x",
        is_active=True,
    )
    db_session.add(actor)
    db_session.flush()

    # Get-or-create configure permission to avoid UniqueViolation if already seeded.
    perm = db_session.exec(
        select(Permission).where(
            Permission.resource == "leave_sanction_rule",
            Permission.action == "configure",
            Permission.scope == "*",
        )
    ).first()
    if perm is None:
        perm = Permission(resource="leave_sanction_rule", action="configure", scope="*")
        db_session.add(perm)
        db_session.flush()

    role = Role(code=f"LSRCFG{uuid4().hex[:6]}", name="Leave Sanction Config", level=90)
    db_session.add(role)
    db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db_session.add(UserRole(user_id=actor.id, role_id=role.id))
    db_session.flush()

    svc = _svc(db_session)
    rule = svc.create_rule(
        leave_type="CL",
        applicant_role_code="TEST_ROLE",
        sanctioner_role_code="VC",
        priority=999,
        actor_id=actor.id,
        notes="Test rule for audit check",
    )
    db_session.flush()

    audit_row = db_session.exec(
        select(AuditLog).where(
            AuditLog.resource == "leave_sanction_rule",
            AuditLog.resource_id == str(rule.id),
            AuditLog.action == "create",
        )
    ).first()
    assert audit_row is not None, "AuditLog row must be created on create_rule"
    assert audit_row.diff_json is not None, "diff_json must be non-null"


def test_create_rule_requires_configure_permission(db_session) -> None:
    """create_rule raises PermissionDenied when actor lacks 'configure' permission."""
    # Uses db_session (not seeded_session) — see test_create_rule_audited for rationale.
    from uuid import uuid4

    from durgam.auth.permissions import PermissionDenied
    from durgam.models.identity import User

    no_perm_user = User(
        username=f"lsr_noperm_{uuid4().hex[:8]}",
        email=f"lsr_noperm_{uuid4().hex[:8]}@test.local",
        password_hash="x",
        is_active=True,
    )
    db_session.add(no_perm_user)
    db_session.flush()

    svc = _svc(db_session)
    with pytest.raises(PermissionDenied):
        svc.create_rule(
            leave_type="CL",
            applicant_role_code="STUDENT",
            sanctioner_role_code="VC",
            priority=999,
            actor_id=no_perm_user.id,
        )


# ── resolve_channel against seeded matrix ─────────────────────────────────────

def test_resolve_channel_against_seeded_matrix(db_session) -> None:
    """After loading YAML, resolve_channel returns correct channels for key pairs."""
    from uuid import uuid4

    from durgam.services.leave_rules import LeaveChannelError, resolve_channel

    actor = uuid4()
    svc = _svc(db_session)
    svc.load_from_yaml(_YAML_PATH, actor_id=actor)
    db_session.flush()

    rules = LeaveSanctionRuleRepository(db_session).list_active()

    test_cases = [
        # (user_roles, leave_type, expected_sanctioner)
        (["FACULTY"], "CL",  "DIRECTOR"),   # Lecturer-tier → Director (§22.I.iii)
        (["PROFESSOR"], "CL", "VC"),         # Professor → VC (§22.I.ii)
        (["DIRECTOR"], "CL", "VC"),          # Director → VC (§22.I.ii)
        (["FACULTY"], "SCL", "VC"),          # SCL wildcard → VC (§22.II)
        (["FACULTY"], "EOL", "VC"),          # EOL wildcard → VC (§24)
    ]

    for user_roles, leave_type, expected_sanctioner in test_cases:
        channel = resolve_channel(user_roles, leave_type, rules)
        assert len(channel) > 0, f"Empty channel for {user_roles} + {leave_type}"
        # Last entry must be the non-recommend-only sanctioner
        assert channel[-1]["recommend_only"] is False
        assert channel[-1]["role_code"] == expected_sanctioner, (
            f"Expected sanctioner {expected_sanctioner!r} for {user_roles}+{leave_type}, "
            f"got {channel[-1]['role_code']!r}"
        )

    # SCL must have a recommend-only DIRECTOR stage before VC
    scl_channel = resolve_channel(["FACULTY"], "SCL", rules)
    assert scl_channel[0]["recommend_only"] is True
    assert scl_channel[0]["role_code"] == "DIRECTOR"
    assert len(scl_channel) == 2
