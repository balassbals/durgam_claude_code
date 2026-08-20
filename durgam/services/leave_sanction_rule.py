"""LeaveSanctionRuleService — CRUD and YAML loader for the sanctioning matrix (M8).

Audit rows written directly inside the service transaction (M6a pattern).
Permission checks use can() from durgam.auth.permissions.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog
import yaml

from durgam.audit.log import write_audit_row
from durgam.audit.snapshot import audit_snapshot
from durgam.auth.permissions import PermissionDenied, can
from durgam.models.leave import LeaveSanctionAuthorityRule
from durgam.repositories.leave import LeaveSanctionRuleRepository

log = structlog.get_logger(__name__)

# Required keys on every YAML rule entry
_REQUIRED_RULE_KEYS = frozenset(
    {"leave_type", "applicant_role_code", "sanctioner_role_code", "priority"}
)


class LeaveSanctionRuleError(Exception):
    """Domain errors for the leave sanction rule service."""


def _rule_to_dict(raw: dict) -> dict[str, Any]:
    """Validate and normalise a single YAML rule entry."""
    missing = _REQUIRED_RULE_KEYS - set(raw.keys())
    if missing:
        raise LeaveSanctionRuleError(
            f"YAML rule missing required keys: {sorted(missing)!r}. Rule: {raw}"
        )
    return {
        "leave_type": str(raw["leave_type"]),
        "applicant_role_code": str(raw["applicant_role_code"]),
        "applicant_designation_regex": raw.get("applicant_designation_regex"),
        "sanctioner_role_code": str(raw["sanctioner_role_code"]),
        "recommend_via_role_code": raw.get("recommend_via_role_code"),
        # M10 Phase 10B (Q-P10) — optional designation/employee-type keying +
        # resolver-based recommend stage + opt-in gate. Absent fields → wildcard /
        # default, preserving every pre-10B rule unchanged.
        "applicant_designation_codes": raw.get("applicant_designation_codes"),
        "applicant_employee_types": raw.get("applicant_employee_types"),
        "recommend_via_resolver": raw.get("recommend_via_resolver"),
        "requires_optin": bool(raw.get("requires_optin", False)),
        "requires_in_charge": bool(raw.get("requires_in_charge", False)),
        "scope_type": raw.get("scope_type"),
        "notes": raw.get("notes"),
        "priority": int(raw["priority"]),
    }


class LeaveSanctionRuleService:
    """CRUD and YAML loader for LeaveSanctionAuthorityRule."""

    def __init__(
        self, session: Any, repo: LeaveSanctionRuleRepository
    ) -> None:
        self._session = session
        self._repo = repo

    # ── CRUD methods (require 'configure' permission on leave_sanction_rule) ──

    def list_rules(self) -> list[LeaveSanctionAuthorityRule]:
        return self._repo.list_active()

    def create_rule(
        self,
        leave_type: str,
        applicant_role_code: str,
        sanctioner_role_code: str,
        priority: int = 100,
        *,
        actor_id: UUID,
        recommend_via_role_code: str | None = None,
        requires_in_charge: bool = False,
        scope_type: str | None = None,
        notes: str | None = None,
        applicant_designation_regex: str | None = None,
    ) -> LeaveSanctionAuthorityRule:
        if not can(actor_id, "configure", "leave_sanction_rule", "*", None, self._session):
            raise PermissionDenied(actor_id, "configure", "leave_sanction_rule")

        now = datetime.now(UTC)
        rule = LeaveSanctionAuthorityRule(
            id=uuid4(),
            leave_type=leave_type,
            applicant_role_code=applicant_role_code,
            applicant_designation_regex=applicant_designation_regex,
            sanctioner_role_code=sanctioner_role_code,
            recommend_via_role_code=recommend_via_role_code,
            requires_in_charge=requires_in_charge,
            scope_type=scope_type,
            notes=notes,
            priority=priority,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._repo.add(rule)
        after_snap = audit_snapshot(rule)
        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="create",
            resource="leave_sanction_rule",
            resource_id=str(rule.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after=after_snap,
            session=self._session,
        )
        log.info("leave_sanction_rule_created", rule_id=str(rule.id), actor=str(actor_id))
        return rule

    def update_rule(
        self,
        rule_id: UUID,
        fields: dict[str, Any],
        actor_id: UUID,
    ) -> LeaveSanctionAuthorityRule:
        if not can(actor_id, "configure", "leave_sanction_rule", "*", None, self._session):
            raise PermissionDenied(actor_id, "configure", "leave_sanction_rule")

        rule = self._repo.get(rule_id)
        if rule is None:
            raise LeaveSanctionRuleError(f"Rule {rule_id} not found.")

        before_snap = audit_snapshot(rule)
        for key, value in fields.items():
            setattr(rule, key, value)
        rule.updated_by = actor_id
        rule = self._repo.save(rule)
        after_snap = audit_snapshot(rule)
        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="update",
            resource="leave_sanction_rule",
            resource_id=str(rule.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after=after_snap,
            session=self._session,
        )
        return rule

    def soft_delete_rule(self, rule_id: UUID, actor_id: UUID) -> None:
        if not can(actor_id, "configure", "leave_sanction_rule", "*", None, self._session):
            raise PermissionDenied(actor_id, "configure", "leave_sanction_rule")

        rule = self._repo.get(rule_id)
        if rule is None:
            raise LeaveSanctionRuleError(f"Rule {rule_id} not found.")

        before_snap = audit_snapshot(rule)
        self._repo.soft_delete(rule_id, actor_id)
        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="delete",
            resource="leave_sanction_rule",
            resource_id=str(rule_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after=None,
            session=self._session,
        )
        log.info("leave_sanction_rule_deleted", rule_id=str(rule_id), actor=str(actor_id))

    # ── YAML loader (no permission check — called from seed.py as sys_admin) ──

    def load_from_yaml(
        self, path: str | Path, actor_id: UUID
    ) -> dict[str, int]:
        """Idempotent: upsert on (leave_type, applicant_role_code, sanctioner_role_code, priority).

        Returns {'inserted': int, 'updated': int, 'orphaned_soft_deleted': int}.
        Orphans = rules currently active in DB whose natural key does not appear in YAML;
        they are soft-deleted.
        Audit rows are written for each insert, update, and soft-delete.
        """
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not isinstance(raw, dict) or "rules" not in raw:
            raise LeaveSanctionRuleError(
                f"YAML at {path} must have a top-level 'rules' list."
            )
        if not isinstance(raw["rules"], list):
            raise LeaveSanctionRuleError(
                f"'rules' in {path} must be a list."
            )

        yaml_rules = [_rule_to_dict(r) for r in raw["rules"]]

        # Build a set of YAML natural keys for orphan detection
        yaml_keys: set[tuple] = {
            (r["leave_type"], r["applicant_role_code"], r["sanctioner_role_code"], r["priority"])
            for r in yaml_rules
        }

        inserted = 0
        updated = 0

        for rule_dict in yaml_rules:
            existing = self._repo.find_by_natural_key(
                leave_type=rule_dict["leave_type"],
                applicant_role_code=rule_dict["applicant_role_code"],
                sanctioner_role_code=rule_dict["sanctioner_role_code"],
                priority=rule_dict["priority"],
            )
            if existing is None:
                # Insert
                now = datetime.now(UTC)
                rule = LeaveSanctionAuthorityRule(
                    id=uuid4(),
                    created_by=actor_id,
                    updated_by=actor_id,
                    created_at=now,
                    updated_at=now,
                    **rule_dict,
                )
                self._repo.add(rule)
                after_snap = audit_snapshot(rule)
                write_audit_row(
                    actor_user_id=actor_id,
                    actor_role_code=None,
                    action="create",
                    resource="leave_sanction_rule",
                    resource_id=str(rule.id),
                    request_id=None,
                    ip=None,
                    user_agent=None,
                    before=None,
                    after=after_snap,
                    session=self._session,
                )
                inserted += 1
            else:
                # Possibly update if any field changed; resurrect if soft-deleted
                before_snap = audit_snapshot(existing)
                changed = existing.is_deleted  # resurrection counts as update
                for key, value in rule_dict.items():
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed = True
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.deleted_by = None

                if changed:
                    existing.updated_by = actor_id
                    self._repo.save(existing)
                    after_snap = audit_snapshot(existing)
                    write_audit_row(
                        actor_user_id=actor_id,
                        actor_role_code=None,
                        action="update",
                        resource="leave_sanction_rule",
                        resource_id=str(existing.id),
                        request_id=None,
                        ip=None,
                        user_agent=None,
                        before=before_snap,
                        after=after_snap,
                        session=self._session,
                    )
                    updated += 1

        # Soft-delete orphans: active DB rules whose natural key is NOT in YAML
        orphaned = 0
        all_active = self._repo.list_active()
        for rule in all_active:
            key = (rule.leave_type, rule.applicant_role_code, rule.sanctioner_role_code, rule.priority)
            if key not in yaml_keys:
                before_snap = audit_snapshot(rule)
                self._repo.soft_delete(rule.id, actor_id)
                write_audit_row(
                    actor_user_id=actor_id,
                    actor_role_code=None,
                    action="delete",
                    resource="leave_sanction_rule",
                    resource_id=str(rule.id),
                    request_id=None,
                    ip=None,
                    user_agent=None,
                    before=before_snap,
                    after=None,
                    session=self._session,
                )
                orphaned += 1

        log.info(
            "leave_matrix_loaded",
            path=str(path),
            inserted=inserted,
            updated=updated,
            orphaned_soft_deleted=orphaned,
        )
        return {"inserted": inserted, "updated": updated, "orphaned_soft_deleted": orphaned}
