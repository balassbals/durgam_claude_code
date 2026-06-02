"""Repository for DocumentTemplate — unified letterheads + type-based templates (E-005)."""

from sqlmodel import select

from durgam.models.config_anchors import DocumentTemplate
from durgam.repositories.base import BaseRepository


class DocumentTemplateRepository(BaseRepository[DocumentTemplate]):
    def __init__(self, session):
        super().__init__(DocumentTemplate, session)

    def list_active_by_purpose(self, purpose: str) -> list[DocumentTemplate]:
        stmt = (
            select(DocumentTemplate)
            .where(
                DocumentTemplate.is_deleted == False,  # noqa: E712
                DocumentTemplate.purpose == purpose,
            )
            .order_by(DocumentTemplate.role_code)
        )
        return list(self._session.exec(stmt).all())

    def list_letterheads(self) -> list[DocumentTemplate]:
        return self.list_active_by_purpose("letterhead")

    def list_templates(self) -> list[DocumentTemplate]:
        stmt = (
            select(DocumentTemplate)
            .where(
                DocumentTemplate.is_deleted == False,  # noqa: E712
                DocumentTemplate.purpose != "letterhead",
            )
            .order_by(DocumentTemplate.purpose)
        )
        return list(self._session.exec(stmt).all())

    def get_letterhead_by_role(self, role_code: str) -> DocumentTemplate | None:
        stmt = select(DocumentTemplate).where(
            DocumentTemplate.purpose == "letterhead",
            DocumentTemplate.role_code == role_code,
            DocumentTemplate.is_deleted == False,  # noqa: E712
        )
        return self._session.exec(stmt).first()

    def get_template_by_type(self, template_type: str) -> DocumentTemplate | None:
        stmt = select(DocumentTemplate).where(
            DocumentTemplate.purpose == template_type,
            DocumentTemplate.role_code.is_(None),  # type: ignore[union-attr]
            DocumentTemplate.is_deleted == False,  # noqa: E712
        )
        return self._session.exec(stmt).first()
