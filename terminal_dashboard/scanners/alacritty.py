"""Alacritty — process-tree scan."""

from __future__ import annotations

from typing import List

from ..process_utils import (
    focus_window_by_title_hint,
    folder_name_for,
    is_app_running,
    sessions_from_app_process_tree,
)


def scan() -> List[dict]:
    if not is_app_running([r"alacritty", r"/Alacritty\.app/"]):
        return []
    return sessions_from_app_process_tree(
        "Alacritty",
        [r"/Alacritty\.app/", r"/alacritty$", r"\balacritty\b"],
        title_prefix="Alacritty",
    )


def focus(params: dict) -> dict:
    hints = []
    if params.get("cwd") and params["cwd"] != "Unknown/Remote":
        hints.append(folder_name_for(params["cwd"]))
    if params.get("title"):
        hints.append(params["title"])
    ok = focus_window_by_title_hint("Alacritty", hints) or focus_window_by_title_hint("alacritty", hints)
    if ok:
        return {"status": "success", "message": "Focused Alacritty (best-effort)"}
    return {"status": "error", "message": "Could not focus Alacritty"}
