"""
Agricultural glossary service.

This is BhashaSetu's signature feature: a curated, editable terminology base that
keeps BAIF-specific vocabulary (crop names, cattle breeds, scheme names) consistent
across every translation.

Mechanism (term protection):
1. Before translation, source-language glossary terms are replaced with stable
   placeholder tokens so the MT model cannot mistranslate them.
2. After translation, each placeholder is restored with the *canonical* target
   term from the glossary.

This guarantees terminology consistency regardless of translation direction. In
demo mode the placeholders round-trip perfectly; with real MT models it is a
best-effort post-edit (the industry-standard "soft constraint" technique).
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.database import session_scope
from app.db.models import GlossaryEntry

_SEED_FILE = BACKEND_DIR / "app" / "seed" / "glossary_seed.json"
_lock = threading.Lock()
_cache: list[dict] | None = None


def _extract_forms(item: dict) -> dict[str, str]:
    """Read per-language terms from a seed entry.

    Accepts either a nested `{"forms": {code: term}}` object or flat top-level
    language-code keys (e.g. `{"en": ..., "hi": ...}`). Only codes present in the
    language registry are kept, so the seed stays language-agnostic.
    """
    from app.languages import SUPPORTED_CODES

    raw = item.get("forms") if isinstance(item.get("forms"), dict) else item
    return {
        code: str(raw[code]).strip()
        for code in SUPPORTED_CODES
        if raw.get(code) and str(raw[code]).strip()
    }


# --- Seeding ------------------------------------------------------------------
def seed_glossary_if_empty() -> int:
    """Populate the glossary table from the seed file on first run."""
    with session_scope() as session:
        existing = session.scalar(select(GlossaryEntry).limit(1))
        if existing is not None:
            return 0
        if not _SEED_FILE.exists():
            return 0
        data = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
        count = 0
        for item in data.get("entries", []):
            forms = _extract_forms(item)
            if not forms:
                continue
            session.add(
                GlossaryEntry(
                    category=item.get("category", "general"),
                    forms=forms,
                    note=item.get("note"),
                )
            )
            count += 1
        _invalidate_cache()
        return count

# --- Cache --------------------------------------------------------------------
def _invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None

def _terms() -> list[dict]:
    """Cached list of glossary term maps ({lang_code: term}), longest form first."""
    global _cache
    with _lock:
        if _cache is None:
            with session_scope() as session:
                rows = session.scalars(select(GlossaryEntry)).all()
                _cache = [dict(r.forms or {}) for r in rows]
                _cache.sort(
                    key=lambda forms: max((len(v) for v in forms.values()), default=0),
                    reverse=True,
                )
        return _cache

# --- CRUD ---------------------------------------------------------------------
def list_entries(session: Session) -> list[GlossaryEntry]:
    return list(session.scalars(select(GlossaryEntry).order_by(GlossaryEntry.category, GlossaryEntry.en)))


def add_entry(session: Session, *, category: str, forms: dict[str, str], note: str | None = None) -> GlossaryEntry:
    clean = {code: (value or "").strip() for code, value in forms.items() if (value or "").strip()}
    entry = GlossaryEntry(category=category, forms=clean, note=note)
    session.add(entry)
    session.flush()
    _invalidate_cache()
    return entry


def delete_entry(session: Session, entry_id: str) -> bool:
    entry = session.get(GlossaryEntry, entry_id)
    if entry is None:
        return False
    session.delete(entry)
    _invalidate_cache()
    return True


def count(session: Session) -> int:
    return session.query(GlossaryEntry).count()

# --- Term protection ----------------------------------------------------------
_PLACEHOLDER = "GLS{}GLS"  # alphanumeric tokens survive most tokenisers


def _word_regex(term: str) -> re.Pattern:
    # \b works for Latin; for Devanagari we fall back to a plain escaped match.
    if term.isascii():
        return re.compile(rf"\b({re.escape(term)})\b", re.IGNORECASE)
    return re.compile(re.escape(term))


def protect_text(text: str, src_code: str) -> tuple[str, dict[str, dict]]:
    """Replace glossary source terms with placeholders. Returns (masked, mapping)."""
    if not text:
        return text, {}
    mapping: dict[str, dict] = {}
    masked = text
    idx = 0
    for term in _terms():
        src_form = term.get(src_code)
        if not src_form:
            continue
        pattern = _word_regex(src_form)
        if pattern.search(masked):
            token = _PLACEHOLDER.format(idx)
            masked = pattern.sub(token, masked)
            mapping[token] = term
            idx += 1
    return masked, mapping


def restore_text(text: str, mapping: dict[str, dict], tgt_code: str) -> str:
    """Replace placeholders with the canonical target-language term."""
    if not mapping or not text:
        return text
    restored = text
    for token, term in mapping.items():
        target_form = term.get(tgt_code, "")
        # Tolerant match: MT models may alter spacing/case around the token.
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        restored = pattern.sub(target_form, restored)
    return restored