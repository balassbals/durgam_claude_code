"""States for /announcements page (M9 Phase 6b).

Three state classes:
- AnnouncementBrowseState: browse list with tab switching and filters.
- AnnouncementComposerState: compose modal (open/submit/close).
- AnnouncementDetailState: detail side-panel (open/withdraw/close).

All three inherit BaseState directly. Cross-state refresh after save/withdraw
is done via rx.redirect("/announcements"), which triggers on_load → BrowseState.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


def _format_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ── Browse ─────────────────────────────────────────────────────────────────


class AnnouncementBrowseState(BaseState):
    rows: list[dict[str, Any]] = []
    tab: str = "received"
    total: int = 0
    loading: bool = True
    importance_filter: str = "all"
    date_from: str = ""
    date_to: str = ""
    flash: str = ""
    flash_type: str = "info"

    def set_tab(self, value: str) -> None:
        self.tab = value

    def set_importance_filter(self, value: str) -> None:
        self.importance_filter = value

    def set_date_from(self, value: str) -> None:
        self.date_from = value

    def set_date_to(self, value: str) -> None:
        self.date_to = value

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    async def load_announcements(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.loading = True
        self.rows = []
        self.total = 0

        from durgam.repositories.announcement import (
            AnnouncementCategoryRepository,
            AnnouncementComposerConfigRepository,
            AnnouncementRepository,
            AudienceGroupRepository,
        )
        from durgam.services.announcement import AnnouncementService

        from datetime import date as date_type

        imp_filter = None if self.importance_filter == "all" else self.importance_filter
        d_from: date_type | None = None
        d_to: date_type | None = None
        if self.date_from:
            try:
                d_from = date_type.fromisoformat(self.date_from)
            except ValueError:
                pass
        if self.date_to:
            try:
                d_to = date_type.fromisoformat(self.date_to)
            except ValueError:
                pass

        user_id = UUID(self.current_user_id)
        with open_session() as session:
            svc = AnnouncementService(
                repo=AnnouncementRepository(session),
                config_repo=AnnouncementComposerConfigRepository(session),
                category_repo=AnnouncementCategoryRepository(session),
                audience_repo=AudienceGroupRepository(session),
                session=session,
            )
            page, total = svc.list_for_browse(
                viewer_user_id=user_id,
                tab=self.tab,
                importance_filter=imp_filter,
                date_from=d_from,
                date_to=d_to,
            )
            rows = []
            for a in page:
                rows.append({
                    "id": str(a.id),
                    "title": a.title,
                    "category_code": a.category_code,
                    "importance": a.importance,
                    "scheduled_at": _format_dt(a.scheduled_at),
                    "composer_role_code": a.composer_role_code,
                    "is_withdrawn": a.is_deleted,
                    "snippet": (
                        a.message_text[:120] + "…"
                        if len(a.message_text) > 120
                        else a.message_text
                    ),
                })

        self.rows = rows
        self.total = total
        self.loading = False
        self._load_nav_entries()

    async def apply_filters(self) -> None:
        await self.load_announcements()

    async def switch_tab(self, tab: str) -> None:
        self.tab = tab
        self.importance_filter = "all"
        self.date_from = ""
        self.date_to = ""
        await self.load_announcements()


# ── Composer ────────────────────────────────────────────────────────────────


class AnnouncementComposerState(BaseState):
    show_composer: bool = False
    flash: str = ""
    flash_type: str = "info"

    # Form fields
    form_role_code: str = ""
    form_category_code: str = ""
    form_title: str = ""
    form_body_text: str = ""
    form_importance: str = "normal"
    form_scheduled_at: str = ""
    selected_audience_codes: list[str] = []

    # Populated on open_composer
    available_role_codes: list[str] = []
    available_categories: list[dict[str, str]] = []
    available_audience_groups: list[dict[str, str]] = []

    # Staged attachment (Phase 8b — counsellor pattern: bytes held in state, uploaded on save)
    staged_attachment_bytes: bytes = b""
    staged_attachment_name: str = ""
    staged_attachment_mime: str = ""

    # ── Setters ─────────────────────────────────────────────────────────────

    def set_form_role_code(self, value: str) -> None:
        self.form_role_code = value

    def set_form_category_code(self, value: str) -> None:
        self.form_category_code = value

    def set_form_title(self, value: str) -> None:
        self.form_title = value

    def set_form_body_text(self, value: str) -> None:
        self.form_body_text = value

    def set_form_importance(self, value: str) -> None:
        self.form_importance = value

    def set_form_scheduled_at(self, value: str) -> None:
        self.form_scheduled_at = value

    def toggle_audience(self, code: str) -> None:
        if code in self.selected_audience_codes:
            self.selected_audience_codes = [
                c for c in self.selected_audience_codes if c != code
            ]
        else:
            self.selected_audience_codes = self.selected_audience_codes + [code]

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── Handlers ────────────────────────────────────────────────────────────

    def clear_form(self) -> None:
        self.show_composer = False
        self.flash = ""
        self.flash_type = "info"
        self.form_role_code = ""
        self.form_category_code = ""
        self.form_title = ""
        self.form_body_text = ""
        self.form_importance = "normal"
        self.form_scheduled_at = ""
        self.selected_audience_codes = []
        self.available_role_codes = []
        self.available_categories = []
        self.available_audience_groups = []
        self.staged_attachment_bytes = b""
        self.staged_attachment_name = ""
        self.staged_attachment_mime = ""

    async def stage_attachment_file(self, files: list[rx.UploadFile]) -> None:
        """Stage uploaded file bytes in state for later upload on form save.

        Uses the M5a counsellor pattern: on_drop stores bytes in backend state;
        save() uploads them within the same transaction as announcement creation.
        No upload_id staged mode used — on_drop is immediate.
        """
        if not files:
            return
        f = files[0]
        self.staged_attachment_bytes = await f.read()
        self.staged_attachment_name = f.filename or "attachment"
        self.staged_attachment_mime = f.content_type or "application/octet-stream"

    async def open_composer(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        from durgam.repositories.announcement import (
            AnnouncementCategoryRepository,
            AnnouncementComposerConfigRepository,
            AnnouncementRepository,
            AudienceGroupRepository,
        )
        from durgam.services.announcement import (
            AnnouncementService,
        )

        user_id = UUID(self.current_user_id)
        with open_session() as session:
            svc = AnnouncementService(
                repo=AnnouncementRepository(session),
                config_repo=AnnouncementComposerConfigRepository(session),
                category_repo=AnnouncementCategoryRepository(session),
                audience_repo=AudienceGroupRepository(session),
                session=session,
            )
            eligible_roles = svc.list_composer_eligible_roles(user_id)
            if not eligible_roles:
                self.flash = "You are not configured as an announcement composer."
                self.flash_type = "error"
                return

            cat_repo = AnnouncementCategoryRepository(session)
            cats = cat_repo.list_active()
            ag_repo = AudienceGroupRepository(session)
            groups = ag_repo.list_active()

            role_codes = list(eligible_roles)
            categories = [{"code": c.code, "name": c.name} for c in cats]
            audience_groups = [{"code": g.code, "name": g.name} for g in groups]

        self.available_role_codes = role_codes
        self.available_categories = categories
        self.available_audience_groups = audience_groups
        self.form_role_code = role_codes[0] if role_codes else ""
        self.form_category_code = categories[0]["code"] if categories else ""
        self.form_importance = "normal"
        self.selected_audience_codes = []
        self.form_title = ""
        self.form_body_text = ""
        self.form_scheduled_at = ""
        self.flash = ""
        self.flash_type = "info"
        self.show_composer = True

    @require_role(action="create", resource="announcement", scope="*")
    @audit_action(action="create", resource="announcement")
    async def save(self, form_data: dict) -> None:
        title = form_data.get("form_title", "").strip()
        body_text = form_data.get("form_body_text", "").strip()
        role_code = self.form_role_code
        category_code = self.form_category_code
        importance = self.form_importance
        scheduled_at_str = self.form_scheduled_at
        audience_codes = list(self.selected_audience_codes)

        if not title:
            self.flash = "Title is required."
            self.flash_type = "error"
            return
        if not body_text:
            self.flash = "Body text is required."
            self.flash_type = "error"
            return
        if not audience_codes:
            self.flash = "Select at least one audience group."
            self.flash_type = "error"
            return

        scheduled_at: datetime | None = None
        if scheduled_at_str:
            try:
                scheduled_at = datetime.fromisoformat(
                    scheduled_at_str.replace("T", " ")
                ).replace(tzinfo=UTC)
            except ValueError:
                self.flash = "Invalid scheduled date/time."
                self.flash_type = "error"
                return

        from durgam.repositories.announcement import (
            AnnouncementCategoryRepository,
            AnnouncementComposerConfigRepository,
            AnnouncementRepository,
            AudienceGroupRepository,
        )
        from durgam.services.announcement import (
            AnnouncementError,
            AnnouncementService,
        )

        user_id = UUID(self.current_user_id)
        try:
            from durgam.repositories.file_asset import FileAssetRepository
            from durgam.services.upload import UploadService
            from durgam.storage import get_storage_backend

            with open_session() as session:
                file_asset_repo = FileAssetRepository(session)
                upload_svc = UploadService(
                    file_repo=file_asset_repo,
                    backend=get_storage_backend(),
                    allowed_mimes=frozenset({
                        "application/pdf",
                        "image/png",
                        "image/jpeg",
                    }),
                    max_size_mb=2,
                )
                svc = AnnouncementService(
                    repo=AnnouncementRepository(session),
                    config_repo=AnnouncementComposerConfigRepository(session),
                    category_repo=AnnouncementCategoryRepository(session),
                    audience_repo=AudienceGroupRepository(session),
                    session=session,
                    upload_svc=upload_svc,
                    file_asset_repo=file_asset_repo,
                )
                announcement = svc.create_announcement(
                    composer_user_id=user_id,
                    composer_role_code=role_code,
                    category_code=category_code,
                    audience_group_codes=audience_codes,
                    title=title,
                    body_text=body_text,
                    importance=importance,
                    scheduled_at=scheduled_at,
                    actor_id=user_id,
                )
                if self.staged_attachment_bytes:
                    svc.attach_file_to_announcement(
                        announcement_id=announcement.id,
                        file_bytes=self.staged_attachment_bytes,
                        original_name=self.staged_attachment_name,
                        mime_type=self.staged_attachment_mime,
                        actor_id=user_id,
                    )
                ann_id = str(announcement.id)
                session.commit()
            self._set_audit(resource_id=ann_id, after={"title": title, "category_code": category_code})
        except AnnouncementError as e:
            self.flash = e.message
            self.flash_type = "error"
            return

        self.show_composer = False
        self.staged_attachment_bytes = b""
        self.staged_attachment_name = ""
        self.staged_attachment_mime = ""
        return rx.redirect("/announcements")


# ── Detail ──────────────────────────────────────────────────────────────────


class AnnouncementDetailState(BaseState):
    show_detail: bool = False
    detail: dict[str, Any] = {}
    attachments: list[dict[str, str]] = []
    flash: str = ""
    flash_type: str = "info"

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    def close_detail(self) -> None:
        self.show_detail = False
        self.detail = {}
        self.attachments = []
        self.flash = ""
        self.flash_type = "info"

    async def open_detail(self, announcement_id: str) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        from durgam.repositories.announcement import (
            AnnouncementCategoryRepository,
            AnnouncementComposerConfigRepository,
            AnnouncementRepository,
            AudienceGroupRepository,
        )
        from durgam.services.announcement import (
            AnnouncementNotFoundError,
            AnnouncementService,
        )

        user_id = UUID(self.current_user_id)
        try:
            from durgam.repositories.file_asset import FileAssetRepository

            with open_session() as session:
                file_asset_repo = FileAssetRepository(session)
                svc = AnnouncementService(
                    repo=AnnouncementRepository(session),
                    config_repo=AnnouncementComposerConfigRepository(session),
                    category_repo=AnnouncementCategoryRepository(session),
                    audience_repo=AudienceGroupRepository(session),
                    session=session,
                    file_asset_repo=file_asset_repo,
                )
                ann = svc.get_by_id(
                    announcement_id=UUID(announcement_id),
                    viewer_user_id=user_id,
                )
                detail = {
                    "id": str(ann.id),
                    "title": ann.title,
                    "message_text": ann.message_text,
                    "category_code": ann.category_code,
                    "importance": ann.importance,
                    "scheduled_at": _format_dt(ann.scheduled_at),
                    "composer_role_code": ann.composer_role_code,
                    "composer_user_id": str(ann.composer_user_id),
                    "is_withdrawn": ann.is_deleted,
                    "audience_group_codes": ann.audience_group_codes,
                    "is_own": str(ann.composer_user_id) == self.current_user_id,
                }
                attachment_rows = svc.list_attachments(ann.id)
                attachments = [
                    {
                        "file_id": str(a.id),
                        "original_name": a.original_name or "Attachment",
                        "mime_type": a.mime_type or "",
                        "size_bytes": str(a.size_bytes or 0),
                    }
                    for a in attachment_rows
                ]
        except AnnouncementNotFoundError:
            self.flash = "Announcement not found or not visible to you."
            self.flash_type = "error"
            return

        self.detail = detail
        self.attachments = attachments
        self.flash = ""
        self.flash_type = "info"
        self.show_detail = True

    @require_role(action="soft_delete", resource="announcement", scope="own")
    @audit_action(action="withdraw", resource="announcement")
    async def withdraw(self, announcement_id: str) -> None:
        from durgam.repositories.announcement import (
            AnnouncementCategoryRepository,
            AnnouncementComposerConfigRepository,
            AnnouncementRepository,
            AudienceGroupRepository,
        )
        from durgam.services.announcement import (
            AnnouncementError,
            AnnouncementService,
        )
        from durgam.audit.snapshot import audit_snapshot

        user_id = UUID(self.current_user_id)
        try:
            with open_session() as session:
                svc = AnnouncementService(
                    repo=AnnouncementRepository(session),
                    config_repo=AnnouncementComposerConfigRepository(session),
                    category_repo=AnnouncementCategoryRepository(session),
                    audience_repo=AudienceGroupRepository(session),
                    session=session,
                )
                ann = svc.withdraw_announcement(
                    announcement_id=UUID(announcement_id),
                    actor_id=user_id,
                )
                ann_id = str(ann.id)
                snap = audit_snapshot(ann)
                session.commit()
            self._set_audit(resource_id=ann_id, after=snap)
        except AnnouncementError as e:
            self.flash = e.message
            self.flash_type = "error"
            return

        self.show_detail = False
        self.detail = {}
        return rx.redirect("/announcements")
