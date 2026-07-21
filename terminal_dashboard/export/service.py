"""High-level export orchestration: resolve source → transcript → format → clipboard/file."""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

from . import agents, capture, formats


def list_export_sources(session: Dict[str, Any]) -> Dict[str, Any]:
    """What can we export for this terminal session?"""
    cwd = session.get("cwd") or ""
    agent_sources = agents.list_sources_for_cwd(cwd) if cwd and cwd != "Unknown/Remote" else []
    scroll = {
        "available": session.get("app") in (
            "Terminal", "iTerm2", "Tmux", "WezTerm", "Kitty", "Ghostty",
            "Warp", "Alacritty", "Hyper", "Tabby", "Rio", "VS Code", "Cursor", "Antigravity",
        ),
        "quality": {
            "Terminal": "full history",
            "iTerm2": "full scrollback buffer",
            "Tmux": "full pane history",
            "WezTerm": "full (CLI)",
            "Kitty": "full (remote control)",
            "Ghostty": "agent transcript preferred (no scrollback API)",
        }.get(session.get("app") or "", "preview / best-effort"),
    }
    return {
        "cwd": cwd,
        "app": session.get("app"),
        "uid": session.get("uid"),
        "scrollback": scroll,
        "agents": [
            {
                "provider": a["provider"],
                "session_id": a["session_id"],
                "title": a["title"],
                "path": a["path"],
                "mtime": a["mtime"],
                "size": a["size"],
                "mtime_iso": datetime.fromtimestamp(a["mtime"]).isoformat(timespec="seconds"),
            }
            for a in agent_sources
        ],
        "formats": ["md", "txt", "html", "pdf", "json", "zip"],
        "destinations": ["clipboard", "download", "file"],
        "recommended": "agent" if agent_sources else "scrollback",
        # Shared with Agent Session Bridge CLI (`asb`) — same library, no duplicated parsers
        "asb": agents.shared_library_info(),
    }


