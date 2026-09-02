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
    from app.db import models  # noqa: F401  (register models)

    legacy = _extract_legacy_glossary()
    Base.metadata.create_all(_engine)
    if legacy:
        _reinsert_glossary(legacy)


def _extract_legacy_glossary() -> list[dict] | None:
    """Pull rows from a pre-`forms` glossary table and drop it for rebuild.

    Older databases stored one column per language (`en`/`hi`/`mr`). Convert
    those rows into the new language-agnostic `forms` map so no data is lost when
    the table is recreated with the current schema.
    """
    from sqlalchemy import inspect, text

    from app.languages import SUPPORTED_CODES

    insp = inspect(_engine)
    if not insp.has_table("glossary"):
        return None
    cols = [c["name"] for c in insp.get_columns("glossary")]
    if "forms" in cols:
        return None  # already migrated

    lang_cols = [c for c in cols if c in set(SUPPORTED_CODES)]
    with _engine.begin() as conn:
        rows = conn.execute(text("SELECT * FROM glossary")).mappings().all()
        conn.execute(text("DROP TABLE glossary"))

    records: list[dict] = []
    for r in rows:
        forms = {c: r[c] for c in lang_cols if r.get(c)}
        records.append(
            {
                "id": r.get("id"),
                "created_at": r.get("created_at"),
                "category": r.get("category", "general"),
                "forms": forms,
                "note": r.get("note"),
            }
        )
    return records


def _reinsert_glossary(records: list[dict]) -> None:
    from datetime import datetime

    from app.db.models import GlossaryEntry

    def _as_dt(value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    with session_scope() as session:
        for rec in records:
            kwargs = {k: v for k, v in rec.items() if v is not None and k != "created_at"}
            created = _as_dt(rec.get("created_at"))
            if created is not None:
                kwargs["created_at"] = created
            session.add(GlossaryEntry(**kwargs))


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