"""WezTerm via `wezterm cli` when available, else process tree."""

from __future__ import annotations

import json
from typing import List

from ..process_utils import (
    focus_window_by_title_hint,
    folder_name_for,
    get_processes_for_tty,
    is_app_running,
    normalize_path,
    run_cmd,
    sessions_from_app_process_tree,
    which,
)


def scan() -> List[dict]:
    wez = which("wezterm")
    if wez:
        # Prefer rich CLI listing
        out = run_cmd([wez, "cli", "list", "--format", "json"])
        if out:
            try:
                panes = json.loads(out)
            except Exception:
                panes = None
            if isinstance(panes, list):
                sessions = []
                for p in panes:
                    cwd = normalize_path(p.get("cwd") or p.get("current_working_dir"))
                    tty = p.get("tty_name") or p.get("tty")
                    if tty and not str(tty).startswith("/dev/"):
                        tty = f"/dev/{tty}"
                    title = p.get("title") or p.get("window_title") or "WezTerm"
                    sessions.append({
                        "app": "WezTerm",
                        "paneId": p.get("pane_id") or p.get("pane-id"),
                        "windowId": p.get("window_id"),
                        "tabId": p.get("tab_id"),
                        "tty": tty,
                        "title": title,
                        "active": bool(p.get("is_active") or p.get("active")),
                        "cwd": cwd or "Unknown/Remote",
                        "processes": get_processes_for_tty(tty) if tty else [],
                        "contents": "",
                    })
                if sessions:
                    return sessions

    if not is_app_running([r"wezterm-gui", r"/WezTerm", r"wezterm"]):
        return []
    return sessions_from_app_process_tree(
        "WezTerm",
        [r"wezterm-gui", r"/WezTerm\.app/"],
        title_prefix="WezTerm",
    )


def focus(params: dict) -> dict:
    wez = which("wezterm")
    pane_id = params.get("paneId")
    if wez and pane_id is not None:
        run_cmd([wez, "cli", "activate-pane", "--pane-id", str(pane_id)])
        return {"status": "success", "message": f"Focused WezTerm pane {pane_id}"}

    hints = []
    if params.get("cwd") and params["cwd"] != "Unknown/Remote":
        hints.append(folder_name_for(params["cwd"]))
    if params.get("title"):
        hints.append(params["title"])
    ok = focus_window_by_title_hint("WezTerm", hints) or focus_window_by_title_hint("wezterm", hints)
    if ok:
        return {"status": "success", "message": "Focused WezTerm (best-effort)"}
    return {"status": "error", "message": "Could not focus WezTerm"}
