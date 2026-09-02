"""
Automatic Speech Recognition (ASR) via faster-whisper.

faster-whisper is a CTranslate2 re-implementation of OpenAI Whisper that runs
efficiently on CPU with int8 quantisation - ideal for BAIF's hardware. It is
MIT-licensed and fully offline once the model is cached.

When models are disabled (demo mode) or unavailable, a deterministic mock
transcription is returned so the full pipeline and UI can still be exercised.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app.config import settings
from app.languages import get_language

logger = logging.getLogger(__name__)

def _nvidia_gpu_present() -> bool:
    """True if an NVIDIA GPU + driver is detectable (independent of torch build)."""
    import shutil
    import subprocess

    if shutil.which("nvidia-smi") is None:
        return False
    try:
        return subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except Exception:
        return False


def _register_cuda_dll_dirs() -> None:
    """Make CUDA runtime DLLs (cublas64_12.dll, cudnn*.dll) discoverable on Windows.

    faster-whisper's CTranslate2 backend loads these at runtime from the DLL search
    path. The CUDA torch build and the nvidia-* pip wheels ship them inside
    site-packages, but they are not on PATH by default -> 'cublas64_12.dll not found'.
    os.add_dll_directory (Windows/Python 3.8+) adds them without touching system PATH.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    candidate_dirs: list[str] = []
    try:
        import torch
        candidate_dirs.append(os.path.join(os.path.dirname(torch.__file__), "lib"))
    except Exception:
        pass
    try:
        import nvidia  # provided by nvidia-cublas-cu12 / nvidia-cudnn-cu12
        for pkg in ("cublas", "cudnn"):
            candidate_dirs.append(os.path.join(os.path.dirname(nvidia.__file__), pkg, "bin"))
    except Exception:
        pass
    for d in candidate_dirs:
        if d and os.path.isdir(d):
            try:
                os.add_dll_directory(d)
                logger.debug("Registered CUDA DLL directory: %s", d)
            except Exception: # pragma: no cover - defensive
                logger.debug("Could not register CUDA DLL directory: %s", d)

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration: float
    segments: list[TranscriptSegment] = field(default_factory=list)
    mock: bool = False

class _WhisperEngine:
    """Lazy singleton wrapping the faster-whisper model."""

    def __init__(self) -> None:
        self._model = None
        self._load_failed = False

    @property
    def ready(self) -> bool:
        if not settings.enable_models:
            return False
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:  # pragma: no cover - import guard
            return False

    def _resolve_device(self) -> tuple[str, str]:
        device = settings.device
        compute = settings.compute_type
        if device == "auto":
            device = "cpu"
            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
            except Exception:
                pass
            if device == "cpu" and _nvidia_gpu_present():
                logger.warning(
                    "NVIDIA GPU detected but not used. Ensure the CUDA torch build "
                    "and nvidia-cublas-cu12 / nvidia-cudnn-cu12 are installed."
                )
        if device == "cpu" and compute in ("float16", "int8_float16"):
            compute = "int8"
        return device, compute

    def _build_model(self, device: str, compute: str):
        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper '%s' on %s (%s)...",
            settings.whisper_model, device, compute,
        )

        kwargs = {
            "device": device,
            "compute_type": compute,
            "download_root": str(settings.models_path),
            "num_workers": max(1, int(settings.asr_num_workers)),
        }
        if device == "cpu" and int (settings.asr_cpu_threads) > 0:
            kwargs["cpu_threads"] = int(settings.asr_cpu_threads)

        return WhisperModel(settings.whisper_model, **kwargs)

    def _load(self):
        if self._model is not None:
            return self._model

        device, compute = self._resolve_device()
        if device == "cuda":
            _register_cuda_dll_dirs()
            try:
                self._model = self._build_model(device, compute)
                return self._model
            except Exception as exc:  # CUDA/DLL failure -> degrade to CPU
                logger.warning(
                    "GPU (cuda) load failed (%s). Falling back to CPU. "
                    "If you expected GPU, ensure the CUDA torch build and "
                    "nvidia-cublas-cu12 / nvidia-cudnn-cu12 are installed.",
                    exc,
                )
                device = "cpu"
                if compute in {"float16", "int8_float16"}:
                    compute = "int8"

        self._model = self._build_model(device, compute)
        return self._model    

    def transcribe(self, wav_path: str, source_lang: str = "auto") -> TranscriptionResult:
        model = self._load()
        language = None if source_lang in ("auto", "", None) else get_language(source_lang).whisper
        seg_iter, info = model.transcribe(
            wav_path,
            language=language,
            vad_filter=settings.asr_vad_filter,
            beam_size=max(1, int(settings.asr_beam_size)),
            word_timestamps=False,
        )
        segments = [
            TranscriptSegment(start=round(s.start, 3), end=round(s.end, 3), text=s.text.strip())
            for s in seg_iter
        ]
        text = " ".join(s.text for s in segments).strip()
        return TranscriptionResult(
            text=text,
            language=info.language,
            duration=float(info.duration),
            segments=segments,
        )

