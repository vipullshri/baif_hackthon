"""
Subtitle generation.

Produces SubRip (``.srt``) and WebVTT (``.vtt``) files from time-aligned
translated segments. These are consumed by the UI's <track> element and by
FFmpeg for optional burned-in captions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

Segment = Mapping[str, object]  # {"start": float, "end": float, "text": str}


def _clamp(seconds: float) -> float:
    return max(0.0, float(seconds))


def format_timestamp(seconds: float, *, vtt: bool = False) -> str:
    seconds = _clamp(seconds)
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    sep = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def build_srt(segments: Iterable[Segment]) -> str:
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = format_timestamp(float(seg["start"]))
        end = format_timestamp(float(seg["end"]))
        text = str(seg.get("text", "")).strip()
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines).strip() + "\n"


def build_vtt(segments: Iterable[Segment]) -> str:
    lines: list[str] = ["WEBVTT", ""]
    for seg in segments:
        start = format_timestamp(float(seg["start"]), vtt=True)
        end = format_timestamp(float(seg["end"]), vtt=True)
        text = str(seg.get("text", "")).strip()
        lines.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(lines).strip() + "\n"


def write_subtitles(
    segments: list[Segment],
    srt_path: str | Path,
    vtt_path: str | Path,
) -> tuple[Path, Path]:
    srt_path, vtt_path = Path(srt_path), Path(vtt_path)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    vtt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(build_srt(segments), encoding="utf-8")
    vtt_path.write_text(build_vtt(segments), encoding="utf-8")
    return srt_path, vtt_path