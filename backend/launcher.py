"""
BhashaSetu - Windows desktop launcher (PyInstaller entry point).

Boots the FastAPI/uvicorn server on a free local port, opens the default browser
at the app, and shows a small control window so non-technical users can re-open
the app or quit cleanly.

Runtime data (SQLite db, uploads, outputs, model cache) is written to
`%LOCALAPPDATA%\BhashaSetu` so the install directory stays read-only and no
administrator rights are required.
"""
from __future__ import annotations

import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_NAME = "BhashaSetu"
HOST = "127.0.0.1"
PREFERRED_PORT = 8000
_FONT = "Segoe UI"


def _writable_root() -> Path:
    """Per-user writable data directory (works for portable and installed runs)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    root = Path(base) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _redirect_std_streams() -> None:
    """Give the process real output streams.

    A windowed PyInstaller build (console=False) has `sys.stdout` and
    `sys.stderr` set to `None`; uvicorn's logging then raises on startup and
    kills the server thread. Point both at a log file, which also doubles as a
    diagnostics trail.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        stream = open(_writable_root() / "bhashasetu.log", "a", buffering=1, encoding="utf-8")
    except Exception:  # noqa: BLE001 - fall back to a black hole
        import io

        stream = io.StringIO()
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _find_free_port(host: str, preferred: int) -> int:
    """Return `preferred` if free, otherwise the next available port."""
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((host, port)) != 0:  # nothing listening -> free
                return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def _configure_environment() -> None:
    """Point the app at writable, per-user storage *before* it is imported."""
    root = _writable_root()
    data_dir = root / "data"
    models_dir = root / "models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("BHASHASETU_DATA_DIR", str(data_dir))
    os.environ.setdefault("BHASHASETU_MODELS_DIR", str(models_dir))
    os.environ.setdefault("HF_HOME", str(models_dir))
    os.environ.setdefault("BHASHASETU_HOST", HOST)

    # Make a bundled FFmpeg (a `bin/ffmpeg.exe` next to the resources or exe)
    # discoverable for the media pipeline, if one was shipped.
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    exe_dir = Path(sys.executable).resolve().parent
    for candidate in (bundle_root / "bin", exe_dir / "bin"):
        if (candidate / "ffmpeg.exe").exists():
            os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")
            break


def _open_when_ready(url: str, health_url: str) -> None:
    """Poll the health endpoint, then open the app in the default browser."""
    import urllib.request

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1) as resp:  # noqa: S310
                if resp.status == 200:
                    break
        except Exception:  # noqa: BLE001 - server still starting
            time.sleep(0.4)
    webbrowser.open(url)


def _build_server(port: int):
    """Create the uvicorn server (app imported lazily, after env is configured)."""
    import uvicorn

    from app.main import app

    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        log_level="info",
        access_log=False,
        workers=1,
    )
    return uvicorn.Server(config)


def _serve(server) -> None:
    """Run the server, recording any fatal error (the thread can't propagate it)."""
    try:
        server.run()
    except Exception:  # noqa: BLE001 - capture so failures are diagnosable
        import traceback

        traceback.print_exc()
        try:
            (_writable_root() / "last-crash.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except Exception:
            pass


def _run_control_window(url: str, server) -> None:
    """Show a tiny always-available control window; fall back to a console wait."""
    try:
        import tkinter as tk
    except Exception:  # noqa: BLE001 - headless / no Tk available
        _run_console(url, server)
        return

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("400x190")
    root.resizable(False, False)
    root.configure(bg="#0f1d17")

    def _quit() -> None:
        server.should_exit = True
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _quit)

    tk.Label(
        root, text="भाषासेतु · BhashaSetu", fg="#f4b740", bg="#0f1d17",
        font=(_FONT, 15, "bold"),
    ).pack(pady=(22, 2))
    tk.Label(
        root, text="is running", fg="#e7efe9", bg="#0f1d17", font=(_FONT, 10),
    ).pack()
    tk.Label(
        root, text=url, fg="#5fd08a", bg="#0f1d17", font=("Consolas", 10),
    ).pack(pady=(8, 2))
    tk.Label(
        root, text="Keep this window open while you use the app.",
        fg="#9bb0a4", bg="#0f1d17", font=(_FONT, 8),
    ).pack(pady=(2, 12))

    btns = tk.Frame(root, bg="#0f1d17")
    btns.pack()
    tk.Button(
        btns, text="Open BhashaSetu", width=18, relief="flat",
        bg="#1a6b3f", fg="white", activebackground="#22824f", cursor="hand2",
        command=lambda: webbrowser.open(url),
    ).grid(row=0, column=0, padx=6)
    tk.Button(
        btns, text="Quit", width=10, relief="flat",
        bg="#3a2a2a", fg="#f0d9d9", cursor="hand2", command=_quit,
    ).grid(row=0, column=1, padx=6)

    root.mainloop()


def _run_console(url: str, server) -> None:
    print(f"\n  {APP_NAME} is running at {url}")
    print("  Press Ctrl+C to quit.\n")
    try:
        while not server.should_exit:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def main() -> int:
    multiprocessing.freeze_support()
    _redirect_std_streams()
    _configure_environment()

    port = _find_free_port(HOST, int(os.environ.get("BHASHASETU_PORT", PREFERRED_PORT)))
    os.environ["BHASHASETU_PORT"] = str(port)

    url = f"http://{HOST}:{port}/"
    health_url = f"http://{HOST}:{port}/api/health"

    # Record the live URL so users (or IT support) can always find the app,
    # even if the browser fails to open automatically.
    try:
        (_writable_root() / "server-url.txt").write_text(url, encoding="utf-8")
    except Exception:  # noqa: BLE001 - best effort
        pass

    server = _build_server(port)
    server_thread = threading.Thread(target=_serve, args=(server,), name="uvicorn", daemon=True)
    server_thread.start()

    threading.Thread(
        target=_open_when_ready, args=(url, health_url), daemon=True,
    ).start()

    _run_control_window(url, server)

    server.should_exit = True
    server_thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - last-resort crash log for the windowed exe
        import traceback

        try:
            (_writable_root() / "last-crash.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except Exception:
            pass
        raise