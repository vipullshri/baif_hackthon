from pydantic import BaseModel, ConfigDict, Field


class TextTranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str
    generate_tts: bool = True
    title: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    stage: str | None
    progress: int
    input_type: str
    title: str | None
    source_lang: str
    target_lang: str

    detected_lang: str | None
    duration_sec: float | None
    mock: bool
    reused: bool
    error: str | None

    translated_text: str | None
    source_text: str | None
    segments: list | None

    has_srt: bool = False
    has_vtt: bool = False
    has_audio: bool = False
    has_video: bool = False


class JobList(BaseModel):
    items: list[JobOut]
    total: int


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


class GlossaryEntryIn(BaseModel):
    category: str = "general"
    en: str
    hi: str
    mr: str
    note: str | None = None


class GlossaryEntryOut(GlossaryEntryIn):
    model_config = ConfigDict(from_attributes=True)
    id: str