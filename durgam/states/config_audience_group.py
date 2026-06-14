"""AudienceGroupConfigState — audience group CRUD with filter_json builder (M9 Phase 5b)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.announcement import AudienceGroupRepository
from durgam.services.audience_group import AudienceGroupError, AudienceGroupService
from durgam.states.base import BaseState


def _svc(session) -> AudienceGroupService:
    return AudienceGroupService(
        repo=AudienceGroupRepository(session),
        session=session,
    )


def _filter_summary(filter_json: dict[str, Any]) -> str:
    """Return a human-readable one-line summary of a filter_json dict."""
    parts: list[str] = []
    role_codes = filter_json.get("role_codes")
    if role_codes:
        parts.append(f"Roles: {', '.join(role_codes)}")
    scope_type = filter_json.get("scope_type")
    if scope_type:
        scope_codes = filter_json.get("scope_codes") or []
        label = scope_type.capitalize()
        if scope_codes:
            parts.append(f"{label}: {', '.join(scope_codes)}")
        else:
            parts.append(f"{label}: (any)")
    dts = filter_json.get("program_degree_types")
    if dts:
        parts.append(f"Degree types: {', '.join(dts)}")
    return " · ".join(parts) if parts else "Everyone"


class AudienceGroupConfigState(BaseState):
    rows: list[dict] = []
    loading: bool = True
    available_scope_codes_for_current_type: list[str] = []

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_name: str = ""
    form_description: str = ""
    form_is_active: bool = True
    # filter_json broken out into UI-friendly fields
    form_role_codes: list[str] = []
    form_scope_type: str = "none"
    form_scope_codes: list[str] = []
    form_program_degree_types_text: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_audience_groups(self) -> None:
        guard = self._config_guard("audience_group", "configure")
        if guard is not None:
            return guard
        self.loading = True
        self.rows = []
        self.show_form = False

        with open_session() as session:
            svc = _svc(session)
            self._load_role_options(session)
            for g in svc.list_all():
                self.rows.append({
                    "id": str(g.id),
                    "code": g.code,
                    "name": g.name,
                    "filter_summary": _filter_summary(g.filter_json),
                    "active": "Yes" if g.is_active else "No",
                    "description": g.description or "",
                    # raw for edit form
                    "raw_is_active": "1" if g.is_active else "0",
                    "raw_description": g.description or "",
                    "raw_filter_json": g.filter_json,
                })

        self._load_nav_entries()
        self.loading = False

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_form_code(self, v: str) -> None:
        self.form_code = v

    def set_form_name(self, v: str) -> None:
        self.form_name = v

    def set_form_description(self, v: str) -> None:
        self.form_description = v

    def set_form_is_active(self, v: bool) -> None:
        self.form_is_active = v

    def set_form_program_degree_types_text(self, v: str) -> None:
        self.form_program_degree_types_text = v

    def toggle_role_code(self, code: str) -> None:
        if code in self.form_role_codes:
            self.form_role_codes = [c for c in self.form_role_codes if c != code]
        else:
            self.form_role_codes = [*self.form_role_codes, code]

    def toggle_scope_code(self, code: str) -> None:
        if code in self.form_scope_codes:
            self.form_scope_codes = [c for c in self.form_scope_codes if c != code]
        else:
            self.form_scope_codes = [*self.form_scope_codes, code]

    async def set_scope_type(self, value: str) -> None:
        self.form_scope_type = value
        self.form_scope_codes = []
        if value == "none":
            self.available_scope_codes_for_current_type = []
            return
        with open_session() as session:
            svc = _svc(session)
            self.available_scope_codes_for_current_type = svc.list_scope_codes_for_type(value)

    # ── Form open/close ───────────────────────────────────────────────────────

    def open_create(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_description = ""
        self.form_is_active = True
        self.form_role_codes = []
        self.form_scope_type = "none"
        self.form_scope_codes = []
        self.form_program_degree_types_text = ""
        self.available_scope_codes_for_current_type = []
        self.show_form = True

    def open_edit(
        self,
        group_id: str,
        code: str,
        name: str,
        description: str,
        is_active: str,
        filter_json: dict[str, Any],
    ) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = group_id
        self.form_code = code
        self.form_name = name
        self.form_description = description
        self.form_is_active = is_active == "1"
        # Unpack filter_json back into form fields
        self.form_role_codes = list(filter_json.get("role_codes") or [])
        scope_type = filter_json.get("scope_type") or "none"
        self.form_scope_type = scope_type
        self.form_scope_codes = list(filter_json.get("scope_codes") or [])
        dts = filter_json.get("program_degree_types") or []
        self.form_program_degree_types_text = ", ".join(dts)
        # Load scope codes for the current scope_type so the picker shows options
        if scope_type != "none":
            with open_session() as session:
                svc = _svc(session)
                self.available_scope_codes_for_current_type = (
                    svc.list_scope_codes_for_type(scope_type)
                )
        else:
            self.available_scope_codes_for_current_type = []
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    # ── Save ──────────────────────────────────────────────────────────────────

    @require_role(action="configure", resource="audience_group")
    @audit_action(action="configure", resource="audience_group")
    async def save(self, form_data: dict) -> None:
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        editing_id = form_data.get("editing_id", "").strip()

        # Build filter_json from broken-out form fields
        filter_json: dict[str, Any] = {}
        if self.form_role_codes:
            filter_json["role_codes"] = list(self.form_role_codes)
        if self.form_scope_type != "none":
            filter_json["scope_type"] = self.form_scope_type
        if self.form_scope_codes:
            filter_json["scope_codes"] = list(self.form_scope_codes)
        raw_dts = self.form_program_degree_types_text.strip()
        if raw_dts:
            parts = [p.strip() for p in raw_dts.split(",") if p.strip()]
            if parts:
                filter_json["program_degree_types"] = parts

        description = self.form_description.strip() or None
        is_active = self.form_is_active
        actor_id = UUID(self.current_user_id)

        try:
            with open_session() as session:
                svc = _svc(session)
                if not editing_id:
                    entity = svc.create(
                        code=code,
                        name=name,
                        description=description,
                        filter_json=filter_json,
                        is_active=is_active,
                        actor_id=actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    repo = AudienceGroupRepository(session)
                    before_snap = audit_snapshot(repo.get(UUID(editing_id)))
                    entity = svc.update(
                        id_=UUID(editing_id),
                        name=name,
                        description=description,
                        filter_json=filter_json,
                        is_active=is_active,
                        actor_id=actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(
                        resource_id=str(entity.id),
                        before=before_snap,
                        after=after_snap,
                    )
        except AudienceGroupError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return

        self.show_form = False
        self.editing_id = ""
        await self.load_audience_groups()
        self.flash = "Audience group saved."
        self.flash_type = "success"

    # ── Deactivate ────────────────────────────────────────────────────────────

    def open_deactivate_confirm(self, group_id: str, code: str) -> None:
        self.confirm_id = group_id
        self.confirm_title = f"Remove '{code}'?"
        self.confirm_body = (
            f"This will remove the '{code}' audience group. "
            "Existing announcements targeting this group are not affected."
        )
        self.confirm_open = True

    @require_role(action="configure", resource="audience_group")
    @audit_action(action="configure", resource="audience_group")
    async def confirm_deactivate(self) -> None:
        try:
            with open_session() as session:
                repo = AudienceGroupRepository(session)
                entity = repo.get(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(
                    id_=UUID(self.confirm_id),
                    actor_id=UUID(self.current_user_id),
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
        except AudienceGroupError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return

        self.confirm_open = False
        self.confirm_id = ""
        await self.load_audience_groups()
        self.flash = "Audience group removed."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
