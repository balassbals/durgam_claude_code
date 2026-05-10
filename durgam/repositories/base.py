"""BaseRepository — soft-delete filter and CRUD helpers for all repos."""

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.base import TimestampedSoftDelete

type Row = TimestampedSoftDelete


class BaseRepository[T: TimestampedSoftDelete]:
    def __init__(self, model: type[T], session: Session) -> None:
        self._model = model
        self._session = session

    def get_by_id(self, record_id: UUID) -> T | None:
        """Return an active (not soft-deleted) row by primary key."""
        row = self._session.get(self._model, record_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_active(self) -> list[T]:
        """Return all rows where is_deleted=False."""
        statement = select(self._model).where(
            self._model.is_deleted == False  # noqa: E712
        )
        return list(self._session.exec(statement).all())

    def save(self, record: T) -> T:
        """Persist a new or updated record; updates updated_at timestamp."""
        record.updated_at = datetime.now(UTC)
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def soft_delete(self, record: T, actor_id: UUID) -> T:
        """Mark a record as deleted; does NOT hard-delete it."""
        record.is_deleted = True
        record.deleted_at = datetime.now(UTC)
        record.deleted_by = actor_id
        return self.save(record)
