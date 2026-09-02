"""
Language registry.

A single source of truth that maps BhashaSetu's supported languages to the code
conventions used by each model family, plus the writing ``script`` used for
config-driven language auto-detection.

Adding a new language is (almost) a one-line change: add an entry to
``LANGUAGES``. Everything downstream - UI dropdowns, translation, TTS, subtitles
and text auto-detection - derives from this table. For a language that shares a
script with an existing one (e.g. two Devanagari languages) provide ``markers``
to help disambiguate them during auto-detection.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str                   # internal short code (ISO-639-1-ish)
    name_en: str                # English display name
    name_native: str            # native display name
    whisper: str                # faster-whisper language code
    flores: str                 # FLORES-200 tag (IndicTrans2 + NLLB)
    mms: str                    # MMS-TTS model suffix (facebook/mms-tts-<mms>)
    script: str                 # ISO-15924 script code (Latn, Deva, Beng, ...)
    markers: tuple[str, ...] = () # substrings that disambiguate same-script langs


LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", "English", "en", "eng_Latn", "eng", "Latn"),
    "hi": Language("hi", "Hindi", "हिन्दी", "hi", "hin_Deva", "hin", "Deva"),
    "mr": Language(
        "mr", "Marathi", "मराठी", "mr", "mar_Deva", "mar", "Deva",
        # Markers that strongly indicate Marathi over Hindi (same Devanagari script).
        markers=("ळ", "आहे", "नाही", "मला", "तुम्ही", "आम्ही", "होते", "करा"),
    ),
}

SUPPORTED_CODES: list[str] = list(LANGUAGES.keys())


# --- Unicode script detection -----------------------------------------
# Regex per ISO-15924 script code. Extend this map when adding a language whose
# script is not yet listed so that text auto-detection can recognise it.
_SCRIPT_PATTERNS: dict[str, re.Pattern] = {
    "Latn": re.compile(r"[A-Za-z]"),
    "Deva": re.compile(r"[\u0900-\u097F]"),   # Hindi, Marathi, Nepali, ...
    "Beng": re.compile(r"[\u0980-\u09FF]"),   # Bengali, Assamese
    "Guru": re.compile(r"[\u0A00-\u0A7F]"),   # Punjabi (Gurmukhi)
    "Gujr": re.compile(r"[\u0A80-\u0AFF]"),   # Gujarati
    "Orya": re.compile(r"[\u0B00-\u0B7F]"),   # Odia
    "Taml": re.compile(r"[\u0B80-\u0BFF]"),   # Tamil
    "Telu": re.compile(r"[\u0C00-\u0C7F]"),   # Telugu
    "Knda": re.compile(r"[\u0C80-\u0CFF]"),   # Kannada
    "Mlym": re.compile(r"[\u0D00-\u0D7F]"),   # Malayalam
}


def get_language(code: str) -> Language:
    code = (code or "").lower().strip()
    if code not in LANGUAGES:
        raise ValueError(
            f"Unsupported language '{code}'. Supported: {', '.join(SUPPORTED_CODES)}"
        )
    return LANGUAGES[code]


def is_supported(code: str) -> bool:
    return (code or "").lower().strip() in LANGUAGES


def language_options() -> list[dict[str, str]]:
    """UI-friendly list for dropdowns."""
    return [
        {
            "code": lang.code,
            "name": lang.name_en,
            "native": lang.name_native,
        }
        for lang in LANGUAGES.values()
    ]


# --- Auto-detection helpers -------------------------------------------
def default_code() -> str:
    """Fallback language when text has no recognisable script (prefers Latin)."""
    for lang in LANGUAGES.values():
        if lang.script == "Latn":
            return lang.code
    return next(iter(LANGUAGES))


def shares_script(code: str) -> bool:
    """True when ``code``'s script is used by more than one supported language.

    Used to decide whether an auto-detected code needs marker-based
    disambiguation (e.g. Hindi vs Marathi, both Devanagari).
    """
    lang = LANGUAGES.get((code or "").lower().strip())
    if lang is None:
        return False
    return sum(1 for l in LANGUAGES.values() if l.script == lang.script) > 1


def _script_counts(text: str) -> dict[str, int]:
    scripts_in_use = {lang.script for lang in LANGUAGES.values()}
    counts: dict[str, int] = {}
    for script in scripts_in_use:
        pattern = _SCRIPT_PATTERNS.get(script)
        if pattern is not None:
            counts[script] = len(pattern.findall(text))
    return counts


def detect_language(text: str) -> str:
    """Registry-driven language detection for text with no metadata.

    Strategy: pick the script with the most characters present, then - if several
    supported languages share that script - prefer the one whose ``markers`` occur
    in the text, falling back to registry order. Returns ``default_code()`` when no
    supported script is present.
    """
    if not text or not text.strip():
        return default_code()

    counts = _script_counts(text)
    if not counts or max(counts.values()) == 0:
        return default_code()

    best_script = max(counts, key=lambda s: counts[s])
    candidates = [lang for lang in LANGUAGES.values() if lang.script == best_script]
    if not candidates:
        return default_code()
    if len(candidates) == 1:
        return candidates[0].code

    for lang in candidates:
        if lang.markers and any(marker in text for marker in lang.markers):
            return lang.code
    return candidates[0].code


def script_counts_by_code() -> Counter:
    """Debug helper: how many supported languages use each script."""
    return Counter(lang.script for lang in LANGUAGES.values())