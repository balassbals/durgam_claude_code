"""AudienceGroupService — audience group CRUD with filter_json validation (M9 Phase 5b).

The service takes a session directly (not just the repo) because _validate_filter_json
must query roles + scope tables. This is a declared layering deviation — see Phase 5b
report. The session is read-only in validation paths (no flush/commit).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.models.announcement import AudienceGroup
from durgam.repositories.announcement import AudienceGroupRepository

log = structlog.get_logger(__name__)

_CODE_PATTERN = re.compile(r"^[A-Z][A-Z_0-9]*$")
_ALLOWED_FILTER_KEYS = frozenset(
    {"role_codes", "scope_type", "scope_codes", "scope_ids", "program_degree_types"}
)
_VALID_SCOPE_TYPES = frozenset({"school", "department", "campus", "program", "centre"})

# Maps scope_type → (table_name, code_column) for raw code fetches.
# Using model imports to avoid raw SQL strings (layering-compliant).
_SCOPE_MODEL_IMPORTS: dict[str, str] = {
    "school": "durgam.models.school.School",
    "department": "durgam.models.department.Department",
    "campus": "durgam.models.campus.Campus",
    "program": "durgam.models.program.Program",
    "centre": "durgam.models.centre.CentreOfExcellence",
}


class AudienceGroupError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AudienceGroupService:
    def __init__(self, repo: AudienceGroupRepository, session: Session) -> None:
        self._repo = repo
        self._session = session

    # ── Public API ────────────────────────────────────────────────────────────

    def list_all(self) -> list[AudienceGroup]:
        return self._repo.list_all()

    def create(
        self,
        *,
        code: str,
        name: str,
        description: str | None,
        filter_json: dict[str, Any],
        is_active: bool,
        actor_id: UUID,
    ) -> AudienceGroup:
        code = code.strip().upper()
        name = name.strip()
        self._validate_create(code, name)
        self._validate_filter_json(filter_json)
        if self._repo.get_by_code(code) is not None:
            raise AudienceGroupError(f"Code '{code}' already exists.")
        now = datetime.now(UTC)
        group = AudienceGroup(
            code=code,
            name=name,
            description=description or None,
            filter_json=filter_json,
            is_active=is_active,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        group = self._repo.create(group)
        log.info("audience_group_created", code=code, actor=str(actor_id))
        return group

    def update(
        self,
        *,
        id_: UUID,
        name: str,
        description: str | None,
        filter_json: dict[str, Any],
        is_active: bool,
        actor_id: UUID,
    ) -> AudienceGroup:
        group = self._repo.get(id_)
        if group is None:
            raise AudienceGroupError("Audience group not found.")
        name = name.strip()
        if not name:
            raise AudienceGroupError("Name is required.")
        self._validate_filter_json(filter_json)
        group = self._repo.update(
            id_,
            name=name,
            description=description or None,
            filter_json=filter_json,
            is_active=is_active,
            updated_by=actor_id,
        )
        log.info("audience_group_updated", group_id=str(id_), actor=str(actor_id))
        return group

    def soft_delete(self, *, id_: UUID, actor_id: UUID) -> None:
        group = self._repo.get(id_)
        if group is None:
            raise AudienceGroupError("Audience group not found.")
        self._repo.soft_delete(id_, actor_id)
        log.info("audience_group_soft_deleted", group_id=str(id_), actor=str(actor_id))

    def list_scope_codes_for_type(self, scope_type: str) -> list[str]:
        """Return all non-deleted codes for the given scope_type entity, sorted."""
        if scope_type not in _VALID_SCOPE_TYPES:
            return []
        module_path, cls_name = _SCOPE_MODEL_IMPORTS[scope_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        model_cls = getattr(module, cls_name)
        rows = self._session.exec(
            select(model_cls).where(model_cls.is_deleted == False)  # noqa: E712
        ).all()
        return sorted(r.code for r in rows)

    # ── Private validation ────────────────────────────────────────────────────

    def _validate_create(self, code: str, name: str) -> None:
        if not code:
            raise AudienceGroupError("Code is required.")
        if not _CODE_PATTERN.match(code):
            raise AudienceGroupError(
                "Code must start with an uppercase letter and contain only A–Z, digits, and underscores."
            )
        if not name:
            raise AudienceGroupError("Name is required.")

    def _validate_filter_json(self, filter_json: dict[str, Any]) -> None:
        if not isinstance(filter_json, dict):
            raise AudienceGroupError("filter_json must be a dict.")
        unknown = set(filter_json.keys()) - _ALLOWED_FILTER_KEYS
        if unknown:
            raise AudienceGroupError(
                f"Unknown filter_json keys: {', '.join(sorted(unknown))}."
            )

        role_codes = filter_json.get("role_codes")
        if role_codes is not None:
            if not isinstance(role_codes, list):
                raise AudienceGroupError("filter_json.role_codes must be a list.")
            if role_codes:
                existing = self._fetch_role_codes(role_codes)
                missing = [c for c in role_codes if c not in existing]
                if missing:
                    raise AudienceGroupError(
                        f"Unknown role codes: {', '.join(missing)}."
                    )

        scope_type = filter_json.get("scope_type")
        if scope_type is not None:
            if scope_type not in _VALID_SCOPE_TYPES:
                raise AudienceGroupError(
                    f"Invalid scope_type '{scope_type}'. "
                    f"Must be one of: {', '.join(sorted(_VALID_SCOPE_TYPES))}."
                )

        scope_codes = filter_json.get("scope_codes")
        if scope_codes is not None:
            if scope_type is None:
                raise AudienceGroupError(
                    "filter_json.scope_codes requires scope_type to also be set."
                )
            if not isinstance(scope_codes, list):
                raise AudienceGroupError("filter_json.scope_codes must be a list.")
            if scope_codes:
                existing = self._fetch_scope_codes(scope_type, scope_codes)
                missing = [c for c in scope_codes if c not in existing]
                if missing:
                    raise AudienceGroupError(
                        f"Unknown {scope_type} codes: {', '.join(missing)}."
                    )

        program_degree_types = filter_json.get("program_degree_types")
        if program_degree_types is not None:
            if not isinstance(program_degree_types, list):
                raise AudienceGroupError(
                    "filter_json.program_degree_types must be a list."
                )
            if not all(isinstance(t, str) for t in program_degree_types):
                raise AudienceGroupError(
                    "filter_json.program_degree_types must be a list of strings."
                )

    def _fetch_role_codes(self, codes: list[str]) -> set[str]:
        from durgam.models.identity import Role

        rows = self._session.exec(
            select(Role).where(
                Role.code.in_(codes),  # type: ignore[arg-type]
                Role.is_deleted == False,  # noqa: E712
            )
        ).all()
        return {r.code for r in rows}

    def _fetch_scope_codes(self, scope_type: str, codes: list[str]) -> set[str]:
        module_path, cls_name = _SCOPE_MODEL_IMPORTS[scope_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        model_cls = getattr(module, cls_name)
        rows = self._session.exec(
            select(model_cls).where(
                model_cls.code.in_(codes),  # type: ignore[arg-type]
                model_cls.is_deleted == False,  # noqa: E712
            )
        ).all()
        return {r.code for r in rows}
