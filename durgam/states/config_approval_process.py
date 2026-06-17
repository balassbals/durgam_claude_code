"""ApprovalProcessConfigState — approval process template CRUD (SysAdmin only)."""

from __future__ import annotations

from uuid import UUID

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.services.approval_process import ApprovalProcessError, ApprovalProcessService
from durgam.states.base import BaseState


def _svc(session) -> ApprovalProcessService:
    return ApprovalProcessService(
        repo=ApprovalProcessRepository(session),
    )


class ApprovalProcessConfigState(BaseState):
    processes: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_title: str = ""
    form_requestors_selected: list[str] = []
    form_channel_selected: list[str] = []
    form_is_finance: bool = False
    form_cc_selected: list[str] = []
    form_requires_upward: bool = False
    form_max_upward: int = 0
    form_requires_downward: bool = False
    form_max_downward: int = 0
    form_max_attachment_mb: int = 5
    form_allowed_mimes: list[str] = []

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_processes(self) -> None:
        guard = self._config_guard("approval_process", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.processes = []
        self.show_form = False

        with open_session() as session:
            svc = _svc(session)
            self._load_role_options(session)
            for p in svc.list_all():
                self.processes.append({
                    "id": str(p.id),
                    "code": p.code,
                    "title": p.title,
                    "finance": "Yes" if p.is_finance else "No",
                    "requestors": ", ".join(p.requestor_role_codes or []),
                    "channel": ", ".join(p.channel_role_codes or []),
                    # raw for edit (JSON-encoded list for state)
                    "cc": ", ".join(p.informational_cc_role_codes or []),
                    "raw_requestors": ",".join(p.requestor_role_codes or []),
                    "raw_channel": ",".join(p.channel_role_codes or []),
                    "raw_cc": ",".join(p.informational_cc_role_codes or []),
                    "raw_finance": "1" if p.is_finance else "0",
                    "raw_requires_upward": "1" if p.requires_upward_attachments else "0",
                    "raw_max_upward": str(p.max_upward_attachments),
                    "raw_requires_downward": "1" if p.requires_downward_attachments else "0",
                    "raw_max_downward": str(p.max_downward_attachments),
                    "max_attachment_mb": str(p.max_attachment_mb),
                    "raw_max_attachment_mb": str(p.max_attachment_mb),
                    "allowed_mimes": ", ".join(p.allowed_attachment_mime_types_json or []) or "Any",
                    "raw_allowed_mimes": ",".join(p.allowed_attachment_mime_types_json or []),
                })

        self._load_nav_entries()
        self.loading = False

    def set_form_code(self, v: str) -> None:
        self.form_code = v

    def set_form_title(self, v: str) -> None:
        self.form_title = v

    def toggle_requestor(self, code: str) -> None:
        if code in self.form_requestors_selected:
            self.form_requestors_selected = [c for c in self.form_requestors_selected if c != code]
        else:
            self.form_requestors_selected = [*self.form_requestors_selected, code]

    def toggle_channel(self, code: str) -> None:
        if code in self.form_channel_selected:
            self.form_channel_selected = [c for c in self.form_channel_selected if c != code]
        else:
            self.form_channel_selected = [*self.form_channel_selected, code]

    def move_channel_up(self, code: str) -> None:
        lst = list(self.form_channel_selected)
        idx = lst.index(code) if code in lst else -1
        if idx > 0:
            lst[idx - 1], lst[idx] = lst[idx], lst[idx - 1]
            self.form_channel_selected = lst

    def move_channel_down(self, code: str) -> None:
        lst = list(self.form_channel_selected)
        idx = lst.index(code) if code in lst else -1
        if 0 <= idx < len(lst) - 1:
            lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
            self.form_channel_selected = lst

    def toggle_cc(self, code: str) -> None:
        if code in self.form_cc_selected:
            self.form_cc_selected = [c for c in self.form_cc_selected if c != code]
        else:
            self.form_cc_selected = [*self.form_cc_selected, code]

    def set_form_is_finance(self, v: bool) -> None:
        self.form_is_finance = v

    def set_form_requires_upward(self, v: bool) -> None:
        self.form_requires_upward = v

    def set_form_max_upward(self, v: str) -> None:
        try:
            self.form_max_upward = max(0, min(20, int(v)))
        except (ValueError, TypeError):
            self.form_max_upward = 0

    def set_form_requires_downward(self, v: bool) -> None:
        self.form_requires_downward = v

    def set_form_max_downward(self, v: str) -> None:
        try:
            self.form_max_downward = max(0, min(20, int(v)))
        except (ValueError, TypeError):
            self.form_max_downward = 0

    def set_form_max_attachment_mb(self, v: str) -> None:
        try:
            self.form_max_attachment_mb = max(1, min(100, int(v)))
        except (ValueError, TypeError):
            self.form_max_attachment_mb = 5

    def toggle_allowed_mime(self, mime: str) -> None:
        if mime in self.form_allowed_mimes:
            self.form_allowed_mimes = [m for m in self.form_allowed_mimes if m != mime]
        else:
            self.form_allowed_mimes = [*self.form_allowed_mimes, mime]

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_title = ""
        self.form_requestors_selected = []
        self.form_channel_selected = []
        self.form_cc_selected = []
        self.form_is_finance = False
        self.form_requires_upward = False
        self.form_max_upward = 0
        self.form_requires_downward = False
        self.form_max_downward = 0
        self.form_max_attachment_mb = 5
        self.form_allowed_mimes = []
        self.show_form = True

    def open_edit(
        self, pid: str, code: str, title: str, requestors: str,
        channel: str, finance: str, cc: str,
        requires_upward: str = "0", max_upward: str = "0",
        requires_downward: str = "0", max_downward: str = "0",
        max_attachment_mb: str = "5", allowed_mimes: str = "",
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = pid
        self.form_code = code
        self.form_title = title
        self.form_requestors_selected = [r for r in requestors.split(",") if r]
        self.form_channel_selected = [c for c in channel.split(",") if c]
        self.form_cc_selected = [c for c in cc.split(",") if c]
        self.form_is_finance = finance == "1"
        self.form_requires_upward = requires_upward == "1"
        try:
            self.form_max_upward = int(max_upward)
        except (ValueError, TypeError):
            self.form_max_upward = 0
        self.form_requires_downward = requires_downward == "1"
        try:
            self.form_max_downward = int(max_downward)
        except (ValueError, TypeError):
            self.form_max_downward = 0
        try:
            self.form_max_attachment_mb = max(1, int(max_attachment_mb))
        except (ValueError, TypeError):
            self.form_max_attachment_mb = 5
        self.form_allowed_mimes = [m for m in allowed_mimes.split(",") if m.strip()]
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"
        self.form_max_attachment_mb = 5
        self.form_allowed_mimes = []

    @require_role(action="write", resource="approval_process")
    @audit_action(action="write", resource="approval_process")
    async def save_process(self, form_data: dict) -> None:
        code = form_data.get("form_code", "").strip()
        title = form_data.get("form_title", "").strip()
        editing_id = form_data.get("editing_id", "").strip()

        requestors = self.form_requestors_selected or None
        channel = self.form_channel_selected or None
        cc = self.form_cc_selected or None

        if self.form_requires_upward and self.form_max_upward < 1:
            self.flash = "Maximum requestor attachments must be at least 1 when required."
            self.flash_type = "error"
            return
        if self.form_requires_downward and self.form_max_downward < 1:
            self.flash = "Maximum approver attachments must be at least 1 when required."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                allowed_mimes = self.form_allowed_mimes or None
                if not editing_id:
                    entity = svc.create(
                        code=code,
                        title=title,
                        requestor_role_codes=requestors,
                        channel_role_codes=channel,
                        is_finance=self.form_is_finance,
                        informational_cc_role_codes=cc,
                        requires_upward_attachments=self.form_requires_upward,
                        max_upward_attachments=self.form_max_upward,
                        requires_downward_attachments=self.form_requires_downward,
                        max_downward_attachments=self.form_max_downward,
                        max_attachment_mb=self.form_max_attachment_mb,
                        allowed_attachment_mime_types_json=allowed_mimes,
                        actor_id=actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    before_snap = audit_snapshot(
                        ApprovalProcessRepository(session).get_by_id(UUID(editing_id))
                    )
                    entity = svc.update(
                        UUID(editing_id),
                        {
                            "code": code,
                            "title": title,
                            "requestor_role_codes": requestors,
                            "channel_role_codes": channel,
                            "is_finance": self.form_is_finance,
                            "informational_cc_role_codes": cc,
                            "requires_upward_attachments": self.form_requires_upward,
                            "max_upward_attachments": self.form_max_upward,
                            "requires_downward_attachments": self.form_requires_downward,
                            "max_downward_attachments": self.form_max_downward,
                            "max_attachment_mb": self.form_max_attachment_mb,
                            "allowed_attachment_mime_types_json": allowed_mimes,
                        },
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
        except ApprovalProcessError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_processes()
        self.flash = "Approval process saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, code: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate '{code}'?"
        self.confirm_body = "This will remove the approval process template."
        self.confirm_open = True

    @require_role(action="delete", resource="approval_process")
    @audit_action(action="delete", resource="approval_process")
    async def soft_delete_process(self) -> None:
        try:
            with open_session() as session:
                entity = ApprovalProcessRepository(session).get_by_id(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
        except ApprovalProcessError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_processes()
        self.flash = "Approval process deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
