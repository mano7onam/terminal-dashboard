"""Terminal scanners — each returns a list of session dicts."""

from __future__ import annotations

from typing import Callable, Dict, List

from . import alacritty, ghostty, hyper, iterm, kitty, rio, tabby, terminal_app, tmux, warp, wezterm
from . import vscode

# Order is presentation priority for docs / health endpoint
SCANNERS: List[tuple[str, Callable[[], List[dict]]]] = [
    ("Terminal", terminal_app.scan),
    ("iTerm2", iterm.scan),
    ("Ghostty", ghostty.scan),
    ("Warp", warp.scan),
    ("WezTerm", wezterm.scan),
    ("Kitty", kitty.scan),
    ("Alacritty", alacritty.scan),
    ("Hyper", hyper.scan),
    ("Tabby", tabby.scan),
    ("Rio", rio.scan),
    ("VS Code", vscode.scan),
    ("Tmux", tmux.scan),
]


def scan_all() -> List[dict]:
    from ..models import finalize_session
    from ..process_utils import clear_process_cache

    clear_process_cache()
    sessions: List[dict] = []
    for _name, fn in SCANNERS:
        try:
            found = fn() or []
            for s in found:
                sessions.append(finalize_session(s))
        except Exception as e:
            # One broken scanner must not kill the whole dashboard
            print(f"Scanner {_name} failed: {e}")
    return sessions


def detected_apps() -> Dict[str, dict]:
    """Which backends are available / running (for /api/health)."""
    from ..process_utils import app_installed, is_app_running, which

    specs = {
        "Terminal": {
            "installed": app_installed(["Terminal"]) or True,  # always on macOS
            "running": is_app_running([r"/Terminal\.app/"]),
            "focus": "native (AppleScript)",
        },
        "iTerm2": {
            "installed": app_installed(["iTerm", "iTerm2"]),
            "running": is_app_running([r"/iTerm2?\.app/"]),
            "focus": "native (AppleScript)",
        },
        "Ghostty": {
            "installed": app_installed(["Ghostty"]),
            "running": is_app_running([r"[/ ]ghostty$", r"/Ghostty\.app/"]),
            "focus": "native (AppleScript focus by terminal id)",
        },
        "Warp": {
            "installed": app_installed(["Warp"]),
            "running": is_app_running([r"/Warp\.app/", r"\bstable\b.*Warp"]),
            "focus": "best-effort (activate + window title)",
        },
        "WezTerm": {
            "installed": bool(which("wezterm")) or app_installed(["WezTerm", "wezterm"]),
            "running": is_app_running([r"wezterm-gui", r"/WezTerm"]),
            "focus": "native (wezterm cli activate-pane)" if which("wezterm") else "best-effort",
        },
        "Kitty": {
            "installed": bool(which("kitty")) or app_installed(["kitty"]),
            "running": is_app_running([r"/kitty$", r"kitty\.app"]),
            "focus": "native (kitty @ focus-window)" if which("kitty") else "process-tree",
        },
        "Alacritty": {
            "installed": app_installed(["Alacritty", "alacritty"]),
            "running": is_app_running([r"alacritty", r"/Alacritty\.app/"]),
            "focus": "best-effort (activate + window title)",
        },
        "Hyper": {
            "installed": app_installed(["Hyper"]),
            "running": is_app_running([r"/Hyper\.app/"]),
            "focus": "best-effort",
        },
        "Tabby": {
            "installed": app_installed(["Tabby"]),
            "running": is_app_running([r"/Tabby\.app/"]),
            "focus": "best-effort",
        },
        "Rio": {
            "installed": app_installed(["Rio", "rio"]),
            "running": is_app_running([r"/[Rr]io(\.app)?/", r"\brio$"]),
            "focus": "best-effort",
        },
        "VS Code": {
            "installed": app_installed(["Visual Studio Code", "Code"]),
            "running": is_app_running([r"/Visual Studio Code\.app/", r"/Code\.app/"]),
            "focus": "best-effort (integrated terminals via process tree)",
        },
        "Tmux": {
            "installed": bool(which("tmux")),
            "running": bool(which("tmux")),
            "focus": "select-pane + host terminal focus",
        },
    }
    return specs
