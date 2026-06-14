"""Services for announcement config entities: composer config + categories (M9 Phase 5a)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.announcement import AnnouncementCategory, AnnouncementComposerConfig
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
)

log = structlog.get_logger(__name__)


class AnnouncementConfigError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AnnouncementComposerConfigService:
    def __init__(self, repo: AnnouncementComposerConfigRepository) -> None:
        self._repo = repo

    def list_all(self) -> list[AnnouncementComposerConfig]:
        return self._repo.list_all()

    def create(
        self,
        *,
        role_code: str,
        priority_rank: int,
        scope_restriction: str | None,
        enabled: bool,
        notes: str | None,
        actor_id: UUID,
    ) -> AnnouncementComposerConfig:
        role_code = role_code.strip().upper()
        if not role_code:
            raise AnnouncementConfigError("Role code is required.")
        if priority_rank < 1:
            raise AnnouncementConfigError("Priority rank must be at least 1.")
        if self._repo.get_by_role_code(role_code) is not None:
            raise AnnouncementConfigError(f"Role code '{role_code}' already has a composer config.")
        now = datetime.now(UTC)
        config = AnnouncementComposerConfig(
            role_code=role_code,
            priority_rank=priority_rank,
            scope_restriction=scope_restriction or None,
            enabled=enabled,
            notes=notes or None,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        config = self._repo.create(config)
        log.info("composer_config_created", role_code=role_code, actor=str(actor_id))
        return config

    def update(self, id_: UUID, fields: dict, actor_id: UUID) -> AnnouncementComposerConfig:
        config = self._repo.get(id_)
        if config is None:
            raise AnnouncementConfigError("Composer config not found.")
        if "priority_rank" in fields and fields["priority_rank"] < 1:
            raise AnnouncementConfigError("Priority rank must be at least 1.")
        fields["updated_by"] = actor_id
        config = self._repo.update(id_, **fields)
        log.info("composer_config_updated", config_id=str(id_), actor=str(actor_id))
        return config

    def soft_delete(self, id_: UUID, actor_id: UUID) -> None:
        config = self._repo.get(id_)
        if config is None:
            raise AnnouncementConfigError("Composer config not found.")
        self._repo.soft_delete(id_, actor_id)
        log.info("composer_config_soft_deleted", config_id=str(id_), actor=str(actor_id))


class AnnouncementCategoryService:
    def __init__(self, repo: AnnouncementCategoryRepository) -> None:
        self._repo = repo

    def list_all(self) -> list[AnnouncementCategory]:
        return self._repo.list_all()

    @staticmethod
    def _validate_delay(seconds: int) -> int:
        if seconds < 0 or seconds > 86400:
            raise AnnouncementConfigError(
                "Publish delay must be between 0 and 86400 seconds (24 hours)."
            )
        return seconds

    def create(
        self,
        *,
        code: str,
        name: str,
        display_order: int,
        is_active: bool,
        publish_delay_seconds: int = 0,
        notes: str | None,
        actor_id: UUID,
    ) -> AnnouncementCategory:
        code = code.strip().upper()
        name = name.strip()
        if not code:
            raise AnnouncementConfigError("Category code is required.")
        if not name:
            raise AnnouncementConfigError("Category name is required.")
        if self._repo.get_by_code(code) is not None:
            raise AnnouncementConfigError(f"Category code '{code}' is already in use.")
        self._validate_delay(publish_delay_seconds)
        now = datetime.now(UTC)
        category = AnnouncementCategory(
            code=code,
            name=name,
            display_order=display_order,
            is_active=is_active,
            publish_delay_seconds=publish_delay_seconds,
            notes=notes or None,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        category = self._repo.create(category)
        log.info("announcement_category_created", code=code, actor=str(actor_id))
        return category

    def update(self, id_: UUID, fields: dict, actor_id: UUID) -> AnnouncementCategory:
        category = self._repo.get(id_)
        if category is None:
            raise AnnouncementConfigError("Announcement category not found.")
        if "name" in fields:
            name = (fields["name"] or "").strip()
            if not name:
                raise AnnouncementConfigError("Category name is required.")
            fields["name"] = name
        if "publish_delay_seconds" in fields:
            self._validate_delay(fields["publish_delay_seconds"])
        fields["updated_by"] = actor_id
        category = self._repo.update(id_, **fields)
        log.info("announcement_category_updated", category_id=str(id_), actor=str(actor_id))
        return category

    def soft_delete(self, id_: UUID, actor_id: UUID) -> None:
        category = self._repo.get(id_)
        if category is None:
            raise AnnouncementConfigError("Announcement category not found.")
        self._repo.soft_delete(id_, actor_id)
        log.info("announcement_category_soft_deleted", category_id=str(id_), actor=str(actor_id))