def export_transcript(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    params:
      session: session dict (from UI)
      format: md|txt|html|pdf|json|zip
      destination: clipboard|download|file
      source: auto|agent|scrollback
      agent_path: optional explicit session file
      agent_provider: claude_code|codex
      include_tools: bool (default True)
      include_thinking: bool (default False)
      path: optional save path when destination=file
    """
    session = params.get("session") or {}
    fmt = (params.get("format") or "md").lower()
    dest = (params.get("destination") or "download").lower()
    source_mode = (params.get("source") or "auto").lower()
    include_tools = params.get("include_tools", True)
    include_thinking = params.get("include_thinking", False)

    transcript, used_source = _resolve_transcript(
        session,
        source_mode=source_mode,
        agent_path=params.get("agent_path"),
        agent_provider=params.get("agent_provider"),
        include_tools=include_tools,
        include_thinking=include_thinking,
    )

    data, media_type, filename = formats.render(
        transcript,
        fmt,
        include_tools=include_tools,
        include_thinking=include_thinking,
    )

    result: Dict[str, Any] = {
        "status": "success",
        "format": fmt,
        "destination": dest,
        "source": used_source,
        "filename": filename,
        "media_type": media_type,
        "bytes": len(data),
        "title": transcript.title,
        "message_count": transcript.message_count,
        "image_count": transcript.image_count,
        "provider": transcript.meta.get("provider") or transcript.source,
        "session_id": transcript.session_id,
        "cwd": transcript.cwd,
    }

    if dest == "clipboard":
        # Clipboard prefers agent-paste markdown even if format is txt
        if fmt in ("md", "markdown", "txt"):
            text = data.decode("utf-8", errors="replace")
        else:
            # For rich formats still put markdown on clipboard for agent portability
            text = formats.clipboard_text(transcript, prefer="md", include_tools=include_tools)
            result["clipboard_note"] = (
                f"Clipboard got Markdown (best for pasting into agents). "
                f"Requested file format was {fmt}."
            )
        ok, err = _copy_to_clipboard(text, html=None)
        # Also try HTML clipboard for richer paste when format is html
        if fmt == "html":
            _copy_to_clipboard(
                formats.clipboard_text(transcript, prefer="md", include_tools=include_tools),
                html=data.decode("utf-8", errors="replace"),
            )
        if not ok:
            result["status"] = "error"
            result["message"] = err or "Failed to copy to clipboard"
            return result
        result["message"] = (
            f"Copied {transcript.message_count} messages "
            f"({len(text):,} chars) to clipboard as "
            f"{'Markdown' if fmt != 'txt' else 'text'}"
        )
        result["preview"] = text[:500]
        return result

    if dest == "file":
        path = params.get("path")
        if not path:
            # Default: ~/Downloads/
            downloads = os.path.expanduser("~/Downloads")
            os.makedirs(downloads, exist_ok=True)
            path = os.path.join(downloads, filename)
        path = os.path.expanduser(path)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        result["path"] = path
        result["message"] = f"Saved {filename} ({len(data):,} bytes) → {path}"
        return result

    if dest == "download":
        result["message"] = f"Ready to download {filename}"
        result["content_base64"] = base64.b64encode(data).decode("ascii")
        return result

    result["status"] = "error"
    result["message"] = f"Unknown destination: {dest}"
    return result


def _resolve_transcript(
    session: Dict[str, Any],
    *,
    source_mode: str,
    agent_path: Optional[str],
    agent_provider: Optional[str],
    include_tools: bool,
    include_thinking: bool,
):
    cwd = session.get("cwd") or ""

    if agent_path and agent_provider:
        t = agents.load_transcript(
            agent_provider,
            agent_path,
            include_tools=include_tools,
            include_thinking=include_thinking,
        )
        return t, f"agent:{agent_provider}"

    want_agent = source_mode in ("auto", "agent")
    want_scroll = source_mode in ("auto", "scrollback")

    if want_agent and cwd and cwd != "Unknown/Remote":
        t = agents.find_best_agent_transcript(
            cwd,
            include_tools=include_tools,
            include_thinking=include_thinking,
            prefer_title=session.get("title"),
        )
        if t and t.messages:
            return t, f"agent:{t.source}"
        if source_mode == "agent":
            # explicit agent requested but none found
            t = agents.transcript_from_scrollback(
                "(No Claude Code / Codex session found for this folder.)\n",
                session,
                "none",
            )
            return t, "agent:none"

    if want_scroll:
        cap = capture.capture_scrollback(session)
        text = cap.get("text") or ""
        if not text.strip() and want_agent:
            # last chance agent even if cwd unknown
            pass
        t = agents.transcript_from_scrollback(text, session, cap.get("source") or "scrollback")
        t.meta.update(cap.get("meta") or {})
        return t, f"scrollback:{cap.get('source')}"

    # Fallback empty
    t = agents.transcript_from_scrollback("", session, "empty")
    return t, "empty"


def _copy_to_clipboard(text: str, html: Optional[str] = None) -> tuple:
    """Copy to macOS clipboard via pbcopy. Optionally set public.html."""
    try:
        if html:
            # Use textutil / osascript for multi-flavor pasteboard is complex;
            # put both via python subprocess with pbcopy for text, and html via AppleScript.
            p = subprocess.run(
                ["pbcopy"],
                input=text.encode("utf-8"),
                check=True,
            )
            # Best-effort HTML flavor
            try:
                import tempfile
                with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                    f.write(html)
                    hp = f.name
                subprocess.run(
                    [
                        "osascript", "-e",
                        f'set the clipboard to (read (POSIX file "{hp}") as «class HTML»)',
                    ],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    os.remove(hp)
                except OSError:
                    pass
            except Exception:
                pass
            return True, None

        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        return True, None
    except Exception as e:
        return False, str(e)
