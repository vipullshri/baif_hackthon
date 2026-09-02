"""Pydantic schemas for API request/response payloads."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# --- Segments ----------------------------------------------------------------
class Segment(BaseModel):
    start: float
    end: float
    source: str
    translated: str | None = None

# --- Requests ----------------------------------------------------------------
class TextTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_lang: str = "auto"
    target_lang: str
    title: str | None = None
    generate_tts: bool = True

class JobOptions(BaseModel):
    source_lang: str = "auto"
    target_lang: str
    title: str | None = None
    generate_tts: bool = True
    generate_subtitles: bool = True
    burn_subtitles: bool = False

# --- Glossary ----------------------------------------------------------------
class GlossaryEntryIn(BaseModel):
    category: str = "general"
    forms: dict[str, str] = Field(default_factory=dict)  # {lang_code: term}
    note: str | None = None

class GlossaryEntryOut(GlossaryEntryIn):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}

# --- Job ---------------------------------------------------------------------
class JobOut(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime

    input_type: str
    source_lang: str
    target_lang: str
    title: str | None = None

    generate_tts: bool
    generate_subtitles: bool
    burn_subtitles: bool

    input_filename: str | None = None
    input_hash: str | None = None

    status: str
    stage: str | None = None
    progress: int
    error: str | None = None
    reused: bool
    mock: bool

    detected_lang: str | None = None
    duration_sec: float | None = None
    source_text: str | None = None
    translated_text: str | None = None
    segments: list[Segment] | None = None

    has_srt: bool = False
    has_vtt: bool = False
    has_audio: bool = False
    has_video: bool = False

    model_config = {"from_attributes": True}

class JobList(BaseModel):
    items: list[JobOut]
    total: int

# --- System ------------------------------------------------------------------
class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    models_enabled: bool
    offline: bool
    device: str
    whisper_model: str
    mt_backend: str
    tts_backend: str
    ready: dict[str, bool]

class LanguageOut(BaseModel):
    code: str
    name: str
    native: str