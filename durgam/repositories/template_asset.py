"""Repository for TemplateAsset — document templates bound to types."""

from sqlmodel import select

from durgam.models.config_anchors import TemplateAsset
from durgam.repositories.base import BaseRepository


class TemplateAssetRepository(BaseRepository[TemplateAsset]):
    def __init__(self, session):
        super().__init__(TemplateAsset, session)

    def list_active_ordered(self) -> list[TemplateAsset]:
        stmt = (
            select(TemplateAsset)
            .where(TemplateAsset.is_deleted == False)  # noqa: E712
            .order_by(TemplateAsset.template_type)
        )
        return list(self._session.exec(stmt).all())

    def get_active_by_type(self, template_type: str) -> TemplateAsset | None:
        stmt = select(TemplateAsset).where(
            TemplateAsset.template_type == template_type,
            TemplateAsset.is_deleted == False,  # noqa: E712
        )
        return self._session.exec(stmt).first()
