"""
Storage, hashing and translation-memory (reuse) service.

Implements BAIF's reuse requirement: every input is SHA-256 hashed, and an
identical request (same content + same languages + same options) is served
instantly from a previous job instead of being re-processed.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Job

_CHUNK = 1 << 20  # 1 MiB

def hash_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def fingerprint(input_hash: str, source_lang: str, target_lang: str,
                generate_tts: bool, generate_subtitles: bool, burn_subtitles: bool) -> str:
    """A composite key identifying an identical translation request."""
    key = f"{input_hash}|{source_lang}|{target_lang}|{int(generate_tts)}|{int(generate_subtitles)}|{int(burn_subtitles)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def find_reusable_job(
    session: Session,
    *,
    input_hash: str,
    source_lang: str,
    target_lang: str,
    generate_tts: bool,
    generate_subtitles: bool,
    burn_subtitles: bool,
) -> Job | None:
    """Return a completed, non-mock job that exactly matches this request."""
    stmt = (
        select(Job)
        .where(
            Job.input_hash == input_hash,
            Job.target_lang == target_lang,
            Job.source_lang == source_lang,
            Job.status == "completed",
            Job.mock.is_(False),
            Job.generate_tts == generate_tts,
            Job.generate_subtitles == generate_subtitles,
            Job.burn_subtitles == burn_subtitles,
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return session.scalar(stmt)

def job_output_dir(job_id: str) -> Path:
    out = settings.outputs_path / job_id
    out.mkdir(parents=True, exist_ok=True)
    return out

def save_upload_stream(src_file, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(src_file, out)
    return dest

def rel_to_data(path: str | Path | None) -> str | None:
    """Store paths relative to the data dir so the DB stays portable."""
    if path is None:
        return None
    try:
        return str(Path(path).resolve().relative_to(settings.data_path))
    except ValueError:
        return str(path)

def abs_from_data(rel: str | None) -> Path | None:
    if not rel:
        return None
    return (settings.data_path / rel).resolve()