"""Agent session transcripts for export.

Implementation lives in the shared library **agent_session_bridge**
(`~/dev/agent-session-bridge`) so Terminal Dashboard and the `asb` CLI
do not duplicate Claude/Codex/Grok parsers.

CLI for agents (search / smart pull across sessions)::

    asb list --json
    asb search "topic" --json
    asb pull <session_id> --query "topic" --mode query

This module re-exports the rich export API used by ``export.service`` /
``export.formats``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _bootstrap_shared_lib() -> Path:
    """Make ``agent_session_bridge`` importable (editable install or sibling repo)."""
    try:
        import agent_session_bridge  # noqa: F401

        return Path(agent_session_bridge.__file__).resolve().parent.parent
    except ImportError:
        pass

    env = os.environ.get("AGENT_SESSION_BRIDGE_PATH") or os.environ.get("ASB_PATH")
    candidates = []
    if env:
        candidates.append(Path(os.path.expanduser(env)))

    # …/claude-terminal-ui/terminal_dashboard/export/agents.py → sibling repo
    here = Path(__file__).resolve()
    repo_root = here.parents[2]  # claude-terminal-ui
    candidates.append(repo_root.parent / "agent-session-bridge")
    candidates.append(Path.home() / "dev" / "agent-session-bridge")

    for root in candidates:
        if not root:
            continue
        pkg = root / "agent_session_bridge"
        if pkg.is_dir():
            root_s = str(root)
            if root_s not in sys.path:
                sys.path.insert(0, root_s)
            try:
                import agent_session_bridge  # noqa: F401

                return root
            except ImportError:
                continue

    raise ImportError(
        "agent_session_bridge not found. Clone/install it next to this repo "
        "(~/dev/agent-session-bridge) or set AGENT_SESSION_BRIDGE_PATH. "
        "See https://github.com/mano7onam/agent-session-bridge"
    )


_ASB_ROOT = _bootstrap_shared_lib()

# Shared rich export surface (attachments, tools, thinking)
from agent_session_bridge.rich import (  # noqa: E402
    Attachment,
    Message,
    Transcript,
    claude_project_dir_for_path,
    find_best_agent_transcript,
    format_ts,
    list_claude_sessions,
    list_codex_sessions,
    list_grok_sessions,
    list_sources_for_cwd,
    load_transcript,
    transcript_from_scrollback,
)

try:
    from agent_session_bridge.bootstrap import asb_cli_hint, which_asb
except Exception:  # pragma: no cover
    def which_asb() -> Optional[str]:
        return None

    def asb_cli_hint() -> Dict[str, Any]:
        return {
            "package": "agent-session-bridge",
            "cli": "asb",
            "path": str(_ASB_ROOT),
            "binary": None,
        }


def shared_library_info() -> Dict[str, Any]:
    """For /api/health and UI — where export/search logic comes from."""
    hint = asb_cli_hint()
    try:
        import agent_session_bridge as asb

        ver = getattr(asb, "__version__", "?")
    except Exception:
        ver = "?"
    hint = dict(hint)
    hint["version"] = ver
    hint["root"] = str(_ASB_ROOT)
    hint["binary"] = which_asb()
    return hint


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
    "list_sources_for_cwd",
    "load_transcript",
    "transcript_from_scrollback",
    "shared_library_info",
    "which_asb",
    "asb_cli_hint",
]
