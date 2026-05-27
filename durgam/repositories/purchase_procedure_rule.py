"""PurchaseProcedureRuleRepository — tier policy for institutional purchases (E-007)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import PurchaseProcedureRule
from durgam.repositories.base import BaseRepository


class PurchaseProcedureRuleRepository(BaseRepository[PurchaseProcedureRule]):
    def __init__(self, session: Session) -> None:
        super().__init__(PurchaseProcedureRule, session)

    def list_by_fund_source(self, fund_source: str) -> list[PurchaseProcedureRule]:
        return list(
            self._session.exec(
                select(PurchaseProcedureRule)
                .where(
                    PurchaseProcedureRule.fund_source == fund_source,
                    PurchaseProcedureRule.is_deleted == False,  # noqa: E712
                )
                .order_by(PurchaseProcedureRule.tier)
            ).all()
        )

    def list_all_active(self) -> list[PurchaseProcedureRule]:
        return list(
            self._session.exec(
                select(PurchaseProcedureRule)
                .where(PurchaseProcedureRule.is_deleted == False)  # noqa: E712
                .order_by(PurchaseProcedureRule.fund_source, PurchaseProcedureRule.tier)
            ).all()
        )
