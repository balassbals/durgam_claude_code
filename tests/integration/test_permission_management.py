"""Integration tests for PermissionRepository (seed-only policy)."""

from __future__ import annotations

from sqlmodel import Session

from durgam.repositories.permission import PermissionRepository


class TestPermissionRepository:
    def test_list_grouped_by_resource_returns_seeded_permissions(
        self, seeded_session: Session
    ) -> None:
        repo = PermissionRepository(seeded_session)
        grouped = repo.list_grouped_by_resource()
        assert len(grouped) > 0
        # All seeded resources must appear
        resources = set(grouped.keys())
        assert "user" in resources
        assert "role" in resources

    def test_get_by_triple_finds_seeded_permission(self, seeded_session: Session) -> None:
        repo = PermissionRepository(seeded_session)
        perm = repo.get_by_triple("user", "read", "*")
        assert perm is not None
        assert perm.resource == "user"
        assert perm.action == "read"
        assert perm.scope == "*"

    def test_get_by_triple_returns_none_for_unknown(self, seeded_session: Session) -> None:
        repo = PermissionRepository(seeded_session)
        perm = repo.get_by_triple("nonexistent", "action", "scope")
        assert perm is None

    def test_permissions_sorted_within_resource(self, seeded_session: Session) -> None:
        repo = PermissionRepository(seeded_session)
        grouped = repo.list_grouped_by_resource()
        for resource, perms in grouped.items():
            actions = [p.action for p in perms]
            assert actions == sorted(actions), f"Permissions for {resource!r} not sorted by action"
