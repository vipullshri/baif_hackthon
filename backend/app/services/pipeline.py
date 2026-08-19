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
from app.services import asr, cancellation, glossary, media, storage, subtitles, tts
from app.services.translate import translate_segments, translate_text

logger = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]+")
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


class DurationLimitError(RuntimeError):
    """Raised when media exceeds the configured maximum duration."""


class JobCancelled(Exception):
    """Raised internally when a running job has been asked to cancel."""


def _check_cancel(job_id: str) -> None:
    """Abort cooperatively if a cancellation has been requested for this job."""
    if cancellation.is_requested(job_id):
        raise JobCancelled(job_id)


def _enforce_duration(duration: float | None) -> None:
    """Reject media longer than the configured limit before heavy processing."""
    limit_min = settings.max_duration_min
    if duration and limit_min and duration > limit_min * 60:
        raise DurationLimitError(
            f"Media is {duration / 60:.1f} min long, which exceeds the "
            f"{limit_min} min limit."
        )

# Approximate speaking rate used to synthesise subtitle timings for text input,
# which has no real timestamps of its own (~2.5 words/second ≈ 150 wpm).
_WORDS_PER_SECOND = 2.5
_MIN_SEGMENT_SEC = 1.2


def _estimate_timings(texts: list[str]) -> list[tuple[float, float]]:
    """Produce sequential (start, end) spans for text that has no timestamps."""
    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for text in texts:
        words = max(1, len((text or "").split()))
        duration = max(_MIN_SEGMENT_SEC, words / _WORDS_PER_SECOND)
        spans.append((cursor, cursor + duration))
        cursor += duration
    return spans


# --- DB helpers -------------------------------------------------------------
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


# --- Main entry point -------------------------------------------------------
def process_job(job_id: str) -> None:
    try:
        _run(job_id)
    except JobCancelled:
        logger.info("Job %s cancelled", job_id)
        _update(job_id, status="cancelled", stage="cancelled", error=None)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        _update(job_id, status="failed", error=_safe_error(exc), stage="error")
    finally:
        cancellation.clear(job_id)


def _safe_error(exc: Exception) -> str:
    """Return a user-safe message; full detail is logged, not exposed.

    Raw FFmpeg/model exceptions can leak stderr, absolute paths and internal
    model names, so only whitelisted, self-authored messages are surfaced.
    """
    if isinstance(exc, DurationLimitError):
        return str(exc)
    if isinstance(exc, media.MediaError):
        return "Media processing failed. Please check the file is valid and try again."
    return "Processing failed due to an internal error. Please try again."


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
    _check_cancel(job_id)
    target = snapshot["target_lang"]
    out_dir = storage.job_output_dir(job_id)

    # --- 1. Acquire transcript + segments -----------------------------------
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
        _enforce_duration(duration)

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

    # --- 2. Translate -------------------------------------------------------
    _check_cancel(job_id)
    if src == target:
        translated_text = source_text
        translated_segments = [s["text"] for s in segments_src]
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

    # --- 3. Text-to-Speech (voice-over) -------------------------------------
    if snapshot["generate_tts"]:
        _check_cancel(job_id)
        _update(job_id, stage="synthesizing-voice", progress=78)
        audio_out = out_dir / "voiceover.wav"
        tts.synthesize(translated_text, target, audio_out)
        audio_rel = storage.rel_to_data(audio_out)

    # --- 4. Subtitles -------------------------------------------------------
    # Media input carries real ASR timings; text input has none, so we synthesise
    # sequential timings from an average speaking rate instead of skipping subs.
    has_timings = any(seg["end"] > seg["start"] for seg in timed_segments)
    srt_out = None
    if snapshot["generate_subtitles"] and (has_timings or snapshot["input_type"] == "text"):
        _update(job_id, stage="building-subtitles", progress=88)
        if has_timings:
            sub_segments = [
                {"start": s["start"], "end": s["end"], "text": s["translated"]}
                for s in timed_segments
            ]
        else:
            spans = _estimate_timings([s["translated"] for s in timed_segments])
            sub_segments = [
                {"start": start, "end": end, "text": s["translated"]}
                for s, (start, end) in zip(timed_segments, spans)
            ]
        srt_out = out_dir / "subtitles.srt"
        vtt_out = out_dir / "subtitles.vtt"
        subtitles.write_subtitles(sub_segments, srt_out, vtt_out)
        srt_rel = storage.rel_to_data(srt_out)
        vtt_rel = storage.rel_to_data(vtt_out)

    # --- 5. Produce a translated video (video input only) -------------------
    # Dub the translated voice-over back in and/or burn captions so the user
    # gets a playable video, not just a separate audio track.
    render_warning: str | None = None
    if snapshot["input_type"] == "video":
        if not media.ffmpeg_available():
            render_warning = (
                "FFmpeg is unavailable, so no translated video was produced; "
                "the voice-over and subtitles are still available."
            )
            logger.warning("Skipping video render for %s: FFmpeg unavailable", job_id)
        else:
            try:
                base_video = snapshot["input_path"]

                # 5a. Replace the original audio with the translated voice-over.
                if audio_out is not None:
                    _update(job_id, stage="dubbing-video", progress=91)
                    dubbed_out = out_dir / "dubbed.mp4"
                    media.replace_audio(base_video, audio_out, dubbed_out)
                    base_video = dubbed_out
                    video_rel = storage.rel_to_data(dubbed_out)

                # 5b. Burn captions onto the (possibly dubbed) video.
                if snapshot["burn_subtitles"] and srt_out is not None:
                    _update(job_id, stage="burning-captions", progress=94)
                    video_out = out_dir / "captioned.mp4"
                    media.burn_subtitles(base_video, srt_out, video_out)
                    video_rel = storage.rel_to_data(video_out)
            except media.MediaError as exc:
                logger.warning("Video render failed for %s: %s", job_id, exc)
                # If nothing usable came out of the pipeline at all, fail the job
                # instead of silently reporting success. Otherwise complete with a
                # warning so the user still gets the audio/subtitle artefacts.
                if not (audio_rel or srt_rel):
                    raise
                render_warning = (
                    "Translated video could not be rendered; the voice-over and "
                    "subtitles are still available."
                )

    _update(
        job_id,
        status="completed",
        stage="done",
        progress=100,
        source_lang=src,
        error=render_warning,
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