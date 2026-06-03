"""PurchaseCommitteeConfigState — committee template CRUD (Finance Officer only)."""

from __future__ import annotations

from uuid import UUID

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.purchase_committee_template import (
    PurchaseCommitteeTemplateRepository,
)
from durgam.services.purchase_committee_template import (
    PurchaseCommitteeTemplateError,
    PurchaseCommitteeTemplateService,
)
from durgam.states.base import BaseState


def _svc(session) -> PurchaseCommitteeTemplateService:
    return PurchaseCommitteeTemplateService(
        repo=PurchaseCommitteeTemplateRepository(session),
    )


class PurchaseCommitteeConfigState(BaseState):
    templates: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_committee_type: str = "campus_purchase_committee"
    form_eligible_designations_selected: list[str] = []
    form_faculty_count: str = "3"
    form_different_depts: bool = True
    form_fixed_members_selected: list[str] = []
    form_director_excluded: bool = False
    form_escalation: str = ""
    form_expert_mode: str = "proxied_with_proof"
    form_topology: str = "concurrent"
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_templates(self) -> None:
        guard = self._config_guard("purchase_committee_template", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.templates = []
        self.show_form = False

        with open_session() as session:
            self._load_role_options(session)
            self._load_designation_options(session)
            svc = _svc(session)
            for t in svc.list_all():
                self.templates.append({
                    "id": str(t.id),
                    "committee_type": t.committee_type,
                    "eligible_designations": ", ".join(t.eligible_designations),
                    "faculty_count": str(t.faculty_member_count),
                    "different_depts": "Yes" if t.members_from_different_departments else "No",
                    "fixed_members": ", ".join(t.fixed_role_members),
                    "director_excluded": "Yes" if t.director_excluded else "No",
                    "escalation": t.escalation_designate_role_code or "None",
                    "expert_mode": t.external_expert_mode,
                    "topology": t.topology,
                    "notes": t.notes or "",
                    # raw for edit (comma-separated for list parsing)
                    "raw_designations": ",".join(t.eligible_designations),
                    "raw_fixed": ",".join(t.fixed_role_members),
                    "raw_director_excluded": "1" if t.director_excluded else "0",
                    "raw_different_depts": "1" if t.members_from_different_departments else "0",
                    "raw_escalation": t.escalation_designate_role_code or "",
                })

        self._load_nav_entries()
        self.loading = False

    def set_form_committee_type(self, v: str) -> None:
        self.form_committee_type = v

    def toggle_designation(self, code: str) -> None:
        if code in self.form_eligible_designations_selected:
            self.form_eligible_designations_selected = [c for c in self.form_eligible_designations_selected if c != code]
        else:
            self.form_eligible_designations_selected = [*self.form_eligible_designations_selected, code]

    def set_form_faculty_count(self, v: str) -> None:
        self.form_faculty_count = v

    def set_form_different_depts(self, v: bool) -> None:
        self.form_different_depts = v

    def toggle_fixed_member(self, code: str) -> None:
        if code in self.form_fixed_members_selected:
            self.form_fixed_members_selected = [c for c in self.form_fixed_members_selected if c != code]
        else:
            self.form_fixed_members_selected = [*self.form_fixed_members_selected, code]

    def set_form_director_excluded(self, v: bool) -> None:
        self.form_director_excluded = v

    def set_form_escalation(self, v: str) -> None:
        self.form_escalation = v

    def set_form_expert_mode(self, v: str) -> None:
        self.form_expert_mode = v

    def set_form_topology(self, v: str) -> None:
        self.form_topology = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_committee_type = "campus_purchase_committee"
        self.form_eligible_designations_selected = []
        self.form_faculty_count = "3"
        self.form_different_depts = True
        self.form_fixed_members_selected = []
        self.form_director_excluded = False
        self.form_escalation = "__none__"
        self.form_expert_mode = "proxied_with_proof"
        self.form_topology = "concurrent"
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self, tid: str, committee_type: str, designations: str,
        faculty_count: str, different_depts: str, fixed: str,
        director_excluded: str, escalation: str, expert_mode: str,
        topology: str, notes: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = tid
        self.form_committee_type = committee_type
        self.form_eligible_designations_selected = [d for d in designations.split(",") if d]
        self.form_faculty_count = faculty_count
        self.form_different_depts = different_depts == "1"
        self.form_fixed_members_selected = [f for f in fixed.split(",") if f]
        self.form_director_excluded = director_excluded == "1"
        self.form_escalation = escalation if escalation else "__none__"
        self.form_expert_mode = expert_mode
        self.form_topology = topology
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="purchase_committee_template")
    @audit_action(action="write", resource="purchase_committee_template")
    async def save_template(self, form_data: dict) -> None:
        committee_type = form_data.get("form_committee_type", "").strip()
        count_str = form_data.get("form_faculty_count", "3").strip()
        escalation_raw = form_data.get("form_escalation", "").strip()
        escalation = None if escalation_raw in ("", "__none__") else escalation_raw
        expert_mode = form_data.get("form_expert_mode", "proxied_with_proof").strip()
        topology = form_data.get("form_topology", "concurrent").strip()
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        designations = self.form_eligible_designations_selected
        fixed_members = self.form_fixed_members_selected

        try:
            faculty_count = int(count_str)
        except ValueError:
            self.flash = "Faculty member count must be a number."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    entity = svc.create(
                        committee_type=committee_type,
                        eligible_designations=designations,
                        faculty_member_count=faculty_count,
                        members_from_different_departments=self.form_different_depts,
                        fixed_role_members=fixed_members,
                        director_excluded=self.form_director_excluded,
                        escalation_designate_role_code=escalation,
                        external_expert_mode=expert_mode,
                        topology=topology,
                        actor_id=actor_id,
                        notes=notes,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    before_snap = audit_snapshot(
                        PurchaseCommitteeTemplateRepository(session).get_by_id(UUID(editing_id))
                    )
                    entity = svc.update(
                        UUID(editing_id),
                        {
                            "committee_type": committee_type,
                            "eligible_designations": designations,
                            "faculty_member_count": faculty_count,
                            "members_from_different_departments": self.form_different_depts,
                            "fixed_role_members": fixed_members,
                            "director_excluded": self.form_director_excluded,
                            "escalation_designate_role_code": escalation,
                            "external_expert_mode": expert_mode,
                            "topology": topology,
                            "notes": notes,
                        },
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
        except PurchaseCommitteeTemplateError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_templates()
        self.flash = "Committee template saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, ctype: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate '{ctype}'?"
        self.confirm_body = "This will remove the committee template."
        self.confirm_open = True

    @require_role(action="delete", resource="purchase_committee_template")
    @audit_action(action="delete", resource="purchase_committee_template")
    async def soft_delete_template(self) -> None:
        try:
            with open_session() as session:
                entity = PurchaseCommitteeTemplateRepository(session).get_by_id(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
        except PurchaseCommitteeTemplateError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_templates()
        self.flash = "Committee template deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
