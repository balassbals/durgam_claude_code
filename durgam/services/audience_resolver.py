"""AudienceResolver — lazy audience-group evaluation for M9 Announcements.

Strategy (Q1 freeze): audience_group_codes filter is stored on Announcement;
viewer eligibility is resolved at query time by this module. No materialized
recipient table. `groups_user_belongs_to()` is called once per page-load to
pre-compute the viewer's group set, which is then passed to the repository
for a single JSONB ?| query.

Forward concern: `program_degree_types` filter key requires a student enrollment
model (not yet built). `_evaluate_filter` returns False / empty when this key is
present. Tracked in docs/milestones/M9.md scope item D-018 (pending enrollment
milestone).
"""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.models.announcement import Announcement, AudienceGroup
from durgam.models.campus import Campus
from durgam.models.centre import CentreOfExcellence
from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole
from durgam.models.program import Program
from durgam.models.school import School

log = structlog.get_logger(__name__)

# Maps scope_type strings to (Model class, code column attribute)
_SCOPE_TABLE_MAP: dict[str, tuple[type, object]] = {
    "school": (School, School.code),
    "campus": (Campus, Campus.code),
    "department": (Department, Department.code),
    "program": (Program, Program.code),
    "centre": (CentreOfExcellence, CentreOfExcellence.code),
}


