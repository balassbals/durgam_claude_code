"""TemplateConfigState — template upload, replace, deactivate (/admin/config/templates)."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.file_asset import FileAssetRepository
from durgam.repositories.template_asset import TemplateAssetRepository
from durgam.services.template_asset import TemplateAssetService, TemplateError
from durgam.services.upload import UploadService
from durgam.states.base import BaseState
from durgam.storage import get_storage_backend


def _svc(session) -> TemplateAssetService:
    return TemplateAssetService(
        repo=TemplateAssetRepository(session),
        upload_svc=UploadService(
            file_repo=FileAssetRepository(session),
            backend=get_storage_backend(),
        ),
    )


class TemplateConfigState(BaseState):
    templates: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    form_template_type: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_templates(self) -> None:
        guard = self._config_guard("template_asset", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.templates = []
        self.show_form = False
        with open_session() as session:
            for r in _svc(session).list_all():
                self.templates.append({
                    "id": str(r.id),
                    "template_type": r.template_type.upper(),
                    "file_id": str(r.file_id),
                })
        self._load_nav_entries()
        self.loading = False

    def set_form_template_type(self, value: str) -> None:
        self.form_template_type = value

    def open_upload(self):
        self.flash = ""
        self.flash_type = "info"
        self.form_template_type = ""
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="template_asset")
    @audit_action(action="write", resource="template_asset")
    async def upload_template(self, files: list[rx.UploadFile]) -> None:
        if not files:
            self.flash = "No file selected."
            self.flash_type = "error"
            return

        upload_file = files[0]
        file_bytes: bytes = upload_file.file.read()
        original_name = upload_file.filename or "template"
        content_type = upload_file.content_type or "application/octet-stream"
        template_type = self.form_template_type.strip()

        try:
            with open_session() as session:
                _svc(session).upload_template(
                    template_type,
                    file_bytes,
                    original_name,
                    content_type,
                    UUID(self.current_user_id),
                )
                session.commit()
            self.show_form = False
            await self.load_templates()
            self.flash = "Template uploaded."
            self.flash_type = "success"
        except TemplateError as e:
            self.flash = e.message
            self.flash_type = "error"

    def open_deactivate_confirm(self, record_id: str, template_type: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate '{template_type}' template?"
        self.confirm_body = "This will deactivate the template. A new one can be uploaded later."
        self.confirm_open = True

    @require_role(action="delete", resource="template_asset")
    @audit_action(action="delete", resource="template_asset")
    async def soft_delete_template(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id)
                )
                session.commit()
            self.confirm_open = False
            self.confirm_id = ""
            await self.load_templates()
            self.flash = "Template deactivated."
            self.flash_type = "success"
        except TemplateError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_id = ""

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
