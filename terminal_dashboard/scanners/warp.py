"""Warp terminal — process-tree scan + best-effort focus."""

from __future__ import annotations

from typing import List

from ..process_utils import (
    focus_window_by_title_hint,
    folder_name_for,
    is_app_running,
    sessions_from_app_process_tree,
)


def scan() -> List[dict]:
    if not is_app_running([r"/Warp\.app/", r"Warp\.app"]):
        return []
    # Avoid matching Cloudflare WARP VPN
    return sessions_from_app_process_tree(
        app_name="Warp",
        root_patterns=[r"/Applications/Warp\.app/", r"Warp\.app/Contents/MacOS/stable"],
        title_prefix="Warp",
    )


def focus(params: dict) -> dict:
    hints = []
    if params.get("cwd") and params["cwd"] != "Unknown/Remote":
        hints.append(folder_name_for(params["cwd"]))
        hints.append(params["cwd"].split("/")[-1])
    if params.get("title"):
        hints.append(params["title"])
    ok = focus_window_by_title_hint("Warp", hints)
    if ok:
        return {"status": "success", "message": "Focused Warp (best-effort window match)"}
    return {
        "status": "error",
        "message": "Could not focus Warp window. Grant Accessibility to your terminal/Python if prompted.",
    }
