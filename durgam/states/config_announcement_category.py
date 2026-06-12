"""AnnouncementCategoryConfigState — announcement category CRUD (Registrar-tier, M9 Phase 5a)."""

from __future__ import annotations

from uuid import UUID

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.announcement import AnnouncementCategoryRepository
from durgam.services.announcement_config import (
    AnnouncementCategoryService,
    AnnouncementConfigError,
)
from durgam.states.base import BaseState


def _svc(session) -> AnnouncementCategoryService:
    return AnnouncementCategoryService(
        repo=AnnouncementCategoryRepository(session),
    )


class AnnouncementCategoryConfigState(BaseState):
    categories: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_name: str = ""
    form_display_order: int = 0
    form_is_active: bool = True
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_categories(self) -> None:
        guard = self._config_guard("announcement_category", "configure")
        if guard is not None:
            return guard
        self.loading = True
        self.categories = []
        self.show_form = False

        with open_session() as session:
            svc = _svc(session)
            for c in svc.list_all():
                self.categories.append({
                    "id": str(c.id),
                    "code": c.code,
                    "name": c.name,
                    "display_order": str(c.display_order),
                    "active": "Yes" if c.is_active else "No",
                    "notes": c.notes or "",
                    # raw for edit
                    "raw_is_active": "1" if c.is_active else "0",
                    "raw_notes": c.notes or "",
                })

        self._load_nav_entries()
        self.loading = False

    def set_form_code(self, v: str) -> None:
        self.form_code = v

    def set_form_name(self, v: str) -> None:
        self.form_name = v

    def set_form_display_order(self, v: str) -> None:
        try:
            self.form_display_order = max(0, int(v))
        except (ValueError, TypeError):
            self.form_display_order = 0

    def set_form_is_active(self, v: bool) -> None:
        self.form_is_active = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_display_order = 0
        self.form_is_active = True
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self,
        cat_id: str,
        code: str,
        name: str,
        display_order: str,
        is_active: str,
        notes: str,
    ) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = cat_id
        self.form_code = code
        self.form_name = name
        try:
            self.form_display_order = int(display_order)
        except (ValueError, TypeError):
            self.form_display_order = 0
        self.form_is_active = is_active == "1"
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="configure", resource="announcement_category")
    @audit_action(action="configure", resource="announcement_category")
    async def save_category(self, form_data: dict) -> None:
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        display_order_raw = form_data.get("form_display_order", "0")
        editing_id = form_data.get("editing_id", "").strip()

        try:
            display_order = max(0, int(display_order_raw))
        except (ValueError, TypeError):
            display_order = 0

        is_active = self.form_is_active
        notes = self.form_notes.strip() or None

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    entity = svc.create(
                        code=code,
                        name=name,
                        display_order=display_order,
                        is_active=is_active,
                        notes=notes,
                        actor_id=actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    repo = AnnouncementCategoryRepository(session)
                    before_snap = audit_snapshot(repo.get(UUID(editing_id)))
                    entity = svc.update(
                        UUID(editing_id),
                        {
                            "name": name,
                            "display_order": display_order,
                            "is_active": is_active,
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
        await self.load_categories()
        self.flash = "Announcement category saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, cat_id: str, code: str) -> None:
        self.confirm_id = cat_id
        self.confirm_title = f"Remove category '{code}'?"
        self.confirm_body = (
            f"This will remove the '{code}' category. "
            "Existing announcements using this category are not affected."
        )
        self.confirm_open = True

    @require_role(action="configure", resource="announcement_category")
    @audit_action(action="configure", resource="announcement_category")
    async def soft_delete_category(self) -> None:
        try:
            with open_session() as session:
                repo = AnnouncementCategoryRepository(session)
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
        await self.load_categories()
        self.flash = "Announcement category removed."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
