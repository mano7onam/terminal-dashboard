"""Hyper — Electron terminal, process-tree scan."""

from __future__ import annotations

from typing import List

from ..process_utils import focus_window_by_title_hint, folder_name_for, is_app_running, sessions_from_app_process_tree


def scan() -> List[dict]:
    if not is_app_running([r"/Hyper\.app/"]):
        return []
    return sessions_from_app_process_tree(
        "Hyper",
        [r"/Hyper\.app/"],
        title_prefix="Hyper",
    )


def focus(params: dict) -> dict:
    hints = [folder_name_for(params.get("cwd"))] if params.get("cwd") else []
    if params.get("title"):
        hints.append(params["title"])
    ok = focus_window_by_title_hint("Hyper", hints)
    if ok:
        return {"status": "success", "message": "Focused Hyper (best-effort)"}
    return {"status": "error", "message": "Could not focus Hyper"}
