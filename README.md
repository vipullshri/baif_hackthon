# 🌉 BhashaSetu (भाषासेतु)

### The Offline Language Bridge for Rural India

**Transcribe → Translate → Voice-over → Subtitle**
**Marathi · Hindi · English — 100% Open Source, 100% Offline-Capable**

*Built for BAIF Development Research Foundation*

</div>

---

## 🎯 What is BhashaSetu?

**BhashaSetu** ("Language Bridge") is a production-grade, **offline-capable** media translation
platform. Field officers at BAIF can drop in a **text note, an audio field-recording, or an
agricultural demo video**, and instantly receive:

| Output | Description |
| ------ | ----------- |
| 📝 **Translated text** | Accurate translation between Marathi, Hindi & English |
| 🔊 **Translated voice-over** | Natural text-to-speech in the target language |
| 🔠 **Subtitles** | Time-aligned `.srt` / `.vtt` files **and** burned-in captions |
| ♻️ **Reusable library** | Every job is stored, hashed & de-duplicated for instant reuse |

Everything runs on a **single Windows 11 machine** (Intel i5 / 16 GB RAM / CPU-only) with
**no cloud, no API keys, no licensing fees**.

---

## 🌟 What makes it unique

1. **🚜 Agricultural Domain Glossary** — A curated, editable glossary guarantees that BAIF-specific
   terms (crop names, cattle breeds, scheme names, "BAIF" itself) translate **consistently** every
   time. Generic translators get these wrong; BhashaSetu does not.
2. **♻️ Translation Memory + De-duplication** — Files are SHA-256 hashed. Re-uploading the same
   recording returns the cached result in milliseconds, directly satisfying BAIF's *reuse* requirement.
3. **📦 Single Deployable, Truly Offline** — The FastAPI server serves the UI itself — a polished
   **zero-build** UI by default (no Node toolchain), or the compiled **React** build if you prefer.
   After a one-time model download, **unplug the internet** and it keeps working.
4. **🧑‍🏫 Human-in-the-loop** — Reviewers can correct any translation; corrections feed back into the
   glossary & memory, so the system *improves with use*.
5. **🪴 Modern, calm, India-first UI** — A unique earthy-tech design built for low-stress field use.

---

## 🏗️ Architecture at a glance

```
                          BhashaSetu (single host)
                         --------------------------

Upload      React UI ──HTTP/WS──> FastAPI ──> Job Queue (async)
text /                                           │
audio /                                          ▼
video ───┐                                 Pipeline
         │                         ┌───────────────────────────┐
         │                         │ 1. FFmpeg   (extract audio)│
         │                         │ 2. Whisper  (speech→text)  │
         │                         │ 3. Glossary (protect terms)│
         │                         │ 4. IndicTrans2 (translate) │
         │                         │ 5. MMS/Parler TTS (voice)  │
         │                         │ 6. SRT/VTT + FFmpeg burn-in│
         │                         └───────────────────────────┘
         │                                       ▼
         └───────────────────────> SQLite + local file library (reuse)
```

Full details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 📦 Open-Source Model Stack (all free, all offline)

| Stage | Model | License | Why |
| ----- | ----- | ------- | --- |
| Speech-to-Text | **faster-whisper** (`small`/`medium`) | MIT | Best multilingual ASR; word-level timestamps; CPU-optimised (CTranslate2) |
| Translation | **AI4Bharat IndicTrans2** (distilled 200M) | MIT | State-of-the-art for Indian languages; built in India |
| Text-to-Speech | **MMS-TTS** (default) / **Indic Parler-TTS** (HQ) | CC-BY-NC / Apache-2.0 | Lightweight CPU voices for mr/hi/en |
| Media | **FFmpeg** | LGPL | Industry standard audio/video processing |

> Models are **pluggable** behind clean interfaces - swap in NLLB-200 or any HF model via config.
> See [docs/MODELS.md](docs/MODELS.md) for the licensing rationale and alternatives.

---

## 🚀 Quick Start

### Windows 11 (one command)

