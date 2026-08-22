"""ORM models: translation jobs and the agricultural glossary."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    """A single translation request and all of its outputs."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    # -- Request -------------------------------------------------------------
    input_type: Mapped[str] = mapped_column(String(16))          # text | audio | video
    source_lang: Mapped[str] = mapped_column(String(8), default="auto")
    target_lang: Mapped[str] = mapped_column(String(8))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    generate_tts: Mapped[bool] = mapped_column(default=True)
    generate_subtitles: Mapped[bool] = mapped_column(default=True)
    burn_subtitles: Mapped[bool] = mapped_column(default=False)

    # -- Input ---------------------------------------------------------------
    input_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    input_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- Progress / status ---------------------------------------------------
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reused: Mapped[bool] = mapped_column(default=False)
    mock: Mapped[bool] = mapped_column(default=False)

    # -- Results -------------------------------------------------------------
    detected_lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)     # transcript
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[list | None] = mapped_column(JSON, nullable=True)       # timed segments

    # output artefact paths (relative to data dir)
    srt_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    vtt_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class GlossaryEntry(Base):
    """
    Domain terminology that must translate consistently.

    Stores the canonical form of a term per language in a single ``forms`` JSON
    map (``{lang_code: term}``) so the glossary is language-agnostic: adding a new
    language needs no schema change.
    """

    __tablename__ = "glossary"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    category: Mapped[str] = mapped_column(String(64), default="general", index=True)
    forms: Mapped[dict] = mapped_column(JSON, default=dict)  # {lang_code: term}
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def form(self, code: str) -> str:
        return (self.forms or {}).get(code, "")