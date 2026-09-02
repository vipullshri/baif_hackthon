# BhashaSetu - Installation Guide (BAIF Handover)

Step-by-step guide for setting up BhashaSetu from scratch on a fresh Windows machine.
Follow the sections in order - do not skip steps.

---

## 1. Check available disk space

BhashaSetu requires approximately **15-20 GB** of free disk space for the full live install
(Python packages ~3 GB + ML models ~10-12 GB + working data).

Check free space before starting:

1. Open **File Explorer** -> right-click the drive you want to install on (e.g. `C:` or `D:`) -> **Properties**.
2. Confirm at least **20 GB free**.

Or in PowerShell:
```powershell
Get-PSDrive C | Select-Object Name, @{N="Free(GB)";E={"{0:N1}" -f ($_.Free/1GB)}}
```

If space is tight, choose a larger drive (e.g. `D:\`) - the installer will ask you where to install.

---

## 2. Install Python 3.12

1. Go to **https://www.python.org/downloads/** and download **Python 3.12** (Windows installer, 64-bit).
2. Run the installer.
3. **Important:** on the first screen, tick **"Add Python to PATH"** before clicking Install Now.
4. Verify the install - open a new PowerShell window and run:

```powershell
python --version
```

Expected output: `Python 3.12.x`

> If you see `Python was not found`, restart PowerShell and try again, or re-run the installer and tick "Add to PATH".

---

## 3. Install Node.js 18+

Node.js is required to build the web frontend.

1. Go to **https://nodejs.org** and download the **LTS** version (18 or higher).
2. Run the installer with default settings.
3. Verify:

```powershell
node --version
npm --version
```

Expected: `v18.x.x` (or higher) and `10.x.x` (or higher).

---

## 4. Install FFmpeg

FFmpeg is required to process audio and video files.

**Option A - automatic via winget (recommended):**
```powershell
winget install Gyan.FFmpeg
```

**Option B - manual:**
1. Download the "essentials" build from **https://www.gyan.dev/ffmpeg/builds/**
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to PATH: open **System Properties -> Environment Variables -> Path -> Edit -> New** and add `C:\ffmpeg\bin`.
4. Restart PowerShell, then verify:

```powershell
ffmpeg -version
```

---

## 5. Get the code from Git

Open **PowerShell as Administrator** (right-click the Start menu -> "Windows PowerShell (Admin)") and run:

```powershell
cd C:\
git clone https://github.com/your-org/baif_hackathon.git
cd baif_hackathon
```

> Replace `https://github.com/your-org/baif_hackathon.git` with the actual repository URL shared by the development team.

If Git is not installed:
```powershell
winget install Git.Git
```
Then close and reopen PowerShell and retry the clone.

---

## 6. Set your HuggingFace token

BhashaSetu uses **IndicTrans2** AI models for high-quality translation. These models are hosted on
HuggingFace and require a token to download.

The HuggingFace token has been shared with you separately (by email or as communicated by the team).

**Option A - set before running the installer (recommended for first install):**

In the same PowerShell window before running the installer:

```powershell
$env:BHASHASETU_HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

The installer will save it permanently to `backend\.env`.

**Option B - edit `backend\.env` directly (for updating the token after install):**

Open `backend\.env` in any text editor (e.g. Notepad) and add or update this line:

```
BHASHASETU_HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

If `backend\.env` does not exist yet, copy `backend\.env.example` to `backend\.env` first, then add the line.

Replace `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` with the actual token value from the email/communication.

> If you do not have the token yet, contact the development team before proceeding.

---

## 7. Run the installer

**Stay in the same PowerShell (Admin) window** with the project folder open, then run:

```powershell
& .\scripts\install.ps1 -Live -BuildFrontend
```

> **Important:** use `& .\` (call operator) - do not run as `powershell -File ...` as Windows
> security policy may block it.

The installer will:
1. Ask you which drive/folder to install into - press **Enter** to use the project folder, or type a path like `D:\` for a separate drive.
2. Create the Python virtual environment.
3. Install all Python dependencies.
4. Install FFmpeg automatically if not already present.
5. Download all AI models from HuggingFace (~10-12 GB, first time only).
6. Build the React web frontend.
7. Save all configuration to `backend/.env`.
8. Start the app and open **http://127.0.0.1:8000** in your browser.

The first install takes **20-40 minutes** depending on internet speed (model download is the slow part).
Subsequent starts take a few seconds.

---

## 8. Verify the app is running

After the installer finishes, open your browser at:

```
http://127.0.0.1:8000
```

You should see the BhashaSetu web interface with tabs: **Translate**, **Library**, **Glossary**, **System**.

Health check (optional):
```powershell
curl http://127.0.0.1:8000/api/health
```

---

## 9. Where to find translated videos and outputs

All processed files are stored under the install base directory:

```
<install_base>\translationService\data\
├─ outputs\        ← translated videos, dubbed audio, subtitle files (.srt, .vtt)
├─ library\        ← completed jobs saved to the library (accessible from the Library tab)
├─ uploads\        ← original uploaded files (temporary, cleaned up after processing)
├─ logs\           ← application log files (see §10)
└─ db\             ← SQLite database (glossary, job history)
```

**Where is `<install_base>`?**

- If you pressed Enter during install (default), it is the project folder itself:
  e.g. `C:\baif_hackathon\translationService\data\`
- If you chose `D:\` during install, it is: `D:\translationService\data\`
- You can also check the value in `backend\.env`:

```powershell
Get-Content .\backend\.env | Select-String "BASE_DIR"
```

From the **Library tab** in the browser you can also download outputs directly without navigating the file system.

---

## 10. Where to find logs

Log files are written to:

```
<install_base>\translationService\data\logs\bhashasetu.log
```

The log file rotates automatically (5 MB per file, 5 files kept).

To tail the live log in PowerShell:
```powershell
Get-Content "<install_base>\translationService\data\logs\bhashasetu.log" -Wait -Tail 50
```

The backend also prints all log output to the PowerShell terminal while it is running.

---

## 11. Starting the app after first install

After the first install you do not need to reinstall. Just run:

```powershell
& .\scripts\install.ps1
```

The script detects the existing install and starts the app immediately without repeating setup.

---

## 12. Configuration reference

All settings are stored in `backend\.env` and can be edited with any text editor.

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `BHASHASETU_BASE_DIR` | *(set by installer)* | Root directory for all data and models. |
| `BHASHASETU_ENABLE_MODELS` | `true` (after `-Live`) | `true` = real AI models, `false` = demo/mock. |
| `BHASHASETU_HF_TOKEN` | *(set in §6)* | HuggingFace token for downloading IndicTrans2 models. |
| `BHASHASETU_OFFLINE` | `false` | `true` = fully offline, no network calls after models are downloaded. |
| `BHASHASETU_DEVICE` | `auto` | `cpu` or `cuda` (GPU). Leave `auto` unless you know you have a CUDA GPU. |
| `BHASHASETU_WHISPER_MODEL` | `small` | Speech recognition model size: `tiny`·`base`·`small`·`medium`. |
| `BHASHASETU_MAX_AUDIO_MB` | `150` | Upload size limit for audio files. |
| `BHASHASETU_MAX_VIDEO_MB` | `200` | Upload size limit for video files. |

---

## 13. Going fully offline (field deployment without internet)

1. Complete the full install (§7) on a machine **with** internet.
2. Confirm the app works and models are downloaded.
3. Edit `backend\.env` and set:
```
BHASHASETU_OFFLINE=true
```
4. Copy the entire project folder (including `translationService\` beside it) to the offline machine.
5. Run `& .\scripts\install.ps1` on the offline machine - it will detect the existing install and start without downloading anything.

---

## 14. Running on a local network (shared access)

To allow other devices on the same Wi-Fi to use BhashaSetu, start it with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Other devices can then open `http://<this-machine-IP>:8000` in their browser.
Find this machine's IP with: `ipconfig` (look for IPv4 Address under the active adapter).

---

## 15. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| Browser shows old UI / plain JSON | Hard-refresh with **Ctrl+F5**. If still wrong, re-run `& .\scripts\install.ps1 -BuildFrontend`. |
| `App is not defined` error in browser | Clear browser cache and hard-refresh (Ctrl+F5). |
| Install asks for HuggingFace token | Set `$env:BHASHASETU_HF_TOKEN` before running the script (§6). |
| Model download fails / 401 error | Token is missing or wrong. Update `BHASHASETU_HF_TOKEN` in `backend\.env` and re-run `& .\scripts\install.ps1 -Live`. |
| `ffmpeg not found` on a media job | Install FFmpeg (§4) or run `winget install Gyan.FFmpeg`. |
| Media job stuck / failed | Check `data\logs\bhashasetu.log` - usually a missing model, re-run with `-Live`. |
| Port 8000 already in use | Another process is using the port. Restart the machine or find and stop the conflicting process. |
| First translation request is slow | Models load into memory on first use (30-60 s). Subsequent requests are fast. |
| Not enough disk space error | Free up space or choose a different drive during install. Minimum 20 GB required. |
| Devanagari text looks wrong in terminal | Cosmetic only - the files and browser display correctly. |

---

## 16. Project layout reference

```
baif_hackathon/
├─ backend/             FastAPI app (API + serves the UI)
│  ├─ app/
│  │  ├─ services/      asr · translate · tts · media · subtitles · glossary · pipeline
│  │  └─ static/        React build output (created automatically by installer)
│  ├─ .env              runtime configuration (written by installer)
│  ├─ requirements.txt  core API dependencies
│  └─ requirements-ml.txt  ML/AI dependencies (live mode)
├─ frontend/            React + Vite + Tailwind source
├─ docs/                ARCHITECTURE · INSTALLATION · MODELS
└─ scripts/             install.ps1 · download_models.py
```

Runtime data (outside the project folder when a separate drive is chosen):
```
translationService\
├─ .venv\               Python virtual environment
├─ models\              downloaded AI model weights
├─ data\
│  ├─ outputs\          translated videos, audio, subtitle files
│  ├─ library\          completed jobs (also accessible in the Library tab)
│  ├─ uploads\          temporary upload storage
│  ├─ logs\             bhashasetu.log (rotating)
│  └─ db\               SQLite database
```

Returns the version, whether models are enabled, the offline flag, the active engines, and which are
loaded - also visible in the UI's **System** tab.

---

## 13. Run as a standalone Windows app (`.exe`)

For field machines that shouldn't need Python installed, BhashaSetu can be packaged into a
self-contained Windows application with [PyInstaller](https://pyinstaller.org/). Two artifacts can
be produced:

| Artifact | Path | What it is |
| -------- | ---- | ---------- |
| **Portable EXE** | `dist\BhashaSetu.exe` | A single double-click file - nothing to install. Copy it anywhere and run. |
| **App folder** | `dist\BhashaSetu\` | The same app as a folder (faster startup). This is what the Setup installer packages. |
| **Setup installer** | `dist\BhashaSetu-Setup-1.0.0.exe` | Friendly installer with Start-Menu + Desktop shortcuts and an uninstaller (built with Inno Setup, §12.4) |

### 12.1 Running the packaged app

Double-click `BhashaSetu.exe` (or the shortcut the installer creates). A small control window
appears, the local server starts on `127.0.0.1`, and your browser opens to the BhashaSetu UI
automatically. Use **Open BhashaSetu** to reopen the tab, and **Quit** (or closing the window) to
stop the server.

> This is the **Lite / demo build**: it bundles the full UI and the complete *text* pipeline in
> **mock mode** (instant, deterministic output with the BAIF glossary applied) - ideal for demos,
> onboarding and UI walkthroughs with zero setup. Real ML output and audio/video need the **Full
> build** (§12.5).

### 12.2 Where the app stores data

The program files are read-only; everything writable is kept **per-user** under
`%LOCALAPPDATA%\BhashaSetu\`:

```
%LOCALAPPDATA%\BhashaSetu\
├─ data\                SQLite db, uploads, outputs, media library, tmp
├─ models\              downloaded models (Full build)
├─ server-url.txt       the local URL the app is currently serving
└─ bhashasetu.log       runtime log - check here first when troubleshooting
```

Deleting that folder fully resets the app. The Setup installer also offers to remove it on uninstall.

### 12.3 Building the EXE yourself

On any machine with **Python 3.10+** (internet is only needed the first time, to fetch PyInstaller):

```powershell
# from the project root
./scripts/build_exe.ps1 -Both       # build BOTH the portable .exe and the app folder
# ...or individually:
./scripts/build_exe.ps1             # app folder only  -> dist\BhashaSetu\
./scripts/build_exe.ps1 -Onefile    # portable file    -> dist\BhashaSetu.exe
./scripts/build_exe.ps1 -Both -Clean # recreate the build venv first
```

The script creates an **isolated build venv** (core deps + PyInstaller only - no ML stack), runs the
bundled spec at `installer\bhashasetu.spec`, and writes the result to `dist\`.

> **Locked-down machine?** If running `.ps1` scripts is blocked by execution policy or Constrained
> Language mode, run the same steps manually:

```powershell
> cd backend
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> pip install "pyinstaller>=6.6,<7"
>
> # app folder build:
> python -m PyInstaller --noconfirm --distpath ..\dist --workpath ..\build\pyinstaller ..\installer\bhashasetu.spec
>
> # portable single-file build:
> $env:BHASHASETU_ONEFILE = "1"
> python -m PyInstaller --noconfirm --distpath ..\dist --workpath ..\build\pyinstaller-onefile ..\installer\bhashasetu.spec
```

### 12.4 Building the Setup installer (`setup.exe`)

To produce a friendly `BhashaSetu-Setup-1.0.0.exe` (Start-Menu + Desktop shortcuts, uninstaller):

1. Build the **app folder** first (`./scripts/build_exe.ps1`), so `dist\BhashaSetu` exists.
2. Install **Inno Setup** (free): <https://jrsoftware.org/isinfo.php> - or `winget install JRSoftware.InnoSetup`.
3. Compile the bundled script:
   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\bhashasetu.iss
   ```
The installer is written to `dist\BhashaSetu-Setup-1.0.0.exe`. It installs **per-user by default**
(no admin required) and offers to remove the data folder on uninstall.

### 12.5 Full build (real ML models + audio/video)

The default packaged app is the small **Lite/demo** build. To package the **full** offline pipeline
(Whisper ASR, IndicTrans2 translation, MMS/Parler TTS, FFmpeg media):

1. Build on a machine **with internet and ample disk** - the result is multi-GB.
2. Use a build venv that also has the ML stack and the models pre-downloaded:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install -r requirements-ml.txt        # PyTorch (CPU), transformers, faster-whisper, …
   python ..\scripts\download_models.py      # pre-fetch models into backend\models\
   ```
3. Edit `installer\bhashasetu.spec` (it has a commented **FULL BUILD** block showing exactly this):
   - Set `excludes = []` (stop excluding the ML libraries).
   - Uncomment the `collect_all(...)` loop so `torch`, `transformers`, `ctranslate2`,
     `sentencepiece`, `tokenizers`, `soundfile` and `numpy` are fully bundled.
   - Drop `ffmpeg.exe` at `installer\bin\ffmpeg.exe` - the spec auto-bundles `installer\bin\` to
     `bin\`, and the launcher adds it to `PATH` at runtime.
   - Optionally bundle the downloaded `models\` folder, or let the app fetch them on first run into
     `%LOCALAPPDATA%\BhashaSetu\models\`.
4. Rebuild exactly as in §12.3. Expect a much larger artifact and a slower first run while models load.

> **Tip:** keep shipping the **Lite** EXE for demos/onboarding and the **Full** build (or a separate
> model pack) for production field machines.

### 12.6 Troubleshooting the packaged app

| Symptom | Fix |
| ------- | --- |
| Window opens but the browser shows an error / nothing | Give it a few seconds on first launch; then read `%LOCALAPPDATA%\BhashaSetu\bhashasetu.log`. |
| App exits immediately | Check `%LOCALAPPDATA%\BhashaSetu\last-crash.log` for the traceback. |
| "Windows protected your PC" (SmartScreen) | The exe is unsigned. Click **More info -> Run anyway**, or code-sign it for wide distribution. |
| Port 8000 busy | The launcher auto-selects the next free port; the actual URL is in `server-url.txt`. |
| Antivirus flags the onefile exe | A known PyInstaller false-positive. Prefer the **app folder** build, or add an exclusion / code-sign it. |