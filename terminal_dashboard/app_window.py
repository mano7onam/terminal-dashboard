"""Open the dashboard in a native macOS WKWebView window (no browser tab)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_NATIVE = os.path.join(_ROOT, "native")
_BIN_DIR = os.path.join(_ROOT, "dist", "bin")
_HELPER_NAME = "TerminalDashboardWebView"


def open_app_window(url: str) -> dict:
    """
    Launch a native WebView window pointed at ``url``.

    Uses a small Swift helper (compiled on first use if needed).
    """
    if sys.platform != "darwin":
        return {"status": "error", "message": "Native app window is macOS-only"}

    helper = _ensure_helper()
    if not helper:
        return {
            "status": "error",
            "message": "Could not build WebView helper (need Xcode CLT / swiftc)",
        }

    try:
        subprocess.Popen(
            [helper, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"status": "success", "message": f"Opened app window: {url}", "mode": "app"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _ensure_helper() -> Optional[str]:
    os.makedirs(_BIN_DIR, exist_ok=True)
    dest = os.path.join(_BIN_DIR, _HELPER_NAME)
    src = os.path.join(_NATIVE, "StandaloneWebView.swift")
    if not os.path.isfile(src):
        return None

    # Rebuild if missing or source newer
    need_build = not os.path.isfile(dest)
    if not need_build:
        try:
            need_build = os.path.getmtime(src) > os.path.getmtime(dest)
        except OSError:
            need_build = True

    if need_build:
        swiftc = shutil.which("swiftc")
        if not swiftc:
            return dest if os.path.isfile(dest) else None
        cmd = [
            swiftc,
            "-O",
            "-framework",
            "WebKit",
            "-framework",
            "Cocoa",
            src,
            "-o",
            dest,
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=120,
            )
            os.chmod(dest, 0o755)
        except Exception:
            if os.path.isfile(dest):
                return dest
            return None

    return dest if os.path.isfile(dest) and os.access(dest, os.X_OK) else None
