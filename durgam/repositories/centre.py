"""CentreRepository — queries for the CentreOfExcellence model (§8.2)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.centre import CentreOfExcellence
from durgam.repositories.base import BaseRepository


class CentreRepository(BaseRepository[CentreOfExcellence]):
    def __init__(self, session: Session) -> None:
        super().__init__(CentreOfExcellence, session)

    def get_by_code(self, code: str) -> CentreOfExcellence | None:
        return self._session.exec(
            select(CentreOfExcellence).where(
                CentreOfExcellence.code == code,
                CentreOfExcellence.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_by_campus(self, campus_id: UUID) -> list[CentreOfExcellence]:
        return list(
            self._session.exec(
                select(CentreOfExcellence).where(
                    CentreOfExcellence.campus_id == campus_id,
                    CentreOfExcellence.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def hard_delete(self, centre: CentreOfExcellence) -> None:
        self._session.delete(centre)
        self._session.flush()
