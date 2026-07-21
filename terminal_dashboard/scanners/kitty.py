"""Kitty via remote control when available, else process tree."""

from __future__ import annotations

import json
from typing import List

from ..process_utils import (
    focus_window_by_title_hint,
    folder_name_for,
    is_app_running,
    normalize_path,
    run_cmd,
    sessions_from_app_process_tree,
    which,
)


def _kitty_cmd() -> List[str] | None:
    # Prefer `kitten @` / `kitty @`
    if which("kitten"):
        return ["kitten", "@"]
    if which("kitty"):
        return ["kitty", "@"]
    return None


def scan() -> List[dict]:
    base = _kitty_cmd()
    if base:
        out = run_cmd(base + ["ls"])
        if out:
            try:
                data = json.loads(out)
            except Exception:
                data = None
            sessions = []
            if isinstance(data, list):
                for os_win in data:
                    for tab in os_win.get("tabs") or []:
                        for w in tab.get("windows") or []:
                            cwd = normalize_path(w.get("cwd"))
                            title = w.get("title") or tab.get("title") or "Kitty"
                            sessions.append({
                                "app": "Kitty",
                                "windowId": w.get("id") or os_win.get("id"),
                                "paneId": w.get("id"),
                                "tabId": tab.get("id"),
                                "tty": None,
                                "title": title,
                                "active": bool(w.get("is_focused") or tab.get("is_focused")),
                                "cwd": cwd or "Unknown/Remote",
                                "processes": [],
                                "contents": "",
                            })
            if sessions:
                return sessions

    if not is_app_running([r"/kitty(\.app)?/", r"\bkitty$"]):
        return []
    return sessions_from_app_process_tree(
        "Kitty",
        [r"/kitty\.app/", r"/bin/kitty", r"\bkitty$"],
        title_prefix="Kitty",
    )


def focus(params: dict) -> dict:
    base = _kitty_cmd()
    wid = params.get("windowId") or params.get("paneId")
    if base and wid is not None:
        run_cmd(base + ["focus-window", f"--match=id:{wid}"])
        return {"status": "success", "message": f"Focused Kitty window {wid}"}

    hints = []
    if params.get("cwd") and params["cwd"] != "Unknown/Remote":
        hints.append(folder_name_for(params["cwd"]))
    if params.get("title"):
        hints.append(params["title"])
    ok = focus_window_by_title_hint("kitty", hints)
    if ok:
        return {"status": "success", "message": "Focused Kitty (best-effort)"}
    return {
        "status": "error",
        "message": "Could not focus Kitty. Enable remote control (allow_remote_control yes) for precise focus.",
    }
