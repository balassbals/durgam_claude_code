"""DesignationConfigState — extensible faculty designation vocabulary CRUD."""

from __future__ import annotations

from uuid import UUID

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.designation import DesignationRepository
from durgam.services.designation import DesignationError, DesignationService
from durgam.states.base import BaseState


def _svc(session) -> DesignationService:
    return DesignationService(
        repo=DesignationRepository(session),
    )


class DesignationConfigState(BaseState):
    designations: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_name: str = ""
    form_rank: str = "1"
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_designations(self) -> None:
        guard = self._config_guard("designation", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.designations = []
        self.show_form = False

        with open_session() as session:
            svc = _svc(session)
            for d in svc.list_all():
                self.designations.append({
                    "id": str(d.id),
                    "code": d.code,
                    "name": d.name,
                    "rank": str(d.rank),
                    "notes": d.notes or "",
                })

        self._load_nav_entries()
        self.loading = False

    def set_form_code(self, v: str) -> None:
        self.form_code = v

    def set_form_name(self, v: str) -> None:
        self.form_name = v

    def set_form_rank(self, v: str) -> None:
        self.form_rank = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_rank = "1"
        self.form_notes = ""
        self.show_form = True

    def open_edit(self, did: str, code: str, name: str, rank: str, notes: str):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = did
        self.form_code = code
        self.form_name = name
        self.form_rank = rank
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="designation")
    @audit_action(action="write", resource="designation")
    async def save_designation(self, form_data: dict) -> None:
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        rank_str = form_data.get("form_rank", "1").strip()
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        try:
            rank = int(rank_str)
        except ValueError:
            self.flash = "Rank must be a number."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        code=code,
                        name=name,
                        rank=rank,
                        actor_id=actor_id,
                        notes=notes,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {"code": code, "name": name, "rank": rank, "notes": notes},
                        actor_id,
                    )
                session.commit()
        except DesignationError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_designations()
        self.flash = "Designation saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, code: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate designation '{code}'?"
        self.confirm_body = "This will remove the designation from the vocabulary."
        self.confirm_open = True

    @require_role(action="delete", resource="designation")
    @audit_action(action="delete", resource="designation")
    async def soft_delete_designation(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
        except DesignationError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_designations()
        self.flash = "Designation deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
