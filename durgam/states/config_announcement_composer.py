"""AnnouncementComposerConfigState — composer roster CRUD (SysAdmin only, M9 Phase 5a)."""

from __future__ import annotations

from uuid import UUID

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.announcement import AnnouncementComposerConfigRepository
from durgam.services.announcement_config import (
    AnnouncementComposerConfigService,
    AnnouncementConfigError,
)
from durgam.states.base import BaseState


def _svc(session) -> AnnouncementComposerConfigService:
    return AnnouncementComposerConfigService(
        repo=AnnouncementComposerConfigRepository(session),
    )


class AnnouncementComposerConfigState(BaseState):
    configs: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_role_code: str = ""
    form_priority_rank: int = 10
    form_scope_restriction: str = ""
    form_enabled: bool = True
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_composer_configs(self) -> None:
        guard = self._config_guard("announcement_composer_config", "configure")
        if guard is not None:
            return guard
        self.loading = True
        self.configs = []
        self.show_form = False

        with open_session() as session:
            svc = _svc(session)
            for c in svc.list_all():
                self.configs.append({
                    "id": str(c.id),
                    "role_code": c.role_code,
                    "priority_rank": str(c.priority_rank),
                    "scope_restriction": c.scope_restriction or "—",
                    "enabled": "Yes" if c.enabled else "No",
                    "notes": c.notes or "",
                    # raw values for edit form
                    "raw_scope_restriction": c.scope_restriction or "",
                    "raw_enabled": "1" if c.enabled else "0",
                    "raw_notes": c.notes or "",
                })

        self._load_nav_entries()
        self.loading = False

    def set_form_role_code(self, v: str) -> None:
        self.form_role_code = v

    def set_form_priority_rank(self, v: str) -> None:
        try:
            self.form_priority_rank = max(1, int(v))
        except (ValueError, TypeError):
            self.form_priority_rank = 1

    def set_form_scope_restriction(self, v: str) -> None:
        self.form_scope_restriction = "" if v == "none" else v

    def set_form_enabled(self, v: bool) -> None:
        self.form_enabled = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_role_code = ""
        self.form_priority_rank = 10
        self.form_scope_restriction = ""
        self.form_enabled = True
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self,
        cfg_id: str,
        role_code: str,
        priority_rank: str,
        scope_restriction: str,
        enabled: str,
        notes: str,
    ) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = cfg_id
        self.form_role_code = role_code
        try:
            self.form_priority_rank = int(priority_rank)
        except (ValueError, TypeError):
            self.form_priority_rank = 10
        self.form_scope_restriction = scope_restriction
        self.form_enabled = enabled == "1"
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="configure", resource="announcement_composer_config")
    @audit_action(action="configure", resource="announcement_composer_config")
    async def save_config(self, form_data: dict) -> None:
        role_code = form_data.get("form_role_code", "").strip()
        priority_rank_raw = form_data.get("form_priority_rank", "10")
        editing_id = form_data.get("editing_id", "").strip()

        try:
            priority_rank = max(1, int(priority_rank_raw))
        except (ValueError, TypeError):
            priority_rank = 10

        scope_restriction = self.form_scope_restriction.strip() or None
        enabled = self.form_enabled
        notes = self.form_notes.strip() or None

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    entity = svc.create(
                        role_code=role_code,
                        priority_rank=priority_rank,
                        scope_restriction=scope_restriction,
                        enabled=enabled,
                        notes=notes,
                        actor_id=actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    repo = AnnouncementComposerConfigRepository(session)
                    before_snap = audit_snapshot(repo.get(UUID(editing_id)))
                    entity = svc.update(
                        UUID(editing_id),
                        {
                            "priority_rank": priority_rank,
                            "scope_restriction": scope_restriction,
                            "enabled": enabled,
                            "notes": notes,
                        },
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
        except AnnouncementConfigError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return

        self.show_form = False
        self.editing_id = ""
        await self.load_composer_configs()
        self.flash = "Composer config saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, cfg_id: str, role_code: str) -> None:
        self.confirm_id = cfg_id
        self.confirm_title = f"Remove '{role_code}'?"
        self.confirm_body = (
            f"This will remove {role_code} from the composer roster. "
            "Existing announcements are not affected."
        )
        self.confirm_open = True

    @require_role(action="configure", resource="announcement_composer_config")
    @audit_action(action="configure", resource="announcement_composer_config")
    async def soft_delete_config(self) -> None:
        try:
            with open_session() as session:
                repo = AnnouncementComposerConfigRepository(session)
                entity = repo.get(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(UUID(self.confirm_id), UUID(self.current_user_id))
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
        except AnnouncementConfigError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return

        self.confirm_open = False
        self.confirm_id = ""
        await self.load_composer_configs()
        self.flash = "Composer config removed."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