class AudienceResolver:
    """Stateless utility — all methods receive a SQLModel Session.

    Typical call sequence for rendering an announcement feed:
    1. Load all active AudienceGroup rows once (repo.list_active()).
    2. Call groups_user_belongs_to(user_id, groups, session) → set of codes.
    3. Pass that set to AnnouncementRepository.list_visible_to_user(...).
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def groups_user_belongs_to(
        self,
        user_id: UUID,
        groups: list[AudienceGroup],
        session: Session,
    ) -> set[str]:
        """Return the codes from `groups` that user_id belongs to."""
        matched: set[str] = set()
        for group in groups:
            if self._evaluate_filter(user_id, group.filter_json, session):
                matched.add(group.code)
        return matched

    def user_can_see(
        self,
        user_id: UUID,
        announcement: Announcement,
        groups_by_code: dict[str, AudienceGroup],
        session: Session,
    ) -> bool:
        """True if user_id is in the effective recipient set of announcement.

        Effective set = (∪ group_members for code in audience_group_codes)
                        ∪ ad_hoc_user_ids
                        − exclude_user_ids
        """
        uid_str = str(user_id)

        # Hard exclusion first (cheapest path)
        if announcement.exclude_user_ids and uid_str in announcement.exclude_user_ids:
            return False

        # Explicit ad-hoc inclusion
        if announcement.ad_hoc_user_ids and uid_str in announcement.ad_hoc_user_ids:
            return True

        # Group-based membership
        for code in announcement.audience_group_codes:
            group = groups_by_code.get(code)
            if group is None:
                continue
            if self._evaluate_filter(user_id, group.filter_json, session):
                return True

        return False

    def resolve_recipients(
        self,
        group_codes: list[str],
        groups_by_code: dict[str, AudienceGroup],
        session: Session,
    ) -> list[UUID]:
        """Return all user IDs that belong to any of the given group codes.

        Used for admin preview and auto-announcement dispatch. May be a large
        result set for groups like ALL — caller should paginate or count only.
        """
        user_id_set: set[UUID] = set()
        for code in group_codes:
            group = groups_by_code.get(code)
            if group is None:
                continue
            matched = self._resolve_filter_recipients(group.filter_json, session)
            user_id_set.update(matched)
        return list(user_id_set)

    # ------------------------------------------------------------------
    # Per-user filter evaluation
    # ------------------------------------------------------------------

    def _evaluate_filter(
        self,
        user_id: UUID,
        filter_json: dict,
        session: Session,
    ) -> bool:
        """Return True if user_id satisfies all criteria in filter_json.

        All filter keys are optional. Missing / empty key = no constraint on
        that dimension. An entirely empty dict means ALL authenticated users.
        """
        role_codes: list[str] = filter_json.get("role_codes") or []
        scope_type: str | None = filter_json.get("scope_type")
        scope_codes: list[str] = filter_json.get("scope_codes") or []
        scope_ids_raw: list[str] = filter_json.get("scope_ids") or []
        program_degree_types: list[str] = filter_json.get("program_degree_types") or []

        # Forward concern: student enrollment model not yet built.
        if program_degree_types:
            return False

        # Empty filter → matches all authenticated users.
        if not role_codes and not scope_type:
            return True

        stmt = (
            select(UserRole)
            .join(Role, UserRole.role_id == Role.id)  # type: ignore[arg-type]
            .where(UserRole.user_id == user_id)
        )

        if role_codes:
            stmt = stmt.where(Role.code.in_(role_codes))

        if scope_type:
            stmt = stmt.where(UserRole.scope_type == scope_type)

            scope_id_set: set[UUID] = set()
            if scope_codes:
                scope_id_set.update(
                    self._resolve_scope_codes(scope_type, scope_codes, session)
                )
            if scope_ids_raw:
                scope_id_set.update(UUID(sid) for sid in scope_ids_raw)

            if scope_id_set:
                stmt = stmt.where(UserRole.scope_id.in_(scope_id_set))

        return session.exec(stmt).first() is not None

    # ------------------------------------------------------------------
    # Bulk recipient resolution (inverse of per-user evaluation)
    # ------------------------------------------------------------------

    def _resolve_filter_recipients(
        self,
        filter_json: dict,
        session: Session,
    ) -> list[UUID]:
        """Return all user IDs matching filter_json. Used by resolve_recipients."""
        role_codes: list[str] = filter_json.get("role_codes") or []
        scope_type: str | None = filter_json.get("scope_type")
        scope_codes: list[str] = filter_json.get("scope_codes") or []
        scope_ids_raw: list[str] = filter_json.get("scope_ids") or []
        program_degree_types: list[str] = filter_json.get("program_degree_types") or []

        # Forward concern: student enrollment model not yet built.
        if program_degree_types:
            return []

        if not role_codes and not scope_type:
            # ALL group: return all active, non-deleted users.
            rows = session.exec(
                select(User.id).where(  # type: ignore[union-attr]
                    User.is_active == True,  # noqa: E712
                    User.is_deleted == False,  # noqa: E712
                )
            ).all()
            return list(rows)

        stmt = (
            select(UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)  # type: ignore[arg-type]
            .distinct()
        )

        if role_codes:
            stmt = stmt.where(Role.code.in_(role_codes))

        if scope_type:
            stmt = stmt.where(UserRole.scope_type == scope_type)

            scope_id_set: set[UUID] = set()
            if scope_codes:
                scope_id_set.update(
                    self._resolve_scope_codes(scope_type, scope_codes, session)
                )
            if scope_ids_raw:
                scope_id_set.update(UUID(sid) for sid in scope_ids_raw)

            if scope_id_set:
                stmt = stmt.where(UserRole.scope_id.in_(scope_id_set))

        rows = session.exec(stmt).all()
        return list(rows)

    # ------------------------------------------------------------------
    # Scope code → ID lookup
    # ------------------------------------------------------------------

    def _resolve_scope_codes(
        self,
        scope_type: str,
        codes: list[str],
        session: Session,
    ) -> list[UUID]:
        """Look up scope entity IDs by their code strings."""
        entry = _SCOPE_TABLE_MAP.get(scope_type)
        if entry is None:
            log.warning(
                "audience_resolver.unknown_scope_type",
                scope_type=scope_type,
            )
            return []

        model_cls, code_col = entry
        rows = session.exec(
            select(model_cls).where(  # type: ignore[arg-type]
                code_col.in_(codes),
                model_cls.is_deleted == False,  # noqa: E712
            )
        ).all()
        return [row.id for row in rows]
