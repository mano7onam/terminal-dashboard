"""Focus / open-directory / open-terminal actions."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional

from . import ides
from .process_utils import app_installed, is_app_running, normalize_path
from .scanners import (
    alacritty,
    ghostty,
    hyper,
    iterm,
    kitty,
    rio,
    tabby,
    terminal_app,
    tmux,
    vscode,
    warp,
    wezterm,
)
from .scripting import applescript_escape, jxa_escape, run_applescript, run_jxa

FOCUS_HANDLERS = {
    "Terminal": terminal_app.focus,
    "iTerm2": iterm.focus,
    "Ghostty": ghostty.focus,
    "Warp": warp.focus,
    "WezTerm": wezterm.focus,
    "Kitty": kitty.focus,
    "Alacritty": alacritty.focus,
    "Hyper": hyper.focus,
    "Tabby": tabby.focus,
    "Rio": rio.focus,
    "VS Code": vscode.focus,
    "Cursor": vscode.focus,
    "Antigravity": vscode.focus,
    "Tmux": tmux.focus,
}


def focus_session(params: Dict[str, Any]) -> Dict[str, Any]:
    app = params.get("app")
    handler = FOCUS_HANDLERS.get(app)
    if not handler:
        return {"status": "error", "message": f"Unknown application type: {app}"}
    try:
        return handler(params)
    except Exception as e:
        return {"status": "error", "message": str(e)}


def pick_folder(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Native macOS folder picker (must show a real GUI dialog).

    Uses NSOpenPanel via JXA first (reliable from background servers),
    then Finder `choose folder` as fallback.
    """
    params = params or {}
    prompt = params.get("prompt") or "Choose a folder for a new terminal"
    default = params.get("default") or os.path.expanduser("~/dev")
    if not os.path.isdir(default):
        default = os.path.expanduser("~")

    # 1) NSOpenPanel — works better when called from a headless Python server
    out = _pick_folder_nsopenpanel(prompt, default)
    if out is not None:
        return out

    # 2) Finder choose folder (bring Finder frontmost)
    out = _pick_folder_finder(prompt, default)
    if out is not None:
        return out

    return {
        "status": "error",
        "message": (
            "Folder picker failed. Grant Automation for osascript/Finder, "
            "or paste the path manually."
        ),
    }


def _pick_folder_nsopenpanel(prompt: str, default: str) -> Optional[Dict[str, Any]]:
    """JXA + AppKit NSOpenPanel (modal, forces UI)."""
    prompt_esc = jxa_escape(prompt)
    default_esc = jxa_escape(default)
    # ObjC bridge — runModal blocks until user picks/cancels
    jxa = f"""
    ObjC.import("AppKit");
    function run() {{
        try {{
            var app = $.NSApplication.sharedApplication;
            app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
            app.activateIgnoringOtherApps(true);

            var panel = $.NSOpenPanel.openPanel;
            panel.setCanChooseFiles(false);
            panel.setCanChooseDirectories(true);
            panel.setAllowsMultipleSelection(false);
            panel.setCanCreateDirectories(true);
            panel.setMessage("{prompt_esc}");
            panel.setPrompt("Select");
            try {{
                var url = $.NSURL.fileURLWithPath("{default_esc}");
                panel.setDirectoryURL(url);
            }} catch (e) {{}}

            // Bring panel to front
            panel.setLevel($.NSModalPanelWindowLevel);
            var result = panel.runModal;
            if (result == $.NSModalResponseOK || result == 1) {{
                var urls = panel.URLs;
                if (urls && urls.count > 0) {{
                    var p = ObjC.unwrap(urls.objectAtIndex(0).path);
                    return "OK:" + p;
                }}
            }}
            if (result == $.NSModalResponseCancel || result == 0) {{
                return "CANCELLED";
            }}
            return "CANCELLED";
        }} catch (e) {{
            return "ERROR:" + String(e);
        }}
    }}
    """
    raw = run_jxa(jxa, timeout=300.0)  # user can take a while
    return _parse_pick_result(raw)


