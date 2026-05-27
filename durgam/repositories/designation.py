"""DesignationRepository — extensible faculty designation vocabulary."""

from sqlmodel import Session, select

from durgam.models.config_anchors import Designation
from durgam.repositories.base import BaseRepository


class DesignationRepository(BaseRepository[Designation]):
    def __init__(self, session: Session) -> None:
        super().__init__(Designation, session)

    def list_all_active(self) -> list[Designation]:
        return list(
            self._session.exec(
                select(Designation)
                .where(Designation.is_deleted == False)  # noqa: E712
                .order_by(Designation.rank)
            ).all()
        )

    def get_by_code(self, code: str) -> Designation | None:
        return self._session.exec(
            select(Designation).where(
                Designation.code == code,
                Designation.is_deleted == False,  # noqa: E712
            )
        ).first()
