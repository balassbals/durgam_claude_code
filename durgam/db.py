"""Database session factory — importable by States without violating the
'States must not import SQLModel/SQLAlchemy' layering rule.

States import open_session() from this module; they never import Session or
create_engine directly.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlmodel import Session

if TYPE_CHECKING:
    from collections.abc import Generator

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from durgam.config import settings

        _engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    return _engine


@contextmanager
def open_session() -> Generator[Session]:
    """Yield a SQLModel Session.

    Does NOT auto-commit. SQLAlchemy 2.x Session.__exit__ calls session.close()
    only — not session.commit(). Every handler that writes to the DB must call
    session.commit() inside the with block after all service/repo calls succeed.
    Read-only handlers do not need a commit.
    """
    with Session(_get_engine()) as session:
        yield session
