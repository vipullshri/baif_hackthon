#!/usr/bin/env python
"""
BhashaSetu - model pre-downloader.

Fetches the open-source models BhashaSetu uses into the project-local model cache
(`backend/models` by default) so the app can later run **fully offline**.

The model IDs mirror `backend/app/config.py`; override any of them with the same
`BHASHASETU_*` environment variables.

Usage (from the project root, with the backend venv active):

    python scripts/download_models.py            # defaults: whisper + IndicTrans2 + MMS-TTS
    python scripts/download_models.py --all      # also NLLB + Indic Parler-TTS
    python scripts/download_models.py --parler   # add the high-quality TTS voices
    python scripts/download_models.py --nllb     # add the NLLB fallback translator
    python scripts/download_models.py --whisper-model medium

All models are free and openly licensed - see `docs/MODELS.md`.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# --- Resolve the model cache from app settings and route HF/torch there ---------
# Reuse the app's single source of truth (app.config): downloads land under the
# configured base dir (<base>/models) with HF/torch caches and TEMP all routed to
# the same drive for offline portability. Set BHASHASETU_BASE_DIR to choose it.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from app.config import settings  # noqa: E402

settings.ensure_dirs()
settings.apply_offline_env()
MODELS_DIR = settings.models_path

def _env(name: str, default: str) -> str:
    return os.environ.get(f"BHASHASETU_{name}", default)


# Model IDs (mirror backend/app/config.py) ---------------------------------------
WHISPER_MODEL = _env("WHISPER_MODEL", "small")
INDICTRANS = [
    _env("INDICTRANS_EN_INDIC", "ai4bharat/indictrans2-en-indic-dist-200M"),
    _env("INDICTRANS_INDIC_EN", "ai4bharat/indictrans2-indic-en-dist-200M"),
    _env("INDICTRANS_INDIC_INDIC", "ai4bharat/indictrans2-indic-indic-dist-320M"),
]
NLLB = _env("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
MMS_TTS = ["facebook/mms-tts-eng", "facebook/mms-tts-hin", "facebook/mms-tts-mar"]
PARLER = "ai4bharat/indic-parler-tts"


# --- Helpers --------------------------------------------------------------------
def _hr(title: str) -> None:
    print(f"\n{'-' * 64}\n  {title}\n{'-' * 64}")

def download_repo(repo_id: str) -> bool:
    """Download a full HF repo snapshot into the local cache."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "  X huggingface_hub is not installed.\n"
            "    Install the ML stack first: pip install -r backend/requirements-ml.txt",
            file=sys.stderr,
        )
        return False
    try:
        print(f"  • {repo_id} ...", flush=True)
        snapshot_download(repo_id=repo_id, cache_dir=str(MODELS_DIR))
        print(f"    ✓ done")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"    X failed: {exc}", file=sys.stderr)
        return False

def download_whisper(size: str) -> bool:
    """Download the faster-whisper model exactly as the app loads it."""
    print(f"  • faster-whisper '{size}' ...", flush=True)
    try:
        from faster_whisper import WhisperModel

        WhisperModel(size, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))
        print("    ✓ done")
        return True
    except ImportError:
        # Fall back to a raw snapshot of the CTranslate2 weights.
        print("    (faster-whisper not installed - fetching repo snapshot instead)")
        return download_repo(f"Systran/faster-whisper-{size}")
    except Exception as exc:  # noqa: BLE001
        print(f"    X failed: {exc}", file=sys.stderr)
        return False


# --- Main -----------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-download BhashaSetu's open models for offline use.")
    parser.add_argument("--all", action="store_true", help="Download everything (adds NLLB + Parler-TTS).")
    parser.add_argument("--nllb", action="store_true", help="Also download the NLLB fallback translator.")
    parser.add_argument("--parler", action="store_true", help="Also download Indic Parler-TTS (HQ voices).")
    parser.add_argument("--no-whisper", action="store_true", help="Skip the Whisper ASR model.")
    parser.add_argument("--whisper-model", default=WHISPER_MODEL, help="Whisper size: tiny|base|small|medium.")
    args = parser.parse_args()

    want_nllb = args.all or args.nllb
    want_parler = args.all or args.parler

    print(f"BhashaSetu model downloader")
    print(f"Model cache: {MODELS_DIR}")

    results: list[tuple[str, bool]] = []

    if not args.no_whisper:
        _hr("Speech-to-Text - faster-whisper (MIT)")
        results.append((f"whisper-{args.whisper_model}", download_whisper(args.whisper_model)))

    _hr("Translation - AI4Bharat IndicTrans2 (MIT)")
    for repo in INDICTRANS:
        results.append((repo, download_repo(repo)))

    if want_nllb:
        _hr("Translation fallback - NLLB-200 (CC-BY-NC)")
        results.append((NLLB, download_repo(NLLB)))

    _hr("Text-to-Speech - MMS-TTS (Meta)")
    for repo in MMS_TTS:
        results.append((repo, download_repo(repo)))

    if want_parler:
        _hr("Text-to-Speech HQ - Indic Parler-TTS (Apache-2.0)")
        results.append((PARLER, download_repo(PARLER)))

    # Summary ------------------------------------------------------------------------
    _hr("Summary")
    ok = sum(1 for _, success in results if success)
    for name, success in results:
        print(f"  {'✓' if success else 'X'}  {name}")
    print(f"\n{ok}/{len(results)} downloaded into {MODELS_DIR}")

    if ok == len(results):
        print("\nAll set. Run offline with:")
        print("  set BHASHASETU_ENABLE_MODELS=true && set BHASHASETU_OFFLINE=true")
        return 0
    print("\nSome downloads failed - re-run this script (downloads resume) once dependencies/network are ready.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())