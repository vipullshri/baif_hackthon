"""REST + WebSocket API routes."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __app_name__, __version__
from app.config import settings
from app.db.database import get_db, session_scope
from app.db.models import Job
from app.languages import is_supported, language_options
from app.schemas import (
    GlossaryEntryIn,
    GlossaryEntryOut,
    HealthOut,
    JobList,
    JobOut,
    LanguageOut,
    TextTranslateRequest,
)
from app.services import asr, glossary, media, storage, tts
from app.services.jobs import submit_job
from app.services.pipeline import process_job
from app.services.translate import translator_ready

router = APIRouter(prefix="/api")


# --- Serialization ----------------------------------------------------
def to_job_out(job: Job) -> JobOut:
    data = JobOut.model_validate(job)
    data.has_srt = bool(job.srt_path)
    data.has_vtt = bool(job.vtt_path)
    data.has_audio = bool(job.audio_path)
    data.has_video = bool(job.video_path)
    return data


# --- System -----------------------------------------------------------
@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        status="ok",
        app=__app_name__,
        version=__version__,
        models_enabled=settings.enable_models,
        offline=settings.offline,
        device=settings.device,
        whisper_model=settings.whisper_model,
        mt_backend=settings.mt_backend,
        tts_backend=settings.tts_backend,
        ready={
            "ffmpeg": media.ffmpeg_available(),
            "asr": asr.asr_ready(),
            "translation": translator_ready(),
            "tts": tts.tts_ready(),
        },
    )


@router.get("/languages", response_model=list[LanguageOut])
def languages() -> list[LanguageOut]:
    return [LanguageOut(**opt) for opt in language_options()]


# --- Text translation (synchronous) -----------------------------------
@router.post("/translate/text", response_model=JobOut)
def translate_text_endpoint(payload: TextTranslateRequest) -> JobOut:
    if not is_supported(payload.target_lang):
        raise HTTPException(400, f"Unsupported target language '{payload.target_lang}'")
    if payload.source_lang != "auto" and not is_supported(payload.source_lang):
        raise HTTPException(400, f"Unsupported source language '{payload.source_lang}'")

    input_hash = storage.hash_text(f"{payload.text}|{payload.source_lang}|{payload.target_lang}")

    with session_scope() as session:
        reuse = storage.find_reusable_job(
            session,
            input_hash=input_hash,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            generate_tts=payload.generate_tts,
            generate_subtitles=False,
            burn_subtitles=False,
        )
        if reuse:
            clone = _clone_job(reuse)
            session.add(clone)
            session.flush()
            out = to_job_out(clone)
            return out

        job = Job(
            input_type="text",
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            title=payload.title,
            generate_tts=payload.generate_tts,
            generate_subtitles=False,
            burn_subtitles=False,
            input_text=payload.text,
            input_hash=input_hash,
            status="pending",
        )
        session.add(job)
        session.flush()
        job_id = job.id

    # Text is fast - process inline so the caller gets the result immediately.
    process_job(job_id)
    with session_scope() as session:
        return to_job_out(session.get(Job, job_id))


# --- Media upload (asynchronous) --------------------------------------
@router.post("/jobs", response_model=JobOut, status_code=202)
async def create_media_job(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    title: str | None = Form(None),
    generate_tts: bool = Form(True),
    generate_subtitles: bool = Form(True),
    burn_subtitles: bool = Form(False),
) -> JobOut:
    filename = file.filename or "upload"
    kind = media.media_kind(filename)
    if kind == "unknown":
        raise HTTPException(
            415,
            "Unsupported format. Allowed audio: "
            + ", ".join(sorted(media.AUDIO_EXTS))
            + " | video: "
            + ", ".join(sorted(media.VIDEO_EXTS)),
        )
    if not is_supported(target_lang):
        raise HTTPException(400, f"Unsupported target language '{target_lang}'")

    # Stream upload to disk while enforcing the size limit.
    limit_mb = settings.max_video_mb if kind == "video" else settings.max_audio_mb
    ext = Path(filename).suffix.lower()
    tmp_path = settings.uploads_path / f"_incoming{ext}"
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(tmp_path, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > limit_mb * 1024 * 1024:
                out.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds the {limit_mb} MB limit for {kind}.")
            out.write(chunk)

    input_hash = storage.hash_file(tmp_path)

    with session_scope() as session:
        reuse = storage.find_reusable_job(
            session,
            input_hash=input_hash,
            source_lang=source_lang,
            target_lang=target_lang,
            generate_tts=generate_tts,
            generate_subtitles=generate_subtitles,
            burn_subtitles=burn_subtitles,
        )
        if reuse:
            tmp_path.unlink(missing_ok=True)  # storage-level de-duplication
            clone = _clone_job(reuse)
            session.add(clone)
            session.flush()
            return to_job_out(clone)

        job = Job(
            input_type=kind,
            source_lang=source_lang,
            target_lang=target_lang,
            title=title or filename,
            generate_tts=generate_tts,
            generate_subtitles=generate_subtitles,
            burn_subtitles=burn_subtitles,
            input_filename=filename,
            input_hash=input_hash,
            status="pending",
        )
        session.add(job)
        session.flush()
        job_id = job.id
        final_path = settings.uploads_path / f"{job_id}{ext}"
        job.input_path = storage.rel_to_data(final_path)

    shutil.move(str(tmp_path), str(final_path))
    submit_job(job_id)

    with session_scope() as session:
        return to_job_out(session.get(Job, job_id))


def _clone_job(source: Job) -> Job:
    """Create a completed job that reuses an identical previous result."""
    return Job(
        input_type=source.input_type,
        source_lang=source.source_lang,
        target_lang=source.target_lang,
        title=source.title,
        generate_tts=source.generate_tts,
        generate_subtitles=source.generate_subtitles,
        burn_subtitles=source.burn_subtitles,
        input_filename=source.input_filename,
        input_path=source.input_path,
        input_hash=source.input_hash,
        input_text=source.input_text,
        status="completed",
        stage="done",
        progress=100,
        reused=True,
        mock=source.mock,
        detected_lang=source.detected_lang,
        duration_sec=source.duration_sec,
        source_text=source.source_text,
        translated_text=source.translated_text,
        segments=source.segments,
        srt_path=source.srt_path,
        vtt_path=source.vtt_path,
        audio_path=source.audio_path,
        video_path=source.video_path,
    )


# --- Job retrieval ----------------------------------------------------
@router.get("/jobs", response_model=JobList)
def list_jobs(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> JobList:
    total = db.query(Job).count()
    rows = db.scalars(
        select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200)).offset(offset)
    ).all()
    return JobList(items=[to_job_out(j) for j in rows], total=total)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return to_job_out(job)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    # Remove outputs unless they are shared by another (reused) job.
    out_dir = settings.outputs_path / job_id
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    db.delete(job)
    db.commit()


# --- Artefact download / streaming ------------------------------------
_KIND_MAP = {
    "input": ("input_path", None, False),
    "audio": ("audio_path", "audio/wav", False),
    "video": ("video_path", "video/mp4", False),
    "srt": ("srt_path", "application/x-subrip", True),
    "vtt": ("vtt_path", "text/vtt", False),
}


@router.get("/jobs/{job_id}/file/{kind}")
def get_job_file(job_id: str, kind: str, download: bool = False, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")

    if kind in ("text", "transcript"):
        content = (job.translated_text if kind == "text" else job.source_text) or ""
        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{kind}-{job_id}.txt"'
        return PlainTextResponse(content, headers=headers, media_type="text/plain; charset=utf-8")

    if kind not in _KIND_MAP:
        raise HTTPException(404, f"Unknown artefact '{kind}'")

    attr, media_type, force_attach = _KIND_MAP[kind]
    rel = getattr(job, attr)
    path = storage.abs_from_data(rel)
    if not path or not path.exists():
        raise HTTPException(404, f"Artefact '{kind}' not available for this job")

    disposition = "attachment" if (download or force_attach) else "inline"
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type=disposition,
    )


# --- Live progress (WebSocket) ----------------------------------------
@router.websocket("/jobs/{job_id}/ws")
async def job_progress_ws(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is None:
                    await websocket.send_json({"error": "not_found"})
                    break
                payload = to_job_out(job).model_dump(mode="json")
            await websocket.send_json(payload)
            if job.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.7)
    except WebSocketDisconnect:
        return


# --- Glossary ---------------------------------------------------------
@router.get("/glossary", response_model=list[GlossaryEntryOut])
def get_glossary(db: Session = Depends(get_db)) -> list[GlossaryEntryOut]:
    return [GlossaryEntryOut.model_validate(e) for e in glossary.list_entries(db)]


@router.post("/glossary", response_model=GlossaryEntryOut, status_code=201)
def create_glossary_entry(payload: GlossaryEntryIn, db: Session = Depends(get_db)) -> GlossaryEntryOut:
    entry = glossary.add_entry(
        db, category=payload.category, en=payload.en, hi=payload.hi, mr=payload.mr, note=payload.note
    )
    db.commit()
    db.refresh(entry)
    return GlossaryEntryOut.model_validate(entry)


@router.delete("/glossary/{entry_id}", status_code=204)
def remove_glossary_entry(entry_id: str, db: Session = Depends(get_db)):
    if not glossary.delete_entry(db, entry_id):
        raise HTTPException(404, "Glossary entry not found")
    db.commit()