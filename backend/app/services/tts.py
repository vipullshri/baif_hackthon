"""
Text-to-Speech (TTS).

Primary backend: **MMS-TTS** (Meta's Massively Multilingual Speech) - tiny VITS
models per language (eng/hin/mar) that synthesise quickly on CPU.

Optional backend: **Indic Parler-TTS** (Apache-2.0) for higher-quality, more
expressive voices (heavier; recommended only with a GPU).

Demo mode emits a short, valid WAV tone using only the Python standard library,
so the audio player works without any model or numpy/torch installed.
"""
from __future__ import annotations

import logging
import math
import struct
import wave
from pathlib import Path

from app.config import settings
from app.languages import get_language
from app.services.translate import split_sentences

logger = logging.getLogger(__name__)

_MMS_SAMPLE_RATE = 16000


class _MMStts:
    """Lazy per-language MMS-TTS (VITS) voices."""

    def __init__(self) -> None:
        self._voices: dict[str, tuple] = {}

    @property
    def ready(self) -> bool:
        if not settings.enable_models or settings.tts_backend != "mms":
            return False
        try:
            import transformers  # noqa: F401
            return True
        except Exception:
            return False

    def _voice(self, lang_code: str):
        if lang_code not in self._voices:
            import torch
            from transformers import AutoTokenizer, VitsModel

            name = f"facebook/mms-tts-{get_language(lang_code).mms}"
            logger.info("Loading MMS-TTS voice '%s'...", name)
            model = VitsModel.from_pretrained(name)
            tok = AutoTokenizer.from_pretrained(name)
            model.eval()
            self._voices[lang_code] = (model, tok, torch)
        return self._voices[lang_code]

    def synthesize(self, text: str, lang_code: str, out_wav: Path) -> Path:
        import numpy as np
        import soundfile as sf

        model, tok, torch = self._voice(lang_code)
        chunks: list = []
        for sentence in split_sentences(text) or [text]:
            inputs = tok(sentence, return_tensors="pt")
            with torch.no_grad():
                wav = model(**inputs).waveform[0].cpu().numpy()
            chunks.append(wav)
            chunks.append(np.zeros(int(0.15 * model.config.sampling_rate), dtype=wav.dtype))
        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_wav), audio, model.config.sampling_rate)
        return out_wav


_mms = _MMStts()


def tts_ready() -> bool:
    return _mms.ready


def _mock_synthesize(text: str, lang_code: str, out_wav: Path) -> Path:
    """Generate a gentle, valid WAV tone proportional to the text length."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    words = max(1, len((text or "").split()))
    duration = min(20.0, max(1.2, words * 0.35))  # ~0.35s per word, capped
    framerate = _MMS_SAMPLE_RATE
    n_frames = int(duration * framerate)
    base_freq = {"en": 220.0, "hi": 247.0, "mr": 262.0}.get(lang_code, 220.0)

    with wave.open(str(out_wav), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(framerate)
        frames = bytearray()
        for i in range(n_frames):
            t = i / framerate
            # soft amplitude envelope + slow vibrato to sound less harsh
            env = 0.25 * (0.5 - 0.5 * math.cos(min(t, 0.1) / 0.1 * math.pi)) if t < 0.1 else 0.25
            vibrato = base_freq + 4.0 * math.sin(2 * math.pi * 5 * t)
            sample = env * math.sin(2 * math.pi * vibrato * t)
            frames += struct.pack("<h", int(sample * 32767))
        wav.writeframes(bytes(frames))
    return out_wav


def synthesize(text: str, lang_code: str, out_wav: str | Path) -> Path:
    """Synthesise speech for ``text`` into ``out_wav``. Mocks in demo mode."""
    out_wav = Path(out_wav)
    text = (text or "").strip()
    if not text:
        text = "."
    if not _mms.ready:
        logger.info("TTS running in MOCK mode (models disabled/unavailable).")
        return _mock_synthesize(text, lang_code, out_wav)
    return _mms.synthesize(text, lang_code, out_wav)