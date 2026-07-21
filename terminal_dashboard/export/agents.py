"""Agent session transcripts for export.

Implementation lives in the shared library **puenteo**
(``pip install puenteo`` / ``~/dev/puenteo``) so Terminal Dashboard and the
``puenteo`` CLI do not duplicate Claude/Codex/Grok/Pi parsers.

CLI for agents::

    puenteo list --json
    puenteo search "topic" --json
    puenteo pull <session_id> --query "topic" --mode query
    puenteo export <session_id> -f md -o chat.md

This module re-exports the rich export API used by ``export.service`` /
``export.formats``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _bootstrap_shared_lib() -> Path:
    """Make ``puenteo`` importable (pip install or sibling repo)."""
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

    # …/claude-terminal-ui/terminal_dashboard/export/agents.py → sibling repos
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    candidates.append(repo_root.parent / "puenteo")
    candidates.append(repo_root.parent / "agent-session-bridge")  # legacy folder
    candidates.append(Path.home() / "dev" / "puenteo")
    candidates.append(Path.home() / "dev" / "agent-session-bridge")

    for root in candidates:
        if not root:
            continue
        pkg = root / "puenteo"
        if pkg.is_dir():
            root_s = str(root)
            if root_s not in sys.path:
                sys.path.insert(0, root_s)
            try:
                import puenteo  # noqa: F401

                return root
            except ImportError:
                continue

    raise ImportError(
        "puenteo not found. Install with: pip install puenteo\n"
        "Or clone next to this repo (~/dev/puenteo) / set PUENTEO_PATH.\n"
        "See https://github.com/mano7onam/puenteo"
    )


_PUENTEO_ROOT = _bootstrap_shared_lib()

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
            "path": str(_PUENTEO_ROOT),
            "binary": None,
        }


def shared_library_info() -> Dict[str, Any]:
    """For /api/health and UI — where export/search logic comes from."""
    hint = dict(puenteo_cli_hint())
    try:
        import puenteo as p

        ver = getattr(p, "__version__", "?")
    except Exception:
        ver = "?"
    hint["version"] = ver
    hint["root"] = str(_PUENTEO_ROOT)
    hint["binary"] = which_puenteo()
    return hint


# Back-compat names used by older UI code
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
