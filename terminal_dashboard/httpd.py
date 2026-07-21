"""HTTP server for the dashboard UI + JSON API."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import actions, ides
from .browser import open_dashboard
from .export import export_transcript, list_export_sources
from .preview import get_preview
from .scanners import detected_apps, scan_all
from .version import APP_NAME, DESCRIPTION, __version__

DEFAULT_PORT = 8080


class DashboardHandler(SimpleHTTPRequestHandler):
    # Directory that contains index.html
    static_dir: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.static_dir, **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        path = args[0] if args else ""
        if isinstance(path, str) and ("/api/terminals" in path or "GET / " in path):
            return
        super().log_message(fmt, *args)

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/terminals":
            try:
                self._json(scan_all())
            except Exception as e:
                print(f"scan error: {e}", file=sys.stderr)
                self._json({"error": str(e)}, status=500)
            return
        if url.path == "/api/health":
            apps = detected_apps()
            self._json({
                "status": "ok",
                "name": APP_NAME,
                "version": __version__,
                "description": DESCRIPTION,
                "platform": sys.platform,
                "apps": apps,
                "ides": ides.list_available_ides(),
            })
            return
        if url.path == "/api/ides":
            self._json({"ides": ides.list_available_ides()})
            return
        if url.path in ("/", "/index.html"):
            # Always serve fresh UI (avoid stale Export/IDE buttons after updates)
            try:
                index_path = os.path.join(self.static_dir or DashboardHandler.static_dir, "index.html")
                with open(index_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                print(f"index serve error: {e}", file=sys.stderr)
                self.send_error(500, str(e))
            return
        return super().do_GET()

    def do_POST(self) -> None:
        url = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            params = json.loads(raw)
        except Exception:
            params = {}

        try:
            if url.path == "/api/focus":
                self._json(actions.focus_session(params))
            elif url.path == "/api/open_dir":
                self._json(actions.open_directory(params))
            elif url.path == "/api/pick_folder":
                self._json(actions.pick_folder(params))
            elif url.path == "/api/open_terminal":
                # Convenience alias: { path, app, mode }
                path = params.get("path")
                app = params.get("app") or "auto"
                mode = params.get("mode") or "window"
                self._json(actions.open_directory({
                    "path": path,
                    "action": "terminal",
                    "app": app,
                    "mode": mode,
                }))
            elif url.path == "/api/export":
                self._json(export_transcript(params))
            elif url.path == "/api/export/sources":
                session = params.get("session") or params
                self._json(list_export_sources(session))
            elif url.path == "/api/preview":
                session = params.get("session") or params
                want_shot = params.get("screenshot", True)
                if isinstance(want_shot, str):
                    want_shot = want_shot.lower() not in ("0", "false", "no")
                # Default FALSE — focusing for screenshots causes terminal/browser thrashing
                allow_focus = params.get("allow_focus", False)
                if isinstance(allow_focus, str):
                    allow_focus = allow_focus.lower() in ("1", "true", "yes")
                self._json(get_preview(
                    session,
                    want_screenshot=bool(want_shot),
                    allow_focus_for_shot=bool(allow_focus),
                ))
            elif url.path == "/api/open_browser":
                # { url?, mode: "reuse"|"new" } — url optional; default this server
                mode = (params.get("mode") or "reuse").lower()
                if mode not in ("reuse", "new"):
                    mode = "reuse"
                dash_url = params.get("url")
                if not dash_url:
                    host = self.headers.get("Host") or f"127.0.0.1:{DEFAULT_PORT}"
                    # Prefer host from request so port is correct
                    dash_url = f"http://{host}/"
                self._json(open_dashboard(dash_url, mode=mode))  # type: ignore[arg-type]
            else:
                self._json({"status": "error", "message": "Not Found"}, status=404)
        except Exception as e:
            print(f"POST {url.path} error: {e}", file=sys.stderr)
            self._json({"status": "error", "message": str(e)}, status=500)


def create_server(port: int = DEFAULT_PORT, static_dir: str | None = None) -> ThreadingHTTPServer:
    """Create (but do not serve) the dashboard HTTP server."""
    if static_dir is None:
        static_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_dir = os.path.abspath(static_dir)
    if not os.path.isfile(os.path.join(static_dir, "index.html")):
        raise FileNotFoundError(f"index.html not found in {static_dir}")

    DashboardHandler.static_dir = static_dir
    ThreadingHTTPServer.allow_reuse_address = True
    try:
        return ThreadingHTTPServer(("", port), DashboardHandler)
    except OSError as e:
        raise OSError(f"cannot bind to port {port}: {e}") from e


def run_server(port: int = DEFAULT_PORT, static_dir: str | None = None) -> None:
    try:
        httpd = create_server(port=port, static_dir=static_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        print("hint: stop the other process or run with --port 8081", file=sys.stderr)
        sys.exit(1)

    print(f"=== {APP_NAME} v{__version__} ===")
    print(f"Open  http://localhost:{port}")
    print(f"API   http://localhost:{port}/api/terminals")
    print(f"Health http://localhost:{port}/api/health")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.server_close()
        sys.exit(0)
