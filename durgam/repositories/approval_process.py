"""ApprovalProcessRepository — approval process template config."""

from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalProcess
from durgam.repositories.base import BaseRepository


class ApprovalProcessRepository(BaseRepository[ApprovalProcess]):
    def __init__(self, session: Session) -> None:
        super().__init__(ApprovalProcess, session)

    def get_by_code(self, code: str) -> ApprovalProcess | None:
        return self._session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == code,
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_all_active(self) -> list[ApprovalProcess]:
        return list(
            self._session.exec(
                select(ApprovalProcess)
                .where(ApprovalProcess.is_deleted == False)  # noqa: E712
                .order_by(ApprovalProcess.code)
            ).all()
        )