```powershell
# From the project root, in PowerShell
./scripts/install.ps1
```

This checks prerequisites, creates the virtual environment, installs dependencies,
and starts the app automatically by default.

Common options:
- `-Live` installs the ML stack and pre-downloads models.
- `-BuildFrontend` forces a fresh React rebuild.
- `-NoRun` completes setup without auto-start.
- `-Reinstall` rebuilds the install state.

> **Demo mode:** If the heavy ML models aren't downloaded yet, the backend automatically runs in
> a deterministic **mock mode** so you can demo the full UI/UX flow immediately. Flip
> `BHASHASETU_ENABLE_MODELS=true` in `.env` once models are present.

Manual setup commands are intentionally moved to advanced guidance:
[docs/INSTALLATION.md](docs/INSTALLATION.md)

### 🪟 Prefer a double-click app? Build a Windows `.exe`

No Python needed on the target machine — package BhashaSetu into a self-contained Windows app:

```powershell
# From the project root - builds the portable .exe AND the installer-ready app folder
./scripts/build_exe.ps1 -Both
```

Double-click `dist\BhashaSetu.exe`: a small control window opens, the local server starts, and your
browser opens to the UI automatically. You can also build a friendly `setup.exe` (Inno Setup) and
package the full ML pipeline — see
[docs/INSTALLATION.md §13](docs/INSTALLATION.md#13-run-as-a-standalone-windows-app-exe).

Full setup (incl. FFmpeg & GPU notes): [docs/INSTALLATION.md](docs/INSTALLATION.md)

---

## 📁 Repository layout

```
baif_hackathon/
├── backend/            FastAPI app + ML pipeline services
│   ├── launcher.py     desktop entry point for the packaged Windows .exe
│   └── app/
│       ├── services/   asr · translate · tts · media · subtitles · glossary · storage · pipeline
│       ├── api/        REST + WebSocket routes
│       ├── data/       glossary seed, SQLite db, media library
│       └── static/     compiled React UI (created by `npm run build`)
├── frontend/           React + Vite + Tailwind UI (required runtime UI)
├── installer/          PyInstaller spec + Inno Setup script for the Windows .exe
├── presentation/       self-contained slide decks (index.html ; technical.html)
├── scripts/            install.ps1 · download_models.py · build_exe.ps1
└── docs/               ARCHITECTURE · INSTALLATION · MODELS
```

---

## 👩🏽‍💻 Presentation

Three self-contained slide decks ship in [presentation/](presentation/) — no internet or dependencies:

- **Full pitch deck** — [presentation/index.html](presentation/index.html) (problem → solution →
  architecture → models → demo → impact → roadmap).
- **Highlights** — [presentation/highlights.html](presentation/highlights.html), a fast 6-slide
  condensed version of the pitch (problem → solution → how it works → glossary → impact).
- **Technical overview** — [presentation/technical.html](presentation/technical.html), a concise
  6-slide intermediate walkthrough (what it does → architecture → pipeline → glossary/memory → stack).
- **In simple words** — [presentation/overview.html](presentation/overview.html), a 6-slide
  plain-language deck for non-technical viewers (no jargon — what it is, what you can do, why it helps).

Navigate with <kbd>←</kbd>/<kbd>→</kbd> or <kbd>Space</kbd>, jump via the dots, and press
<kbd>F</kbd> for fullscreen.

---

## 📊 Performance envelope (target hardware: i5 11th-gen, 16 GB, CPU)

| Input | Approx. processing time* |
| ----- | ------------------------ |
| Text paragraph | < 1 s |
| 5-min audio | ~2-4 min |
| 15-min video (full pipeline) | ~8-15 min |

\* With `whisper-small` + IndicTrans2-distilled on CPU. Faster with `int8` quantisation (default)
and dramatically faster on any CUDA GPU.

---

## 🤝 Built for impact

BhashaSetu lets BAIF's knowledge — field guides, training videos, livestock & agronomy advice —
reach farmers **in their mother tongue**, without recurring software costs and without sending a
single sensitive field recording to the cloud.

> *Every voice. Every language. Offline.*