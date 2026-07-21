"""VS Code / Cursor / Antigravity integrated terminals + focus-by-workspace."""

from __future__ import annotations

import subprocess
from typing import List

from ..ides import open_in_ide
from ..process_utils import (
    folder_name_for,
    is_app_running,
    sessions_from_app_process_tree,
    which,
)


_EDITOR_APPS = [
    (
        "VS Code",
        [r"/Visual Studio Code\.app/", r"/Code\.app/Contents/MacOS/Electron"],
        [r"/Visual Studio Code\.app/", r"Code Helper"],
        "vscode",
    ),
    (
        "Cursor",
        [r"/Cursor\.app/"],
        [r"/Cursor\.app/"],
        "cursor",
    ),
    (
        "Antigravity",
        [r"/Antigravity\.app/", r"/Antigravity IDE\.app/"],
        [r"/Antigravity"],
        "antigravity",
    ),
]


def scan() -> List[dict]:
    sessions: List[dict] = []
    for app_name, run_pats, root_pats, ide_id in _EDITOR_APPS:
        if not is_app_running(run_pats):
            continue
        found = sessions_from_app_process_tree(
            app_name,
            root_pats,
            title_prefix=f"{app_name} Terminal",
        )
        for s in found:
            if s.get("tty"):
                s["ideId"] = ide_id
                sessions.append(s)
    return sessions


def focus(params: dict) -> dict:
    """
    For integrated terminals we don't need the exact pane — open the IDE
    on the session's project folder so the user can find the terminal there.
    """
    app = params.get("app") or "VS Code"
    cwd = params.get("cwd")
    ide_id = params.get("ideId") or {
        "VS Code": "vscode",
        "Cursor": "cursor",
        "Antigravity": "antigravity",
    }.get(app, "vscode")

    if cwd and cwd != "Unknown/Remote":
        res = open_in_ide(cwd, ide_id)
        if res.get("status") == "success":
            return {
                "status": "success",
                "message": (
                    f"Opened {app} on {folder_name_for(cwd)} — "
                    f"find the terminal panel inside the IDE"
                ),
            }
        # Fall through with error detail
        return {
            "status": "error",
            "message": res.get("message") or f"Could not open {app} on {cwd}",
        }

    # No cwd: just activate the app
    open_names = {
        "VS Code": "Visual Studio Code",
        "Cursor": "Cursor",
        "Antigravity": "Antigravity",
    }
    name = open_names.get(app, app)
    try:
        subprocess.run(["open", "-a", name], check=False)
        return {
            "status": "success",
            "message": f"Activated {name} (no project path for this session)",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
