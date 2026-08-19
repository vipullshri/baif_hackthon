"""
Pipeline orchestration.

Takes a persisted Job, runs the appropriate stages (media -> ASR -> glossary ->
translation -> TTS -> subtitles -> burn-in) and records progress + results in the DB.

The pipeline is deliberately synchronous and self-contained; it is executed on a
background worker thread (see ``jobs.py``). For multi-node scale-out the same
function can be driven by a Celery task without modification.
"""
from __future__ import annotations

import logging
import re

from app.config import settings
from app.db.database import session_scope
from app.db.models import Job
from app.languages import get_language
from app.services import asr, glossary, media, storage, subtitles, tts
from app.services.translate import translate_segments, translate_text

logger = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
# Markers that strongly indicate Marathi over Hindi.
_MARATHI_MARKERS = ("ळ", "आहे", "नाही", "मला", "तुम्ही", "आम्ही", "होते", "करा")

def detect_text_language(text: str) -> str:
    """Lightweight script/keyword heuristic for text input (en / hi / mr)."""
    if not text:
        return "en"
    deva = len(_DEVANAGARI.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if deva == 0 or latin > deva:
        return "en"
    if any(marker in text for marker in _MARATHI_MARKERS):
        return "mr"
    return "hi"


# --- DB helpers -------------------------------------------------------
def _update(job_id: str, **fields) -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)

def _translate_with_glossary(text: str, src: str, tgt: str) -> str:
    masked, mapping = glossary.protect_text(text, src)
    out = translate_text(masked, src, tgt)
    return glossary.restore_text(out, mapping, tgt)

def _translate_segments_with_glossary(texts: list[str], src: str, tgt: str) -> list[str]:
    masked, mappings = [], []
    for t in texts:
        m, mp = glossary.protect_text(t, src)
        masked.append(m)
        mappings.append(mp)
    translated = translate_segments(masked, src, tgt)
    return [glossary.restore_text(tr, mp, tgt) for tr, mp in zip(translated, mappings)]


# --- Main entry point -------------------------------------------------
def process_job(job_id: str) -> None:
    try:
        _run(job_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        _update(job_id, status="failed", error=str(exc), stage="error")

def _run(job_id: str) -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise RuntimeError("Job not found")
        snapshot = {
            "input_type": job.input_type,
            "source_lang": job.source_lang,
            "target_lang": job.target_lang,
            "input_path": storage.abs_from_data(job.input_path) if job.input_path else None,
            "input_text": job.input_text,
            "generate_tts": job.generate_tts,
            "generate_subtitles": job.generate_subtitles,
            "burn_subtitles": job.burn_subtitles,
            "input_filename": job.input_filename,
        }

    _update(job_id, status="processing", stage="starting", progress=5, mock=not _real_mode())
    target = snapshot["target_lang"]
    out_dir = storage.job_output_dir(job_id)

    # --- 1. Acquire transcript + segments -----------------------------
    if snapshot["input_type"] == "text":
        src = snapshot["source_lang"]
        if src in ("auto", "", None):
            src = detect_text_language(snapshot["input_text"] or "")
        source_text = (snapshot["input_text"] or "").strip()
        segments_src = [{"start": 0.0, "end": 0.0, "text": source_text}]
        duration = None
        _update(job_id, stage="translating", progress=40, detected_lang=src, source_text=source_text)
    else:
        _update(job_id, stage="extracting-audio", progress=10)
        input_path = snapshot["input_path"]
        wav_path = settings.tmp_path / f"{job_id}.wav"
        if media.ffmpeg_available():
            media.extract_audio(input_path, wav_path)
            audio_for_asr = str(wav_path)
        else:
            # No FFmpeg: fall back to feeding the original file straight to ASR.
            audio_for_asr = str(input_path)
        duration = media.probe_duration(input_path)

        _update(job_id, stage="transcribing", progress=25, duration_sec=duration)
        result = asr.transcribe(audio_for_asr, snapshot["source_lang"], duration=duration)
        src = result.language if snapshot["source_lang"] in ("auto", "", None) else snapshot["source_lang"]
        source_text = result.text
        segments_src = [{"start": s.start, "end": s.end, "text": s.text} for s in result.segments]
        duration = result.duration
        _update(
            job_id, stage="translating", progress=55,
            detected_lang=src, source_text=source_text,
            duration_sec=duration,
        )

    # --- 2. Translate -------------------------------------------------
    if src == target:
        translated_text = source_text
        translated_segments = [{"text": s["text"]} for s in segments_src]
    else:
        translated_text = _translate_with_glossary(source_text, src, target)
        seg_texts = [s["text"] for s in segments_src]
        translated_segments = _translate_segments_with_glossary(seg_texts, src, target)

    timed_segments = [
        {"start": s["start"], "end": s["end"], "source": s["text"], "translated": tr}
        for s, tr in zip(segments_src, translated_segments)
    ]
    _update(job_id, stage="translated", progress=65, translated_text=translated_text, segments=timed_segments)

    srt_rel = vtt_rel = audio_rel = video_rel = None
    audio_out = None

    # --- 3. Text-to-Speech (voice-over) -------------------------------
    if snapshot["generate_tts"]:
        _update(job_id, stage="synthesizing-voice", progress=78)
        audio_out = out_dir / "voiceover.wav"
        tts.synthesize(translated_text, target, audio_out)
        audio_rel = storage.rel_to_data(audio_out)

    # --- 4. Subtitles (only when we have real timings) ----------------
    has_timings = snapshot["input_type"] != "text" and any(
        seg["end"] > seg["start"] for seg in timed_segments
    )
    srt_out = None
    if snapshot["generate_subtitles"] and has_timings:
        _update(job_id, stage="building-subtitles", progress=88)
        sub_segments = [
            {"start": s["start"], "end": s["end"], "text": s["translated"]}
            for s in timed_segments
        ]
        srt_out = out_dir / "subtitles.srt"
        vtt_out = out_dir / "subtitles.vtt"
        subtitles.write_subtitles(sub_segments, srt_out, vtt_out)
        srt_rel = storage.rel_to_data(srt_out)
        vtt_rel = storage.rel_to_data(vtt_out)

    # --- 5. Produces a translated video (video input only) ---------------------------
    if snapshot["input_type"] == "video" and  media.ffmpeg_available():
        try:
            base_video = snapshot["input_path"]

            #5.a Replace the original audio with the generated voice-over (if any)
            if audio_out is not None:
                _update(job_id, stage="dubbing-video", progress=91)
                dubbed_out = out_dir / "dubbed.mp4"
                media.replace_audio(base_video, audio_out, dubbed_out)
                base_video = dubbed_out
                video_rel = storage.rel_to_data(dubbed_out)

            #5.b Burn-in the translated subtitles (if any)
            if snapshot["burn_subtitles"] and srt_out is not None:    
                _update(job_id, stage="burning-captions", progress=94)
                video_out = out_dir / "captioned.mp4"
                media.burn_subtitles(base_video, srt_out, video_out)
                video_rel = storage.rel_to_data(video_out)
        except media.MediaError as exc:
            logger.warning("Video render failed for %s: %s", job_id, exc)

    _update(
        job_id,
        status="completed",
        stage="done",
        progress=100,
        source_lang=src,
        srt_path=srt_rel,
        vtt_path=vtt_rel,
        audio_path=audio_rel,
        video_path=video_rel,
    )
    logger.info("Job %s completed (%s -> %s)", job_id, src, target)

def _real_mode() -> bool:
    """True when at least the translation stage uses a real model."""
    from app.services.translate import translator_ready
    return settings.enable_models and translator_ready()