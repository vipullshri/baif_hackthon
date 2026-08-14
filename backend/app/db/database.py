"""
SQLite + SQLAlchemy engine and session management.

A single local SQLite file keeps BhashaSetu fully self-contained and offline.
For multi-node scale-out, swap the URL for PostgreSQL - the ORM code is unchanged.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


settings.ensure_dirs()

_engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},  # background worker threads
    future=True,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
    """Enable WAL + foreign keys for safe concurrent reads/writes."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables and seed reference data."""
    from app.db import models  # noqa: F401 (register models)

    Base.metadata.create_all(_engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context manager."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()