_engine = _WhisperEngine()


def asr_ready() -> bool:
    return _engine.ready


def preload_model() -> bool:
    """Warm ASR model at startup to remove first-request load latency."""
    if not _engine.ready:
        return False
    try:
        _engine._load()
        return True
    except Exception: # pragma: no cover - best-effort warmup
        logger.exception("ASR preload failed")
        return False


def _generic_mock_lines(lang_code: str) -> list[str]:
    """Placeholder transcript for a language with no curated demo sample."""
    from app import languages

    try:
        name = languages.get_language(lang_code).name_en
    except ValueError:
        name = lang_code or "the source language"
    return [
        f"This is a demo transcript in {name}.",
        "Enable real models to transcribe actual audio.",
        "BhashaSetu will translate this into your chosen language.",
        "Thank you for trying the demo mode.",
    ]


def _mock_transcription(duration: float | None, source_lang: str) -> TranscriptionResult:
    """Deterministic placeholder transcript for demo mode."""
    from app import languages

    lang = languages.default_code() if source_lang in ("auto", "", None) else source_lang
    duration = duration or 30.0
    samples = {
        "en": [
            "Welcome to this BAIF agricultural training session.",
            "Today we will learn about crossbred cattle management.",
            "Provide clean water and balanced feed every day.",
            "Regular vaccination keeps your livestock healthy.",
        ],
        "hi": [
            "बाएफ के इस कृषि प्रशिक्षण सत्र में आपका स्वागत है।",
            "आज हम संकर पशुओं के प्रबंधन के बारे में जानेंगे।",
            "हर दिन स्वच्छ पानी और संतुलित आहार दें।",
            "नियमित टीकाकरण आपके पशुधन को स्वस्थ रखता है।",
        ],
        "mr": [
            "बायफच्या या कृषी प्रशिक्षण सत्रात आपले स्वागत आहे.",
            "आज आपण संकरित जनावरांच्या व्यवस्थापनाबद्दल शिकू.",
            "दररोज स्वच्छ पाणी आणि संतुलित आहार द्या.",
            "नियमित लसीकरण तुमच्या पशुधनाला निरोगी ठेवते.",
        ],
    }
    lines = samples.get(lang) or _generic_mock_lines(lang)
    n = len(lines)
    step = duration / n
    segments = [
        TranscriptSegment(start=round(i * step, 2), end=round((i + 1) * step, 2), text=line)
        for i, line in enumerate(lines)
    ]
    return TranscriptionResult(
        text=" ".join(lines),
        language=lang,
        duration=duration,
        segments=segments,
        mock=True,
    )


def transcribe(wav_path: str, source_lang: str = "auto", duration: float | None = None) -> TranscriptionResult:
    """Transcribe audio to timed text. Falls back to a mock in demo mode."""
    if not _engine.ready:
        logger.info("ASR running in MOCK mode (models disabled/unavailable).")
        return _mock_transcription(duration, source_lang)
    return _engine.transcribe(wav_path, source_lang)