"""Session identity helpers."""

from __future__ import annotations

from typing import Any, Dict


def make_session_uid(session: Dict[str, Any]) -> str:
    app = session.get("app")
    if app == "Terminal":
        return f"terminal-{session.get('windowId')}-{session.get('tabIndex')}-{session.get('tty') or ''}"
    if app == "iTerm2":
        return f"iterm-{session.get('sessionId') or session.get('tabId')}"
    if app == "Ghostty":
        return f"ghostty-{session.get('terminalId')}"
    if app == "Tmux":
        return (
            f"tmux-{session.get('sessionName')}-"
            f"{session.get('windowIndex')}-{session.get('paneIndex')}"
        )
    if app == "WezTerm":
        return f"wezterm-{session.get('paneId') or session.get('tty')}"
    if app == "Kitty":
        return f"kitty-{session.get('windowId')}-{session.get('paneId') or session.get('tty')}"
    # Process-tree apps (Warp, Alacritty, Hyper, Tabby, Rio, …)
    tty = session.get("tty") or ""
    shell = session.get("shellPid") or ""
    return f"{(app or 'app').lower()}-{tty}-{shell}"


def finalize_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure cwd / folderName / uid exist."""
    from .process_utils import folder_name_for, normalize_path

    cwd = session.get("cwd")
    if cwd and cwd != "Unknown/Remote":
        cwd_n = normalize_path(cwd) or cwd
        session["cwd"] = cwd_n
        session["folderName"] = session.get("folderName") or folder_name_for(cwd_n)
    else:
        session["cwd"] = session.get("cwd") or "Unknown/Remote"
        session["folderName"] = session.get("folderName") or "Remote/System"
    session.setdefault("processes", [])
    session.setdefault("contents", "")
    session.setdefault("active", False)
    session.setdefault("title", session.get("app") or "Terminal")
    session["uid"] = make_session_uid(session)
    return session
