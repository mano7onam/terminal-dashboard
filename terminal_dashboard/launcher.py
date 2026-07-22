#!/usr/bin/env python3
"""
Desktop launcher for Terminal Dashboard.

Starts the local HTTP server and shows a small status window so the app
stays visible in the Dock (not “browser-only”).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

# Ensure package imports work when frozen inside .app/Resources/app
_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_ROOT = os.path.dirname(_HERE)
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)


def _find_free_port(preferred: int = 8080) -> int:
    # Prefer 8080 if free
    for port in (preferred, 0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", port if port else 0))
            chosen = s.getsockname()[1]
            s.close()
            return chosen
        except OSError:
            continue
    return preferred


def _static_dir() -> str:
    # Inside .app: Resources/app has index.html next to terminal_dashboard/
    candidates = [
        _APP_ROOT,
        os.path.dirname(_APP_ROOT),
        os.getcwd(),
    ]
    for c in candidates:
        if os.path.isfile(os.path.join(c, "index.html")):
            return c
    return _APP_ROOT


def main() -> None:
    port = int(os.environ.get("TERMINAL_DASHBOARD_PORT", "8080") or "8080")
    port = _find_free_port(port)
    static = _static_dir()
    url = f"http://127.0.0.1:{port}"

    from terminal_dashboard.httpd import create_server
    from terminal_dashboard.version import APP_NAME, __version__

    httpd = create_server(port=port, static_dir=static)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    # Wait until healthy
    import urllib.request

    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=0.3) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.08)

    # Default: native app window (WKWebView). Browser is optional.
    prefer_browser = os.environ.get("TERMINAL_DASHBOARD_BROWSER", "").strip() in (
        "1",
        "true",
        "yes",
        "browser",
    )
    if prefer_browser:
        try:
            from terminal_dashboard.browser import open_dashboard

            open_dashboard(url, mode="reuse")
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                pass
    else:
        try:
            from terminal_dashboard.app_window import open_app_window

            res = open_app_window(url)
            if res.get("status") != "success":
                raise RuntimeError(res.get("message") or "webview failed")
        except Exception:
            try:
                from terminal_dashboard.browser import open_dashboard

                open_dashboard(url, mode="reuse")
            except Exception:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass

    # Compact status tray (server host) — optional tk window
    try:
        import tkinter as tk
        from tkinter import font as tkfont
    except Exception as e:
        print(f"tkinter unavailable ({e}); server running at {url}", flush=True)
        print("Press Ctrl+C to quit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            httpd.shutdown()
        return

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("400x240")
    root.resizable(False, False)
    root.configure(bg="#0f172a")

    # Try to set window icon if .png exists
    icon_candidates = [
        os.path.join(static, "assets", "AppIcon-1024.png"),
        os.path.join(os.path.dirname(static), "assets", "AppIcon-1024.png"),
        os.path.join(_APP_ROOT, "assets", "AppIcon-1024.png"),
    ]
    for ic in icon_candidates:
        if os.path.isfile(ic):
            try:
                img = tk.PhotoImage(file=ic)
                root.iconphoto(True, img)
                root._icon_ref = img  # noqa: keep ref
            except Exception:
                pass
            break

    title_font = tkfont.Font(family="Helvetica", size=16, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=11)
    mono = tkfont.Font(family="Menlo", size=10)

    tk.Label(
        root, text=APP_NAME, font=title_font,
        fg="#e0e7ff", bg="#0f172a",
    ).pack(pady=(22, 4))

    tk.Label(
        root, text=f"v{__version__}  ·  local server running",
        font=body_font, fg="#94a3b8", bg="#0f172a",
    ).pack()

    status = tk.Label(
        root, text=url, font=mono, fg="#a5b4fc", bg="#0f172a",
        cursor="hand2",
    )
    status.pack(pady=(10, 6))

    btn_row = tk.Frame(root, bg="#0f172a")
    btn_row.pack(pady=12)

    def open_app() -> None:
        try:
            from terminal_dashboard.app_window import open_app_window

            open_app_window(url)
        except Exception:
            open_dash()

    def open_dash() -> None:
        try:
            from terminal_dashboard.browser import open_dashboard
            open_dashboard(url, mode="reuse")
        except Exception:
            webbrowser.open(url)

    def open_dash_new() -> None:
        try:
            from terminal_dashboard.browser import open_dashboard
            open_dashboard(url, mode="new")
        except Exception:
            webbrowser.open(url, new=2)

    def quit_app() -> None:
        try:
            httpd.shutdown()
        except Exception:
            pass
        root.destroy()
        os._exit(0)

    open_btn = tk.Button(
        btn_row, text="App window", command=open_app,
        font=body_font, fg="#0f172a", bg="#818cf8",
        activebackground="#a5b4fc", relief="flat",
        padx=10, pady=8, cursor="hand2",
    )
    open_btn.pack(side="left", padx=4)

    open_browser_btn = tk.Button(
        btn_row, text="Browser tab", command=open_dash,
        font=body_font, fg="#e2e8f0", bg="#334155",
        activebackground="#475569", relief="flat",
        padx=10, pady=8, cursor="hand2",
    )
    open_browser_btn.pack(side="left", padx=4)

    open_new_btn = tk.Button(
        btn_row, text="New tab", command=open_dash_new,
        font=body_font, fg="#e2e8f0", bg="#334155",
        activebackground="#475569", relief="flat",
        padx=10, pady=8, cursor="hand2",
    )
    open_new_btn.pack(side="left", padx=4)

    quit_btn = tk.Button(
        btn_row, text="Quit", command=quit_app,
        font=body_font, fg="#e2e8f0", bg="#1e293b",
        activebackground="#334155", relief="flat",
        padx=10, pady=8, cursor="hand2",
    )
    quit_btn.pack(side="left", padx=4)

    status.bind("<Button-1>", lambda _e: open_app())

    tk.Label(
        root,
        text="Default UI: native app window (WebView).\n"
        "Optional: open in a browser tab. Quit here to stop the server.",
        font=tkfont.Font(family="Helvetica", size=9),
        fg="#64748b", bg="#0f172a", justify="center",
    ).pack(pady=(4, 10))

    root.protocol("WM_DELETE_WINDOW", quit_app)

    # Do NOT force topmost / focus repeatedly — that fights the browser & terminals.
    try:
        root.lift()
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
