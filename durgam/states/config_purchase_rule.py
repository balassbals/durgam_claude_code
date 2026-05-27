"""PurchaseRuleConfigState — purchase procedure rule CRUD (Finance Officer only)."""

from __future__ import annotations

from uuid import UUID

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.purchase_procedure_rule import PurchaseProcedureRuleRepository
from durgam.services.purchase_procedure_rule import (
    PurchaseProcedureRuleError,
    PurchaseProcedureRuleService,
)
from durgam.states.base import BaseState


def _svc(session) -> PurchaseProcedureRuleService:
    return PurchaseProcedureRuleService(
        repo=PurchaseProcedureRuleRepository(session),
    )


FUND_SOURCE_LABELS = {
    "institute": "Institute (Budgeted)",
    "projects_ugc": "Project / UGC Funds",
}


class PurchaseRuleConfigState(BaseState):
    rules: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_fund_source: str = "institute"
    form_tier: str = "1"
    form_floor: str = "0"
    form_ceiling: str = ""
    form_min_quotes: bool = True
    form_quote_count: str = "3"
    form_discretion: bool = False
    form_comparative: bool = False
    form_approvers_selected: list[str] = []
    form_committee: str = "__none__"
    form_notes: str = ""

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_rules(self) -> None:
        guard = self._config_guard("purchase_procedure_rule", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.rules = []
        self.show_form = False

        with open_session() as session:
            self._load_role_options(session)
            svc = _svc(session)
            for r in svc.list_all():
                self.rules.append({
                    "id": str(r.id),
                    "fund_source": FUND_SOURCE_LABELS.get(r.fund_source, r.fund_source),
                    "tier": str(r.tier),
                    "floor": str(r.floor_amount),
                    "ceiling": str(r.ceiling_amount) if r.ceiling_amount is not None else "No limit",
                    "quotes": "Discretion" if r.quote_at_discretion else ("Yes" if r.min_quotes_required else "No"),
                    "comparative": "Yes" if r.comparative_statement_required else "No",
                    "approvers": ", ".join(r.approving_authority_role_codes),
                    "committee": r.committee_level or "None",
                    "notes": r.notes or "",
                    # raw values for edit form
                    "raw_floor": str(r.floor_amount),
                    "raw_ceiling": str(r.ceiling_amount) if r.ceiling_amount is not None else "",
                    "raw_min_quotes": "1" if r.min_quotes_required else "0",
                    "raw_quote_count": str(r.min_quote_count),
                    "raw_discretion": "1" if r.quote_at_discretion else "0",
                    "raw_comparative": "1" if r.comparative_statement_required else "0",
                    "raw_approvers": ",".join(r.approving_authority_role_codes),
                    "raw_committee": r.committee_level or "",
                })

        self._load_nav_entries()
        self.loading = False

    def set_form_fund_source(self, v: str) -> None:
        self.form_fund_source = v

    def set_form_tier(self, v: str) -> None:
        self.form_tier = v

    def set_form_floor(self, v: str) -> None:
        self.form_floor = v

    def set_form_ceiling(self, v: str) -> None:
        self.form_ceiling = v

    def set_form_min_quotes(self, v: bool) -> None:
        self.form_min_quotes = v

    def set_form_quote_count(self, v: str) -> None:
        self.form_quote_count = v

    def set_form_discretion(self, v: bool) -> None:
        self.form_discretion = v

    def set_form_comparative(self, v: bool) -> None:
        self.form_comparative = v

    def toggle_approver(self, code: str) -> None:
        if code in self.form_approvers_selected:
            self.form_approvers_selected = [c for c in self.form_approvers_selected if c != code]
        else:
            self.form_approvers_selected = [*self.form_approvers_selected, code]

    def set_form_committee(self, v: str) -> None:
        self.form_committee = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_fund_source = "institute"
        self.form_tier = "1"
        self.form_floor = "0"
        self.form_ceiling = ""
        self.form_min_quotes = True
        self.form_quote_count = "3"
        self.form_discretion = False
        self.form_comparative = False
        self.form_approvers_selected = []
        self.form_committee = "__none__"
        self.form_notes = ""
        self.show_form = True

    def open_edit(
        self, rid: str, fund_source: str, tier: str, floor: str,
        ceiling: str, min_quotes: str, quote_count: str, discretion: str,
        comparative: str, approvers: str, committee: str, notes: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = rid
        self.form_fund_source = fund_source
        self.form_tier = tier
        self.form_floor = floor
        self.form_ceiling = ceiling
        self.form_min_quotes = min_quotes == "1"
        self.form_quote_count = quote_count
        self.form_discretion = discretion == "1"
        self.form_comparative = comparative == "1"
        self.form_approvers_selected = [a for a in approvers.split(",") if a]
        self.form_committee = committee if committee else "__none__"
        self.form_notes = notes
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="purchase_procedure_rule")
    @audit_action(action="write", resource="purchase_procedure_rule")
    async def save_rule(self, form_data: dict) -> None:
        fund_source = form_data.get("form_fund_source", "").strip()
        tier_str = form_data.get("form_tier", "1").strip()
        floor_str = form_data.get("form_floor", "0").strip()
        ceiling_str = form_data.get("form_ceiling", "").strip()
        quote_count_str = form_data.get("form_quote_count", "3").strip()
        approvers = self.form_approvers_selected
        committee_raw = form_data.get("form_committee", "").strip()
        committee = None if committee_raw in ("", "__none__") else committee_raw
        notes = form_data.get("form_notes", "").strip() or None
        editing_id = form_data.get("editing_id", "").strip()

        try:
            tier = int(tier_str)
            floor_amount = int(floor_str)
            ceiling_amount = int(ceiling_str) if ceiling_str else None
            quote_count = int(quote_count_str)
        except ValueError:
            self.flash = "Numeric fields must contain valid numbers."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        fund_source=fund_source,
                        tier=tier,
                        floor_amount=floor_amount,
                        ceiling_amount=ceiling_amount,
                        min_quotes_required=self.form_min_quotes,
                        min_quote_count=quote_count,
                        quote_at_discretion=self.form_discretion,
                        comparative_statement_required=self.form_comparative,
                        approving_authority_role_codes=approvers,
                        committee_level=committee,
                        actor_id=actor_id,
                        notes=notes,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {
                            "fund_source": fund_source,
                            "tier": tier,
                            "floor_amount": floor_amount,
                            "ceiling_amount": ceiling_amount,
                            "min_quotes_required": self.form_min_quotes,
                            "min_quote_count": quote_count,
                            "quote_at_discretion": self.form_discretion,
                            "comparative_statement_required": self.form_comparative,
                            "approving_authority_role_codes": approvers,
                            "committee_level": committee,
                            "notes": notes,
                        },
                        actor_id,
                    )
                session.commit()
        except PurchaseProcedureRuleError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_rules()
        self.flash = "Purchase procedure rule saved."
        self.flash_type = "success"

    def open_deactivate_confirm(self, record_id: str, tier: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate tier {tier}?"
        self.confirm_body = "This will remove the purchase procedure rule."
        self.confirm_open = True

    @require_role(action="delete", resource="purchase_procedure_rule")
    @audit_action(action="delete", resource="purchase_procedure_rule")
    async def soft_delete_rule(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
        except PurchaseProcedureRuleError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_rules()
        self.flash = "Purchase procedure rule deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
