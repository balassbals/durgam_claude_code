"""PurchaseCommitteeTemplateRepository — standing committee composition (E-007)."""

from sqlmodel import Session, select

from durgam.models.config_anchors import PurchaseCommitteeTemplate
from durgam.repositories.base import BaseRepository


class PurchaseCommitteeTemplateRepository(BaseRepository[PurchaseCommitteeTemplate]):
    def __init__(self, session: Session) -> None:
        super().__init__(PurchaseCommitteeTemplate, session)

    def get_by_type(self, committee_type: str) -> PurchaseCommitteeTemplate | None:
        return self._session.exec(
            select(PurchaseCommitteeTemplate).where(
                PurchaseCommitteeTemplate.committee_type == committee_type,
                PurchaseCommitteeTemplate.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_all_active(self) -> list[PurchaseCommitteeTemplate]:
        return list(
            self._session.exec(
                select(PurchaseCommitteeTemplate)
                .where(PurchaseCommitteeTemplate.is_deleted == False)  # noqa: E712
                .order_by(PurchaseCommitteeTemplate.committee_type)
            ).all()
        )
