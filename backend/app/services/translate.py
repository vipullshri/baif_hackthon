"""
Machine Translation (MT).

Primary backend: **AI4Bharat IndicTrans2** -- the state-of-the-art open model for
Indian languages (MIT licensed). It uses three directional checkpoints
(en->indic, indic->en, indic->indic) which this service selects automatically.

Fallback backend: **NLLB-200** (a single multilingual model) selectable via config.

Demo mode returns a deterministic, readable mock translation so the UI works
end-to-end without any model download.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from app.config import settings
from app.languages import get_language

logger = logging.getLogger(__name__)

# Split text into sentences on Latin + Devanagari terminators while keeping them.
_SENT_SPLIT = re.compile(r"(?<=[.!?।॥])\s+")


def split_sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts: list[str] = []
    for block in text.splitlines():
        block = block.strip()
        if not block:
            continue
        parts.extend(s.strip() for s in _SENT_SPLIT.split(block) if s.strip())
    return parts or [text]


# ----------------------------------------------------------------------
# Backend interface
# ----------------------------------------------------------------------
class TranslatorBackend(ABC):
    @abstractmethod
    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        ...

    @property
    @abstractmethod
    def ready(self) -> bool:
        ...


# ----------------------------------------------------------------------
# IndicTrans2
# ----------------------------------------------------------------------
class IndicTrans2Backend(TranslatorBackend):
    def __init__(self) -> None:
        self._models: dict[str, tuple] = {}
        self._processor = None

    @property
    def ready(self) -> bool:
        if not settings.enable_models:
            return False
        try:
            import IndicTransToolkit  # noqa: F401
            import transformers  # noqa: F401
            return True
        except Exception:
            return False

    def _model_name(self, src: str, tgt: str) -> str:
        if src == "en":
            return settings.indictrans_en_indic
        if tgt == "en":
            return settings.indictrans_indic_en
        return settings.indictrans_indic_indic

    def _get(self, model_name: str):
        if model_name not in self._models:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            logger.info("Loading IndicTrans2 model '%s'...", model_name)
            tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            mdl = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
            mdl.eval()
            if settings.device == "cuda":
                mdl = mdl.to("cuda")
            self._models[model_name] = (tok, mdl, torch)
        return self._models[model_name]

    def _ip(self):
        if self._processor is None:
            from IndicTransToolkit import IndicProcessor
            self._processor = IndicProcessor(inference=True)
        return self._processor

    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        if not sentences:
            return []
        src_flores = get_language(src).flores
        tgt_flores = get_language(tgt).flores
        tok, mdl, torch = self._get(self._model_name(src, tgt))
        ip = self._ip()

        batch = ip.preprocess_batch(sentences, src_lang=src_flores, tgt_lang=tgt_flores)
        inputs = tok(batch, truncation=True, padding="longest", return_tensors="pt", max_length=256)
        if settings.device == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with torch.no_grad():
            generated = mdl.generate(
                **inputs, max_length=256, num_beams=5, num_return_sequences=1
            )
        decoded = tok.batch_decode(generated, skip_special_tokens=True)
        return ip.postprocess_batch(decoded, lang=tgt_flores)


# ----------------------------------------------------------------------
# NLLB-200 (fallback / alternative)
# ----------------------------------------------------------------------
class NLLBBackend(TranslatorBackend):
    def __init__(self) -> None:
        self._tok = None
        self._mdl = None
        self._torch = None

    @property
    def ready(self) -> bool:
        if not settings.enable_models:
            return False
        try:
            import transformers  # noqa: F401
            return True
        except Exception:
            return False

    def _load(self):
        if self._mdl is None:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            logger.info("Loading NLLB model '%s'...", settings.nllb_model)
            self._tok = AutoTokenizer.from_pretrained(settings.nllb_model)
            self._mdl = AutoModelForSeq2SeqLM.from_pretrained(settings.nllb_model)
            self._torch = torch
        return self._tok, self._mdl, self._torch

    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        if not sentences:
            return []
        tok, mdl, torch = self._load()
        tok.src_lang = get_language(src).flores
        tgt_id = tok.convert_tokens_to_ids(get_language(tgt).flores)
        inputs = tok(sentences, return_tensors="pt", padding=True, truncation=True, max_length=256)
        with torch.no_grad():
            generated = mdl.generate(**inputs, forced_bos_token_id=tgt_id, max_length=256, num_beams=5)
        return tok.batch_decode(generated, skip_special_tokens=True)


# ----------------------------------------------------------------------
# Mock backend (demo mode)
# ----------------------------------------------------------------------
class MockBackend(TranslatorBackend):
    @property
    def ready(self) -> bool:
        return True

    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        tag = {"en": "[EN]", "hi": "[हिन्दी]", "mr": "[मराठी]"}.get(tgt, f"[{tgt}]")
        # Echo with a target tag so the demo clearly shows direction + flow.
        return [f"{tag} {s}" for s in sentences]


# ----------------------------------------------------------------------
# Public facade
# ----------------------------------------------------------------------
class Translator:
    def __init__(self) -> None:
        self._real: TranslatorBackend | None = None
        self._mock = MockBackend()

    def _backend(self) -> TranslatorBackend:
        if settings.enable_models:
            if self._real is None:
                self._real = (
                    NLLBBackend() if settings.mt_backend == "nllb" else IndicTrans2Backend()
                )
            if self._real.ready:
                return self._real
            logger.warning("MT backend not ready - using mock translation.")
        return self._mock

    @property
    def ready(self) -> bool:
        return self._backend() is not self._mock

    def translate_segments(self, texts: list[str], src: str, tgt: str) -> list[str]:
        if src == tgt:
            return list(texts)
        return self._backend().translate_batch(texts, src, tgt)

    def translate_text(self, text: str, src: str, tgt: str) -> str:
        if src == tgt:
            return text
        sentences = split_sentences(text)
        translated = self._backend().translate_batch(sentences, src, tgt)
        return " ".join(translated).strip()


_translator = Translator()


def translator_ready() -> bool:
    return _translator.ready


def translate_text(text: str, src: str, tgt: str) -> str:
    return _translator.translate_text(text, src, tgt)


def translate_segments(texts: list[str], src: str, tgt: str) -> list[str]:
    return _translator.translate_segments(texts, src, tgt)