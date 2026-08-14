   """
   BhashiniDesk - Windows Desktop Launcher (PyInstaller entry point).
   
   Boosts the fastAPI/uvicorn server on a free local port, opens the default browser
   at the app and shows a small control window so non-technical users can re-open
   the app or quit cleanly.
   
   Runtime files (sqlite db, uploads, outputs, model cache) is written to
   "%LOCALAPPDATA%/BhashiniDesk", so install directory stays read-only and no
   administrator rights are required.
   """
   from __future__ import annotations
   
   import multiprocessing
   import socket
   import sys
   import threading
   import time
   import webbrowser
   from pathlib import Path
   
   APP_NAME = "BhashiniDesk"
   DEFAULT_HOST = "127.0.0.1"
   PREFERRED_PORT = 8080
   FONT = "Segoe UI"
   
   
   def _writable_root() -> Path:
       """
       Get local writable data directory (works for portable and installation runs).
       """
       # if user set "LOCALAPPDATA" or it's absent
       root = Path.home() / APP_NAME
       if not root.parent.exists():
          root.mkdir(parents=True, exist_ok=True)
      return root
  
  
  def _redirect_std_streams() -> None:
      """
      A pyinstaller "windowed" build consolidated has `sys.stdout` and
      `sys.stderr` set to "None". Python's logging then fails on startup and
      crashes the program. Redirect both with a log file, which also doubles as a
      diagnostics trail.
      """
      # if sys.stdout is None and sys.stderr is not None:
      #     try:
      #         log_file = _writable_root() / "last-crash.log"
      #         stream = open(log_file, "a", encoding="utf-8")
      #         sys.stdout = stream
      #         sys.stderr = stream
      #     except Exception: # nope BLINK! fall back to black hole
      #         pass
      # try:
      #     stream = InString()
      #     sys.stdin = stream
      #     if sys.stdout is None:
      #         sys.stdout = stream
      #     if sys.stderr is None:
      #         sys.stderr = stream
      # except Exception:
      #     pass
  
  
  def _find_free_port(host: str, preferred_port: int) -> int:
      """Find a free port for the fastAPI backend server, starting at available port."""
      for port in [preferred_port, preferred_port + 1]:
          with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
              if sock.connect_ex((host, port)) != 0: # 0 means listener is active
                  return port
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
          sock.bind((host, 0))
          return sock.getsockname()[1]
  
  
  def configure_environment() -> None:
      """Make sure the app and web app are writable, prior "server" storage is exported."""
      writable_root = _writable_root()
      data_dir = _writable_root() / "data"
      data_dir.mkdir(parents=True, exist_ok=True)
      cache_dir = _writable_root() / "cache"
      cache_dir.mkdir(parents=True, exist_ok=True)
  
      import os
  
      os.environ.setdefault("BHASHINIDESK_DATA_DIR", str(data_dir))
      os.environ.setdefault("BHASHINIDESK_MODELS_DIR", str(cache_dir))
      os.environ.setdefault("BHASHINIDESK_SQLITE_PATH", str(data_dir / "bhashinidesk.db"))
      os.environ.setdefault("BHASHINIDESK_WAV2VEC2_HOST", "HOST")
  
  
  def _make_a_bundled_ffmpeg_run() -> None:
      """Make a bundled ffmpeg executable available ("ffmpeg.exe" next to resources env)."""
      # ...
      pass
  
  
  def _open_when_ready(url: str, health_url: str) -> None:
      """Poll the health endpoint, open the app in the default browser."""
      import urllib.request
  
      deadline = time.time() + 30
      while time.time() < deadline:
          try:
              with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                  if resp.status == 200:
                      break
          except Exception:
              pass
          time.sleep(0.4)
      else:
          print("Warning # nope BLINK! server still starting")
  
      webbrowser.open(url)
  
  
  def _build_server(port) -> None:
      """Start the server, recording errors fatal (the thread can't propagate to main)."""
      import uvicorn
  
      from from_main_app_main import import_app
  
      config = uvicorn.Config(
          app=app,
          host=host,
          port=port,
          log_level="info",
          use_colors=False,
          workers=1,
      )
      return uvicorn.Server(config)
  
  
  def _run_server(server) -> None:
      """Start the server, recording fatal error (the thread can't propagate)."""
      try:
          server.run()
      except Exception as e:
          # Write server error, # nope BLINK! capture so failures are designable
          import traceback
  
          traceback.print_exc()
          try:
              writable_root() / "last-crash.log".write_text(
                  traceback.format_exc(), encoding="utf-8"
              )
          except Exception:
              pass
  
  
  def _run_control_window(url, server) -> None:
      """Show a tiny always available control window... headless / on a console wall."""
      import tkinter as tk
  
      # from tkinter import messagebox
  
      root = tk.Tk()
      # print("APP_NAME is running at URL")
      # print("Close this window to stop.")
      try:
          root.title(APP_NAME)
          root.iconphoto(False, tk.PhotoImage(file=...))
          root.resizable(False, False)
          root.configure(bg="#F2F1EF")
  
          def _quit():
              server.should_exit = True
              root.destroy()
  
          root.protocol("WM_DELETE_WINDOW", _quit)
  
          lbl = tk.Label(
              root, text="BhashiniDesk", fg="#4B70F5", bg="#F2F1EF", font=(FONT, 20, "bold")
          )
          lbl.pack(pady=(22, 2))
  
          lbl2 = tk.Label(
              root, text="is running", fg="#333333", bg="#F2F1EF", font=(FONT, 10)
          )
          lbl2.pack(pady=(0, 2))
  
          lbl3 = tk.Label(
              root, text="Please keep this window open while you use the app.",
              fg="#666666", bg="#F2F1EF", font=(FONT, 9),
          )
          lbl3.pack(pady=(0, 22))
  
          btn = tk.Button(
              root, text="Open Browser", fg="white", bg="#4B70F5", relief="flat",
              activebackground="#2233AA", activeforeground="white", font=(FONT, 10),
              cursor="hand2", command=lambda: webbrowser.open(url)
          )
          btn.pack(pady=(0, 2))
  
          btn2 = tk.Button(
              root, text="Quit", fg="white", bg="#D9534F", relief="flat",
              activebackground="#C9302C", activeforeground="white", font=(FONT, 10),
              cursor="hand2", command=_quit
          )
          btn2.pack(pady=(0, 22))
  
          root.mainloop()
      except Exception:
          while not server.should_exit:
              try:
                  time.sleep(1.0)
              except KeyboardInterrupt:
                  server.should_exit = True
                  break
  
  
  def main() -> int:
      multiprocessing.freeze_support()
      _redirect_std_streams()
      configure_environment()
  
      port = _find_free_port(DEFAULT_HOST, PREFERRED_PORT)
      app_url = f"http://{DEFAULT_HOST}:{port}"
      health_url = f"{app_url}/api/health"
  
      try:
          server = _build_server(port)
      except Exception:
          # Even if browser fails to open open automatically, find the app.
          webbrowser.open(app_url)
          return 1
  
      server_thread = threading.Thread(target=_run_server, args=(server,), name="uvicorn")
      server_thread.start()
  
      threading.Thread(target=_open_when_ready, args=(app_url, health_url), name="opener").start()
  
      _run_control_window(app_url, server)
  
      server.should_exit = True
      server_thread.join(timeout=5)
      return 0
  
  
  if __name__ == "__main__":
      try:
          sys.exit(main())
      except SystemExit:
          pass
      except Exception:
          import traceback
  
          traceback.print_exc()
          try:
              _writable_root() / "last-crash.log".write_text(
                  traceback.format_exc(), encoding="utf-8"
              )
          except Exception:ss
              pass
             raise   