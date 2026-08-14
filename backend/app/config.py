import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_path: Path = Field(default=BACKEND_DIR / "data")
    enable_models: bool = True
    device: str = "auto"  # auto | cpu | cuda
    compute_type: str = "auto"  # auto | int8 | float16

    whisper_model: str = "base"
    mt_backend: str = "indictrans2"  # indictrans2 | nllb
    nllb_model: str = "facebook/nllb-200-distilled-600M"
    indictrans_en_indic: str = "ai4bharat/indictrans2-en-indic-dist-200M"
    indictrans_indic_en: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    indictrans_indic_indic: str = "ai4bharat/indictrans2-indic-indic-dist-320M"
    tts_backend: str = "mms"  # mms | indic_parler

    max_audio_mb: int = 50
    max_video_mb: int = 200

    @property
    def models_path(self) -> Path:
        return self.data_path / "models"

    @property
    def db_path(self) -> Path:
        return self.data_path / "bhashasetu.db"

    @property
    def uploads_path(self) -> Path:
        return self.data_path / "uploads"

    @property
    def outputs_path(self) -> Path:
        return self.data_path / "outputs"

    @property
    def tmp_path(self) -> Path:
        return self.data_path / "tmp"

    @property
    def offline(self) -> bool:
        return os.environ.get("HF_HUB_OFFLINE") == "1"

    def ensure_dirs(self) -> None:
        for path in [self.data_path, self.models_path, self.uploads_path, self.outputs_path, self.tmp_path]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()