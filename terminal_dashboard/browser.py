"""Open the dashboard URL in the default browser — reuse existing tab when possible."""

from __future__ import annotations

import subprocess
import webbrowser
from typing import Literal, Optional
from urllib.parse import urlparse

from .scripting import applescript_escape, run_applescript

OpenMode = Literal["reuse", "new"]


def open_dashboard(url: str, mode: OpenMode = "reuse") -> dict:
    """
    Open dashboard in a browser.

    mode:
      - reuse: find an existing tab with this host:port and activate it; else open new
      - new: always open a new tab/window
    """
    url = (url or "").strip()
    if not url:
        return {"status": "error", "message": "Empty URL"}

    if mode == "new":
        return _open_new(url)

    # Prefer reuse via AppleScript (Chrome family / Safari / Arc)
    reused = _try_reuse_tab(url)
    if reused.get("status") == "success":
        return reused

    # Fallback: new tab
    result = _open_new(url)
    result["note"] = reused.get("message") or "No existing tab found — opened new"
    return result


def _open_new(url: str) -> dict:
    try:
        # macOS `open` — respects default browser, always new tab in most browsers
        subprocess.run(["open", url], check=False)
        return {"status": "success", "message": f"Opened new browser tab: {url}", "mode": "new"}
    except Exception:
        webbrowser.open(url, new=2)
        return {"status": "success", "message": f"Opened browser: {url}", "mode": "new"}


def _url_parts(url: str) -> tuple:
    p = urlparse(url if "://" in url else f"http://{url}")
    host = (p.hostname or "127.0.0.1").lower()
    if host == "localhost":
        host = "127.0.0.1"
    port = p.port
    if port is None:
        port = 443 if p.scheme == "https" else 80
    # Also match alternate host form
    hosts = {host, "localhost", "127.0.0.1"}
    return hosts, int(port), url


def _try_reuse_tab(url: str) -> dict:
    hosts, port, full = _url_parts(url)
    # Build AppleScript that checks each known browser
    # Match: URL contains host and :port/  or host:port
    host_list = list(hosts)
    # Primary patterns for contains checks
    needles = []
    for h in host_list:
        needles.append(f"{h}:{port}")
        needles.append(f"{h}:{port}/")
    needles_js = ", ".join(f'"{applescript_escape(n)}"' for n in needles)

    # Chrome-like browsers share the same AppleScript dictionary
    chrome_apps = [
        "Google Chrome",
        "Google Chrome Canary",
        "Chromium",
        "Brave Browser",
        "Microsoft Edge",
        "Vivaldi",
        "Opera",
        "Arc",  # Arc supports Chrome-like scripting on many versions
        "Dia",
    ]

    for app_name in chrome_apps:
        if not _app_running(app_name):
            continue
        res = _reuse_chrome_family(app_name, needles)
        if res.get("status") == "success":
            return res

    if _app_running("Safari"):
        res = _reuse_safari(needles)
        if res.get("status") == "success":
            return res

    return {
        "status": "error",
        "message": "No existing dashboard tab found in running browsers",
    }


def _app_running(name: str) -> bool:
    """True if app is running (does not launch it)."""
    # ps-based — no Accessibility needed, does not launch the app
    try:
        out = subprocess.check_output(
            ["ps", "-Ax", "-o", "comm="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        # process name is often last path component, e.g. "Google Chrome"
        names = {line.strip().split("/")[-1] for line in out.splitlines() if line.strip()}
        if name in names:
            return True
        # Chrome helpers: binary may be "Google Chrome"
        for n in names:
            if n == name or n.endswith(name):
                return True
        return False
    except Exception:
        return False


def _reuse_chrome_family(app_name: str, needles: list) -> dict:
    app = applescript_escape(app_name)
    # Build contains checks
    conds = " or ".join(
        f'(tabURL contains "{applescript_escape(n)}")' for n in needles
    )
    script = f'''
    tell application "{app}"
        set targetFound to false
        set winIndex to 0
        set tabIndex to 0
        set wi to 0
        repeat with w in windows
            set wi to wi + 1
            set ti to 0
            repeat with t in tabs of w
                set ti to ti + 1
                try
                    set tabURL to URL of t
                    if {conds} then
                        set targetFound to true
                        set winIndex to wi
                        set tabIndex to ti
                        exit repeat
                    end if
                end try
            end repeat
            if targetFound then exit repeat
        end repeat
        if targetFound then
            activate
            set index of window winIndex to 1
            set active tab index of window 1 to tabIndex
            return "ok"
        end if
        return "miss"
    end tell
    '''
    out = run_applescript(script)
    if out == "ok":
        return {
            "status": "success",
            "message": f"Reused existing tab in {app_name}",
            "mode": "reuse",
            "browser": app_name,
        }
    return {"status": "error", "message": f"No match in {app_name}"}


def _reuse_safari(needles: list) -> dict:
    conds = " or ".join(
        f'(tabURL contains "{applescript_escape(n)}")' for n in needles
    )
    script = f'''
    tell application "Safari"
        set targetFound to false
        set winIndex to 0
        set tabIndex to 0
        set wi to 0
        repeat with w in windows
            set wi to wi + 1
            set ti to 0
            repeat with t in tabs of w
                set ti to ti + 1
                try
                    set tabURL to URL of t
                    if {conds} then
                        set targetFound to true
                        set winIndex to wi
                        set tabIndex to ti
                        exit repeat
                    end if
                end try
            end repeat
            if targetFound then exit repeat
        end repeat
        if targetFound then
            activate
            set index of window winIndex to 1
            set current tab of window 1 to tab tabIndex of window 1
            return "ok"
        end if
        return "miss"
    end tell
    '''
    out = run_applescript(script)
    if out == "ok":
        return {
            "status": "success",
            "message": "Reused existing tab in Safari",
            "mode": "reuse",
            "browser": "Safari",
        }
    return {"status": "error", "message": "No match in Safari"}
