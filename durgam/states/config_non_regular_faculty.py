"""NonRegularFacultyConfigState — department-scoped non-regular faculty CRUD + approval."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.department import DepartmentRepository
from durgam.repositories.non_regular_faculty import NonRegularFacultyRepository
from durgam.repositories.user import UserRepository
from durgam.services.non_regular_faculty import NonRegularFacultyError, NonRegularFacultyService
from durgam.states.base import BaseState

_TYPE_OPTIONS = ["visiting", "adjunct", "guest", "contract", "honorary"]


def _svc(session) -> NonRegularFacultyService:
    return NonRegularFacultyService(
        repo=NonRegularFacultyRepository(session),
    )


class NonRegularFacultyConfigState(BaseState):
    dept_options: list[dict[str, str]] = []
    selected_dept_id: str = ""
    dept_locked: bool = False
    dept_name_display: str = ""

    visitors: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_name: str = ""
    form_designation: str = ""
    form_organization: str = ""
    form_expertise: str = ""
    form_available_from: str = ""
    form_available_to: str = ""
    form_type: str = "visiting"

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    can_approve: bool = False

    async def load_visitors(self) -> None:
        guard = self._config_guard("non_regular_faculty", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.visitors = []
        self.show_form = False
        self.dept_options = []

        with open_session() as session:
            dept_repo = DepartmentRepository(session)
            all_depts = dept_repo.list_active()
            user_dept_id = self._resolve_user_dept_scope(session)
            if user_dept_id:
                self.dept_locked = True
                self.selected_dept_id = str(user_dept_id)
                matched = [d for d in all_depts if d.id == user_dept_id]
                self.dept_name_display = f"{matched[0].code} — {matched[0].name}" if matched else ""
                self.dept_options = [{"value": str(user_dept_id), "label": self.dept_name_display}]
            else:
                self.dept_locked = False
                for d in all_depts:
                    self.dept_options.append({
                        "value": str(d.id),
                        "label": f"{d.code} — {d.name}",
                    })
                if self.dept_options and not self.selected_dept_id:
                    self.selected_dept_id = self.dept_options[0]["value"]

            self._load_data(session)

        from durgam.auth.permissions import can

        with open_session() as session:
            self.can_approve = can(
                UUID(self.current_user_id),
                "approve", "non_regular_faculty", None, None, session,
            )

        self._load_nav_entries()
        self.loading = False

    def _load_data(self, session) -> None:
        self.visitors = []
        if not self.selected_dept_id:
            return
        svc = _svc(session)
        user_repo = UserRepository(session)
        for v in svc.list_by_department(UUID(self.selected_dept_id)):
            approved_info = ""
            if v.is_admin_approved and v.approved_at:
                approver_name = ""
                if v.approved_by_user_id:
                    approver = user_repo.get_by_id(v.approved_by_user_id)
                    if approver:
                        approver_name = approver.full_name or approver.username
                approved_info = (
                    f"Approved by {approver_name} on "
                    f"{v.approved_at.strftime('%b %-d, %Y')}"
                )
            self.visitors.append({
                "id": str(v.id),
                "name": v.name,
                "designation": v.designation,
                "organization": v.organization,
                "expertise": v.expertise,
                "available_from": str(v.available_from),
                "available_to": str(v.available_to),
                "approved": "yes" if v.is_admin_approved else "no",
                "approved_info": approved_info,
                "non_regular_type": v.non_regular_type,
            })

    async def on_dept_change(self, value: str) -> None:
        self.selected_dept_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)

    def set_form_name(self, v: str) -> None:
        self.form_name = v

    def set_form_designation(self, v: str) -> None:
        self.form_designation = v

    def set_form_organization(self, v: str) -> None:
        self.form_organization = v

    def set_form_expertise(self, v: str) -> None:
        self.form_expertise = v

    def set_form_available_from(self, v: str) -> None:
        self.form_available_from = v

    def set_form_available_to(self, v: str) -> None:
        self.form_available_to = v

    def set_form_type(self, v: str) -> None:
        self.form_type = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_name = ""
        self.form_designation = ""
        self.form_organization = ""
        self.form_expertise = ""
        self.form_available_from = ""
        self.form_available_to = ""
        self.form_type = "visiting"
        self.show_form = True

    def open_edit(
        self, vid: str, name: str, designation: str, organization: str,
        expertise: str, available_from: str, available_to: str,
        non_regular_type: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = vid
        self.form_name = name
        self.form_designation = designation
        self.form_organization = organization
        self.form_expertise = expertise
        self.form_available_from = available_from
        self.form_available_to = available_to
        self.form_type = non_regular_type
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="non_regular_faculty")
    @audit_action(action="write", resource="non_regular_faculty")
    async def save_visitor(self, form_data: dict) -> None:
        name = form_data.get("form_name", "").strip()
        designation = form_data.get("form_designation", "").strip()
        organization = form_data.get("form_organization", "").strip()
        expertise = form_data.get("form_expertise", "").strip()
        available_from_str = form_data.get("form_available_from", "").strip()
        available_to_str = form_data.get("form_available_to", "").strip()
        editing_id = form_data.get("editing_id", "").strip()

        if not available_from_str or not available_to_str:
            self.flash = "Both available-from and available-to dates are required."
            self.flash_type = "error"
            return

        try:
            available_from = date.fromisoformat(available_from_str)
            available_to = date.fromisoformat(available_to_str)
        except ValueError:
            self.flash = "Invalid date format. Use YYYY-MM-DD."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        department_id=UUID(self.selected_dept_id),
                        name=name,
                        designation=designation,
                        organization=organization,
                        expertise=expertise,
                        available_from=available_from,
                        available_to=available_to,
                        actor_id=actor_id,
                        non_regular_type=self.form_type,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {
                            "name": name,
                            "designation": designation,
                            "organization": organization,
                            "expertise": expertise,
                            "available_from": available_from,
                            "available_to": available_to,
                            "non_regular_type": self.form_type,
                        },
                        actor_id,
                    )
                session.commit()
        except NonRegularFacultyError as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_visitors()
        self.flash = "Non-regular faculty record saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, name: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate '{name}'?"
        self.confirm_body = "This will remove the non-regular faculty record."
        self.confirm_open = True

    @require_role(action="delete", resource="non_regular_faculty")
    @audit_action(action="delete", resource="non_regular_faculty")
    async def soft_delete_visitor(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
        except NonRegularFacultyError as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_visitors()
        self.flash = "Non-regular faculty record deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""

    @require_role(action="approve", resource="non_regular_faculty")
    @audit_action(action="approve", resource="non_regular_faculty")
    async def toggle_approval(self, record_id: str, current_status: str) -> None:
        new_approved = current_status != "yes"
        try:
            with open_session() as session:
                _svc(session).set_approval(
                    UUID(record_id), new_approved, UUID(self.current_user_id),
                )
                session.commit()
        except NonRegularFacultyError as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            return
        await self.load_visitors()
        status_label = "approved" if new_approved else "unapproved"
        self.flash = f"Non-regular faculty record {status_label}."
        self.flash_type = "success"
