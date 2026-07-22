"""Agent session transcripts for export — powered by **puenteo**.

Install once::

    pip install puenteo
    # CLI (same tool):
    puenteo list
    asb list

This module re-exports the rich export API used by ``export.service`` /
``export.formats``. Prefer the installed package; fall back to a sibling
checkout under ``~/dev/puenteo`` if needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _bootstrap_puenteo() -> Path:
    """Ensure ``puenteo`` is importable; return package root path."""
    try:
        import puenteo  # noqa: F401

        return Path(puenteo.__file__).resolve().parent.parent
    except ImportError:
        pass

    env = (
        os.environ.get("PUENTEO_PATH")
        or os.environ.get("AGENT_SESSION_BRIDGE_PATH")
        or os.environ.get("ASB_PATH")
    )
    candidates = []
    if env:
        candidates.append(Path(os.path.expanduser(env)))

    here = Path(__file__).resolve()
    repo_root = here.parents[2]  # claude-terminal-ui / terminal-dashboard repo
    candidates.extend(
        [
            repo_root.parent / "puenteo",
            repo_root.parent / "agent-session-bridge",  # legacy local folder name
            Path.home() / "dev" / "puenteo",
            Path.home() / "dev" / "agent-session-bridge",
        ]
    )

    for root in candidates:
        if not root:
            continue
        pkg = root / "puenteo"
        if not pkg.is_dir():
            continue
        root_s = str(root)
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
        try:
            import puenteo  # noqa: F401

            return root
        except ImportError:
            continue

    raise ImportError(
        "puenteo is required for agent chat export.\n"
        "  pip install puenteo\n"
        "  # or: uv add puenteo\n"
        "  # or clone https://github.com/mano7onam/puenteo and set PUENTEO_PATH\n"
        "Docs: https://pypi.org/project/puenteo/"
    )


_PUENTEO_ROOT = _bootstrap_puenteo()

# Rich export surface (attachments, tools, thinking) — from puenteo
from puenteo.rich import (  # noqa: E402
    Attachment,
    Message,
    Transcript,
    claude_project_dir_for_path,
    find_best_agent_transcript,
    format_ts,
    list_claude_sessions,
    list_codex_sessions,
    list_grok_sessions,
    list_pi_sessions,
    list_sources_for_cwd,
    load_transcript,
    transcript_from_scrollback,
)

try:
    from puenteo.bootstrap import puenteo_cli_hint, which_puenteo
except Exception:  # pragma: no cover

    def which_puenteo() -> Optional[str]:
        return None

    def puenteo_cli_hint() -> Dict[str, Any]:
        return {
            "package": "puenteo",
            "cli": "puenteo",
            "cli_aliases": ["puenteo", "asb", "pto"],
            "path": str(_PUENTEO_ROOT),
            "binary": None,
            "install": "pip install puenteo",
            "github": "https://github.com/mano7onam/puenteo",
            "pypi": "https://pypi.org/project/puenteo/",
        }


def shared_library_info() -> Dict[str, Any]:
    """For /api/health and UI — linked puenteo library + CLI."""
    hint = dict(puenteo_cli_hint())
    try:
        import puenteo as p

        ver = getattr(p, "__version__", "?")
    except Exception:
        ver = "?"
    hint["version"] = ver
    hint["root"] = str(_PUENTEO_ROOT)
    hint["binary"] = which_puenteo()
    hint["import"] = "puenteo"
    return hint


# Back-compat names
which_asb = which_puenteo
asb_cli_hint = puenteo_cli_hint


__all__ = [
    "Attachment",
    "Message",
    "Transcript",
    "claude_project_dir_for_path",
    "find_best_agent_transcript",
    "format_ts",
    "list_claude_sessions",
    "list_codex_sessions",
    "list_grok_sessions",
    "list_pi_sessions",
    "list_sources_for_cwd",
    "load_transcript",
    "transcript_from_scrollback",
    "shared_library_info",
    "which_puenteo",
    "puenteo_cli_hint",
    "which_asb",
    "asb_cli_hint",
]
