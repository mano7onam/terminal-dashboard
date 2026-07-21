"""Detect installed IDEs / editors and open a folder in them."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional

from .process_utils import app_installed, normalize_path, which

# (id, display name, app bundle names, CLI binaries, open via `open -a`)
# Order = UI order. JetBrains first when installed (before VS Code / Cursor).
_IDE_SPECS = [
    {
        "id": "idea",
        "name": "IntelliJ IDEA",
        "apps": ["IntelliJ IDEA", "IntelliJ IDEA CE", "IntelliJ IDEA Ultimate"],
        "cli": ["idea"],
        "open_a": ["IntelliJ IDEA", "IntelliJ IDEA CE", "IntelliJ IDEA Ultimate"],
    },
    {
        "id": "pycharm",
        "name": "PyCharm",
        "apps": ["PyCharm", "PyCharm CE", "PyCharm Professional"],
        # JetBrains Toolbox often installs versioned names (scanned below)
        "cli": ["pycharm", "charm"],
        "open_a": ["PyCharm", "PyCharm CE", "PyCharm Professional"],
        "open_a_globs": True,
    },
    {
        "id": "webstorm",
        "name": "WebStorm",
        "apps": ["WebStorm"],
        "cli": ["webstorm"],
        "open_a": ["WebStorm"],
    },
    {
        "id": "goland",
        "name": "GoLand",
        "apps": ["GoLand"],
        "cli": ["goland"],
        "open_a": ["GoLand"],
    },
    {
        "id": "rubymine",
        "name": "RubyMine",
        "apps": ["RubyMine"],
        "cli": ["rubymine"],
        "open_a": ["RubyMine"],
    },
    {
        "id": "androidstudio",
        "name": "Android Studio",
        "apps": ["Android Studio"],
        "cli": ["studio"],
        "open_a": ["Android Studio"],
    },
    {
        "id": "vscode",
        "name": "VS Code",
        "apps": ["Visual Studio Code", "Code"],
        "cli": ["code"],
        "open_a": ["Visual Studio Code"],
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "apps": ["Cursor"],
        "cli": ["cursor"],
        "open_a": ["Cursor"],
    },
    {
        "id": "zed",
        "name": "Zed",
        "apps": ["Zed"],
        "cli": ["zed"],
        "open_a": ["Zed"],
    },
    {
        "id": "sublime",
        "name": "Sublime Text",
        "apps": ["Sublime Text"],
        "cli": ["subl"],
        "open_a": ["Sublime Text"],
    },
    {
        "id": "nova",
        "name": "Nova",
        "apps": ["Nova"],
        "cli": ["nova"],
        "open_a": ["Nova"],
    },
    {
        "id": "xcode",
        "name": "Xcode",
        "apps": ["Xcode"],
        "cli": ["xed"],
        "open_a": ["Xcode"],
    },
    {
        "id": "antigravity",
        "name": "Antigravity",
        "apps": ["Antigravity", "Antigravity IDE"],
        "cli": [],
        "open_a": ["Antigravity", "Antigravity IDE"],
    },
]


def _find_app_bundle(names: List[str]) -> Optional[str]:
    roots = [
        "/Applications",
        os.path.expanduser("~/Applications"),
        "/System/Applications",
    ]
    for name in names:
        for root in roots:
            p = os.path.join(root, f"{name}.app")
            if os.path.isdir(p):
                return p
    # JetBrains Toolbox versioned: PyCharm 2024.3.app etc.
    for root in ("/Applications", os.path.expanduser("~/Applications")):
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.listdir(root):
                if not entry.endswith(".app"):
                    continue
                base = entry[:-4]
                for name in names:
                    if base == name or base.startswith(name + " "):
                        return os.path.join(root, entry)
        except OSError:
            pass
    return None


def list_available_ides() -> List[Dict[str, Any]]:
    """IDEs/editors installed on this Mac (only those that exist)."""
    found = []
    for spec in _IDE_SPECS:
        has_cli = any(which(c) for c in spec.get("cli") or [])
        bundle = _find_app_bundle(spec.get("apps") or [])
        if not has_cli and not bundle:
            # try open_a names
            bundle = _find_app_bundle(spec.get("open_a") or [])
        if has_cli or bundle:
            found.append({
                "id": spec["id"],
                "name": spec["name"],
                "cli": next((c for c in (spec.get("cli") or []) if which(c)), None),
                "app_path": bundle,
            })
    return found


def open_in_ide(path: str, ide_id: str) -> Dict[str, Any]:
    """Open folder/file in the given IDE."""
    path = normalize_path(path) if path else None
    if not path or not os.path.exists(path):
        return {"status": "error", "message": "Invalid path"}

    spec = next((s for s in _IDE_SPECS if s["id"] == ide_id), None)
    if not spec:
        return {"status": "error", "message": f"Unknown IDE: {ide_id}"}

    # Prefer CLI (best for opening the right workspace)
    for cli in spec.get("cli") or []:
        bin_path = which(cli)
        if not bin_path:
            continue
        try:
            subprocess.Popen(
                [bin_path, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {
                "status": "success",
                "message": f"Opened {path} in {spec['name']} ({cli})",
                "ide": spec["name"],
            }
        except Exception as e:
            last_err = str(e)
    else:
        last_err = None

    # Fallback: open -a "App Name" path
    bundle = _find_app_bundle((spec.get("open_a") or []) + (spec.get("apps") or []))
    if bundle:
        app_name = os.path.basename(bundle)[:-4]  # strip .app
        try:
            subprocess.run(["open", "-a", app_name, path], check=True)
            return {
                "status": "success",
                "message": f"Opened {path} in {app_name}",
                "ide": app_name,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {
        "status": "error",
        "message": last_err or f"{spec['name']} is not installed or CLI not on PATH",
    }