def _pick_folder_finder(prompt: str, default: str) -> Optional[Dict[str, Any]]:
    prompt_esc = applescript_escape(prompt)
    default_esc = applescript_escape(default)
    script = f'''
    try
        tell application "Finder"
            activate
        end tell
        delay 0.15
        tell application "System Events"
            set frontmost of process "Finder" to true
        end tell
        delay 0.1
        set theFolder to choose folder with prompt "{prompt_esc}" default location (POSIX file "{default_esc}")
        return "OK:" & (POSIX path of theFolder)
    on error number -128
        return "CANCELLED"
    on error errMsg number errNum
        return "ERROR:" & errNum & ":" & errMsg
    end try
    '''
    raw = run_applescript(script, timeout=300.0)
    return _parse_pick_result(raw)


def _parse_pick_result(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    raw = raw.strip()
    if raw == "CANCELLED" or raw == "":
        return {"status": "cancelled", "message": "Cancelled"}
    if raw.startswith("ERROR:"):
        # Let caller try next strategy unless it's a hard cancel
        err = raw[6:]
        # -1719 / not allowed assistive access etc.
        if "not allowed" in err.lower() or "assistive" in err.lower():
            return {
                "status": "error",
                "message": (
                    "macOS blocked the folder dialog (Automation/Accessibility). "
                    "Paste the path manually, or allow osascript in "
                    "System Settings → Privacy & Security → Automation."
                ),
            }
        return None  # try fallback
    if raw.startswith("OK:"):
        path = raw[3:].strip().rstrip("/")
        path = normalize_path(path) or path
        if path and os.path.isdir(path):
            return {"status": "success", "path": path}
        return {"status": "error", "message": f"Not a directory: {path}"}
    # Bare path (older scripts)
    if raw.startswith("/") and os.path.isdir(raw.rstrip("/")):
        path = normalize_path(raw.rstrip("/")) or raw.rstrip("/")
        return {"status": "success", "path": path}
    return None


def open_directory(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    params:
      path: directory
      action: finder | vscode | terminal
      app: auto | ghostty | terminal | iterm | warp  (for action=terminal)
      mode: tab | window  (for Ghostty / iTerm; Terminal.app always window)
    """
    action = params.get("action")
    path = params.get("path")
    path = normalize_path(path) if path else None

    if action == "pick_folder":
        return pick_folder(params)

    if not path or path == "Unknown/Remote" or not os.path.isdir(path):
        return {"status": "error", "message": "Invalid directory path"}

    if action == "finder":
        try:
            subprocess.run(["open", path], check=True)
            return {"status": "success", "message": f"Opened {path} in Finder"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    if action == "vscode":
        # Back-compat: prefer VS Code, else any available IDE
        res = ides.open_in_ide(path, "vscode")
        if res.get("status") == "success":
            return res
        available = ides.list_available_ides()
        if available:
            return ides.open_in_ide(path, available[0]["id"])
        return res

    if action == "ide":
        ide_id = params.get("ide") or params.get("ide_id") or "vscode"
        return ides.open_in_ide(path, ide_id)

    if action == "terminal":
        app = (params.get("app") or "auto").lower().strip()
        mode = (params.get("mode") or "window").lower().strip()
        if mode not in ("tab", "window"):
            mode = "window"
        return open_terminal_in_path(path, app=app, mode=mode)

    return {"status": "error", "message": "Unknown action type"}


def _resolve_terminal_app(app: str) -> str:
    """Return one of: ghostty, terminal, iterm, warp."""
    app = (app or "auto").lower()
    if app in ("ghostty", "terminal", "iterm", "iterm2", "warp"):
        if app == "iterm2":
            return "iterm"
        return app

    # auto: prefer running app, else installed, else Terminal.app
    if is_app_running([r"[/ ]ghostty$", r"/Ghostty\.app/"]):
        return "ghostty"
    if is_app_running([r"/iTerm2?\.app/"]):
        return "iterm"
    if is_app_running([r"/Warp\.app/"]):
        return "warp"
    if is_app_running([r"/Terminal\.app/"]):
        return "terminal"

    if app_installed(["Ghostty"]):
        return "ghostty"
    if app_installed(["iTerm", "iTerm2"]):
        return "iterm"
    if app_installed(["Warp"]):
        return "warp"
    return "terminal"


def open_terminal_in_path(
    path: str,
    *,
    app: str = "auto",
    mode: str = "window",
) -> Dict[str, Any]:
    """Open Ghostty / Terminal.app / iTerm / Warp in the given directory."""
    path = normalize_path(path) if path else None
    if not path or not os.path.isdir(path):
        return {"status": "error", "message": "Invalid directory path"}

    resolved = _resolve_terminal_app(app)

    if resolved == "ghostty":
        return _open_ghostty(path, mode=mode)
    if resolved == "iterm":
        return _open_iterm(path, mode=mode)
    if resolved == "warp":
        return _open_warp(path)
    return _open_terminal_app(path)


def _open_ghostty(path: str, *, mode: str = "window") -> Dict[str, Any]:
    # Delegate to scanner helper (avoids creating tabs inside a fullscreen front window)
    try:
        res = ghostty.open_in_dir(path, mode=mode)
        if res.get("status") == "success":
            res["app"] = "Ghostty"
            res["path"] = path
            res["mode"] = mode
        return res
    except TypeError:
        # older signature
        res = ghostty.open_in_dir(path)
        res["app"] = "Ghostty"
        res["path"] = path
        return res
    except Exception as e:
        try:
            subprocess.run(["open", "-a", "Ghostty", path], check=False)
            return {
                "status": "success",
                "message": f"Launched Ghostty (cwd may need manual cd: {path})",
                "app": "Ghostty",
                "path": path,
            }
        except Exception:
            return {"status": "error", "message": f"Failed to open Ghostty: {e}"}


def _open_terminal_app(path: str) -> Dict[str, Any]:
    # doScript always creates a new window
    jxa = f"""
    function run() {{
        var app = Application("Terminal");
        app.activate();
        app.doScript("cd " + {json.dumps(path)} + " && clear");
        return "ok";
    }}
    """
    out = run_jxa(jxa)
    if out is None:
        try:
            subprocess.run(["open", "-a", "Terminal", path], check=True)
            return {
                "status": "success",
                "message": f"Opened Terminal.app for {path}",
                "app": "Terminal",
                "path": path,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {
        "status": "success",
        "message": f"Opened Terminal.app window in {path}",
        "app": "Terminal",
        "path": path,
        "mode": "window",
    }


def _open_iterm(path: str, *, mode: str = "window") -> Dict[str, Any]:
    if mode == "tab":
        jxa = f"""
        function run() {{
            var app = Application("iTerm");
            app.activate();
            var win = app.currentWindow();
            if (!win) win = app.createWindowWithDefaultProfile();
            var tab = win.createTabWithDefaultProfile();
            try {{ tab.currentSession().write({{text: "cd " + {json.dumps(path)} + " && clear"}}); }} catch (e) {{}}
            return "ok";
        }}
        """
        label = "tab"
    else:
        jxa = f"""
        function run() {{
            var app = Application("iTerm");
            app.activate();
            var win = app.createWindowWithDefaultProfile();
            try {{ win.currentSession().write({{text: "cd " + {json.dumps(path)} + " && clear"}}); }} catch (e) {{}}
            return "ok";
        }}
        """
        label = "window"
    out = run_jxa(jxa)
    if out is None:
        return {"status": "error", "message": "Failed to open iTerm2"}
    return {
        "status": "success",
        "message": f"Opened iTerm2 {label} in {path}",
        "app": "iTerm2",
        "path": path,
        "mode": mode,
    }


def _open_warp(path: str) -> Dict[str, Any]:
    try:
        subprocess.run(["open", "-a", "Warp", path], check=False)
        return {
            "status": "success",
            "message": f"Opened Warp for {path}",
            "app": "Warp",
            "path": path,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
