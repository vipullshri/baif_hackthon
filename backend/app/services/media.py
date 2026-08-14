"""
FFmpeg-based media processing.

Handles audio extraction, duration probing, subtitle burn-in and voice-over
muxing. FFmpeg is the only external system dependency and is fully open-source.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".wmv", ".mkv", ".flv", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".wma", ".ogg"}

class MediaError(RuntimeError):
    """Raised when an FFmpeg operation fails."""

@lru_cache
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

@lru_cache
def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None

def media_kind(filename: str) -> str:
    """Classify a filename as 'audio', 'video' or 'unknown'."""
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "unknown"

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # ffmpeg not installed
        raise MediaError("FFmpeg is not installed or not on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise MediaError(f"FFmpeg failed: {exc.stderr[-800:]}") from exc

def probe_duration(path: str | Path) -> float | None:
    """Return media duration in seconds, or None if it cannot be determined."""
    if not ffprobe_available():
        return None
    try:
        proc = _run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ]
        )
        data = json.loads(proc.stdout)
        return float(data["format"]["duration"])
    except (MediaError, KeyError, ValueError, json.JSONDecodeError):
        return None

def extract_audio(input_path: str | Path, out_wav: str | Path, sample_rate: int = 16000) -> Path:
    """
    Extract a mono 16 kHz PCM WAV from any audio/video file.

    16 kHz mono PCM is exactly what whisper expects, so this normalises every
    supported format into a single clean input.
    """
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vn",                  # drop video
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", "1",             # mono
            str(out_wav),
        ]
    )
    return out_wav

def _escape_subtitle_path(srt_path: Path) -> str:
    """Escape a path for use inside FFmpeg's ``subtitles=`` filter (Windows-safe)."""
    p = str(srt_path).replace("\\", "/")
    # Escape the drive-letter colon, e.g. C: -> C\:
    p = p.replace(":", r"\:")
    return p

def burn_subtitles(video_in: str | Path, srt_path: str | Path, video_out: str | Path) -> Path:
    """Render subtitles permanently onto the video (hard-subs)."""
    video_out = Path(video_out)
    video_out.parent.mkdir(parents=True, exist_ok=True)
    style = "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3"
    vf = f"subtitles='{_escape_subtitle_path(Path(srt_path))}':force_style='{style}'"
    _run(
        [
            "ffmpeg", "-y",
            "-i", str(video_in),
            "-vf", vf,
            "-c:a", "copy",
            str(video_out),
        ]
    )
    return video_out

def replace_audio(video_in: str | Path, audio_in: str | Path, video_out: str | Path) -> Path:
    """Replace the video's audio track with a generated voice-over."""
    video_out = Path(video_out)
    video_out.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg", "-y",
            "-i", str(video_in),
            "-i", str(audio_in),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-shortest",
            str(video_out),
        ]
    )
    return video_out