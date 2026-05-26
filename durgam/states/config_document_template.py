"""DocumentTemplateConfigState — unified letterhead + template management (E-005).

Provides two state classes:
  - LetterheadConfigState for /admin/config/letterheads
  - TemplateConfigState for /admin/config/templates

Both backed by the unified DocumentTemplate model + DocumentTemplateService.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.document_template import DocumentTemplateRepository
from durgam.repositories.file_asset import FileAssetRepository
from durgam.scopes.registry import load_scope_objects
from durgam.services.document_template import DocumentTemplateError, DocumentTemplateService
from durgam.services.upload import UploadService
from durgam.states.base import BaseState
from durgam.storage import get_storage_backend


def _svc(session) -> DocumentTemplateService:
    return DocumentTemplateService(
        repo=DocumentTemplateRepository(session),
        upload_svc=UploadService(
            file_repo=FileAssetRepository(session),
            backend=get_storage_backend(),
        ),
    )


class LetterheadConfigState(BaseState):
    letterheads: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    form_role_code: str = ""
    form_scope_type: str = ""
    form_scope_type_ui: str = "global"
    form_scope_id: str = ""
    scope_objects_dropdown: list[dict] = []

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_letterheads(self) -> None:
        guard = self._config_guard("letterhead_asset", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.letterheads = []
        self.show_form = False
        with open_session() as session:
            for r in _svc(session).list_letterheads():
                scope_label = "Global"
                if r.scope_type:
                    scope_label = f"{r.scope_type}: {r.scope_id}"
                self.letterheads.append({
                    "id": str(r.id),
                    "role_code": r.role_code or "",
                    "scope": scope_label,
                    "file_id": str(r.file_id),
                })
        self._load_nav_entries()
        self.loading = False

    def _load_scope_objects(self) -> None:
        if not self.form_scope_type or self.form_scope_type == "":
            self.scope_objects_dropdown = []
            return
        with open_session() as session:
            self.scope_objects_dropdown = load_scope_objects(
                self.form_scope_type, session,
            )

    def set_form_role_code(self, value: str) -> None:
        self.form_role_code = value

    def set_form_scope_type_ui(self, value: str) -> None:
        real = "" if value == "global" else value
        self.form_scope_type_ui = value
        self.form_scope_type = real
        self.form_scope_id = ""
        self._load_scope_objects()

    def set_form_scope_id(self, value: str) -> None:
        self.form_scope_id = value

    def open_upload(self):
        self.flash = ""
        self.flash_type = "info"
        self.form_role_code = ""
        self.form_scope_type = ""
        self.form_scope_type_ui = "global"
        self.form_scope_id = ""
        self.scope_objects_dropdown = []
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="letterhead_asset")
    @audit_action(action="write", resource="letterhead_asset")
    async def upload_letterhead(self, files: list[rx.UploadFile]) -> None:
        if not files:
            self.flash = "No file selected."
            self.flash_type = "error"
            return

        upload_file = files[0]
        file_bytes: bytes = upload_file.file.read()
        original_name = upload_file.filename or "letterhead"
        content_type = upload_file.content_type or "application/octet-stream"
        role_code = self.form_role_code.strip()
        scope_type = self.form_scope_type.strip() or None
        scope_id_str = self.form_scope_id.strip()
        scope_id = UUID(scope_id_str) if scope_id_str else None

        try:
            with open_session() as session:
                _svc(session).upload_letterhead(
                    role_code,
                    file_bytes,
                    original_name,
                    content_type,
                    UUID(self.current_user_id),
                    scope_type=scope_type,
                    scope_id=scope_id,
                )
                session.commit()
            self.show_form = False
            await self.load_letterheads()
            self.flash = "Letterhead uploaded."
            self.flash_type = "success"
        except DocumentTemplateError as e:
            self.flash = e.message
            self.flash_type = "error"

    def open_deactivate_confirm(self, record_id: str, role_code: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate letterhead for '{role_code}'?"
        self.confirm_body = "This will deactivate the letterhead. A new one can be uploaded later."
        self.confirm_open = True

    @require_role(action="delete", resource="letterhead_asset")
    @audit_action(action="delete", resource="letterhead_asset")
    async def soft_delete_letterhead(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id)
                )
                session.commit()
            self.confirm_open = False
            self.confirm_id = ""
            await self.load_letterheads()
            self.flash = "Letterhead deactivated."
            self.flash_type = "success"
        except DocumentTemplateError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_id = ""

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""


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
            for r in _svc(session).list_templates():
                self.templates.append({
                    "id": str(r.id),
                    "template_type": r.purpose.upper(),
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
        except DocumentTemplateError as e:
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
        except DocumentTemplateError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_id = ""

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
