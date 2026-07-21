"""On-demand session brief: what this terminal is about (no screenshots).

Loaded only when the user selects a session. Prefer scrollback + agent context
over fragile window captures / Screen Recording permissions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .export import agents
from .export.capture import capture_scrollback
from .process_utils import folder_name_for

PREVIEW_MAX_LINES = 40
PREVIEW_MAX_CHARS = 12_000
AGENT_TITLE_MIN_SCORE = 0.18


def get_preview(
    session: Dict[str, Any],
    *,
    want_screenshot: bool = False,  # ignored — screenshots disabled by design
    allow_focus_for_shot: bool = False,  # ignored
) -> Dict[str, Any]:
    """
    Build a concise “what is this terminal?” brief.

    Returns kind=brief with structured fields for the UI (not a fake terminal).
    """
    app = session.get("app") or ""
    title = (session.get("title") or app or "").strip()
    cwd = session.get("cwd") or ""
    tty = session.get("tty") or session.get("terminalId") or ""
    processes = list(session.get("processes") or [])

    result: Dict[str, Any] = {
        "status": "success",
        "kind": "brief",
        "app": app,
        "title": title,
        "cwd": cwd,
        "uid": session.get("uid"),
        "terminalId": session.get("terminalId"),
        "tty": session.get("tty"),
        "folder": folder_name_for(cwd) if cwd and cwd != "Unknown/Remote" else None,
        "processes": processes,
        "summary": [],          # short bullet facts
        "recent_lines": [],     # last N scrollback lines
        "agent": None,          # matched agent chat meta
        "text": "",             # plain fallback block
        "text_source": None,
        "lines": 0,
        "truncated": False,
        "image_base64": None,   # always None — no screenshots
        "image_mime": None,
        "note": None,
        "match": {},
    }

    summary: List[str] = []
    if app:
        summary.append(f"App: {app}")
    if cwd and cwd != "Unknown/Remote":
        summary.append(f"Folder: {folder_name_for(cwd)}")
        summary.append(f"Path: {cwd}")
    if title and title not in (app, folder_name_for(cwd) if cwd else ""):
        summary.append(f"Title: {title}")
    if session.get("tty"):
        summary.append(f"TTY: {session['tty']}")
    elif session.get("terminalId"):
        tid = str(session["terminalId"])
        summary.append(f"Surface: {tid[:13]}…" if len(tid) > 14 else f"Surface: {tid}")
    if processes:
        # Unique, last few
        uniq = []
        for p in processes:
            if p and p not in uniq:
                uniq.append(p)
        summary.append("Processes: " + ", ".join(uniq[-6:]))

    # Scrollback / snippet
    recent: List[str] = []
    text_source = None
    truncated = False
    if app != "Ghostty":
        cap = capture_scrollback(session)
        raw = (cap.get("text") or "").strip("\n")
        if not raw and session.get("contents"):
            raw = str(session.get("contents") or "")
            text_source = "scan-snippet"
        else:
            text_source = cap.get("source")
        recent, truncated = _last_meaningful_lines(raw)
    else:
        # Ghostty: use scan title + any contents; no scrollback API
        if session.get("contents"):
            recent, truncated = _last_meaningful_lines(str(session["contents"]))
            text_source = "scan-snippet"

    # Agent context (title-matched)
    agent_block = None
    if cwd and cwd != "Unknown/Remote":
        agent_block = _agent_brief(cwd, title)
        if agent_block:
            result["agent"] = {
                "provider": agent_block.get("provider"),
                "title": agent_block.get("title"),
                "session_id": agent_block.get("session_id"),
                "message_count": agent_block.get("message_count"),
                "score": agent_block.get("score"),
                "highlights": agent_block.get("highlights") or [],
            }
            result["match"]["agent"] = agent_block.get("score")
            summary.append(
                f"Agent: {agent_block.get('provider')} · {agent_block.get('title')}"
            )
            if agent_block.get("message_count"):
                summary.append(f"Chat messages: {agent_block['message_count']}")

    result["summary"] = summary
    result["recent_lines"] = recent
    result["truncated"] = truncated
    result["text_source"] = text_source
    result["lines"] = len(recent)

    # Plain text for clipboard-ish fallback
    parts = [" · ".join(summary)] if summary else []
    if result.get("agent") and result["agent"].get("highlights"):
        parts.append("Recent chat:")
        parts.extend("  " + h for h in result["agent"]["highlights"][:8])
    if recent:
        parts.append("Recent output:")
        parts.extend(recent[-PREVIEW_MAX_LINES:])
    result["text"] = "\n".join(parts)

    if not summary and not recent and not agent_block:
        result["note"] = "No extra detail yet — title and path are all we have for this session."
    elif app == "Ghostty" and not recent and agent_block:
        result["note"] = "Ghostty has no scrollback API — showing matched agent chat highlights."
    elif not recent:
        result["note"] = "No scrollback available; showing session metadata" + (
            " + agent highlights" if agent_block else ""
        )

    return result


def _last_meaningful_lines(text: str) -> Tuple[List[str], bool]:
    if not text:
        return [], False
    truncated = False
    if len(text) > PREVIEW_MAX_CHARS:
        text = text[-PREVIEW_MAX_CHARS:]
        truncated = True
        nl = text.find("\n")
        if 0 <= nl < 200:
            text = text[nl + 1:]
    lines = text.splitlines()
    # Drop empty trailing noise, keep last N non-empty-heavy block
    cleaned = []
    for ln in lines:
        s = ln.rstrip()
        # skip pure whitespace / repeated spinners-only lines lightly
        if not s.strip():
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(s)
    if len(cleaned) > PREVIEW_MAX_LINES:
        cleaned = cleaned[-PREVIEW_MAX_LINES:]
        truncated = True
    return cleaned, truncated


def _normalize_title(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"[✳✱*·•●○◉◐◑◒◓⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\s+-\s+(grok|claude|codex|cursor).*$", "", s)
    return s.strip()


def _title_score(terminal_title: str, agent_title: str) -> float:
    a = _normalize_title(terminal_title)
    b = _normalize_title(agent_title)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    ta = set(re.findall(r"[\w\u0400-\u04ff]{3,}", a, flags=re.UNICODE))
    tb = set(re.findall(r"[\w\u0400-\u04ff]{3,}", b, flags=re.UNICODE))
    noise = {"the", "and", "for", "with", "this", "that", "from"}
    ta -= noise
    tb -= noise
    if not ta or not tb:
        return 0.0
    exact = ta & tb
    covered = set(exact)
    for x in ta:
        if x in covered:
            continue
        for y in tb:
            if len(x) >= 4 and len(y) >= 4 and (x in y or y in x):
                covered.add(x)
                break
    coverage = len(covered) / max(len(ta), 1)
    jaccard = len(exact) / max(len(ta | tb), 1)
    score = max(coverage * 0.9, jaccard)
    if len(exact) >= 3:
        score = max(score, 0.55)
    elif len(exact) >= 2:
        score = max(score, 0.35)
    return min(score, 1.0)


def _agent_brief(cwd: str, terminal_title: str) -> Optional[Dict[str, Any]]:
    sources = agents.list_claude_sessions(cwd) + agents.list_codex_sessions(cwd)
    if not sources:
        return None
    scored = []
    for src in sources:
        score = _title_score(terminal_title, src.get("title") or "")
        scored.append((score, src))
    scored.sort(key=lambda x: (x[0], x[1].get("mtime") or 0), reverse=True)
    best_score, best = scored[0]
    if best_score < AGENT_TITLE_MIN_SCORE:
        return None
    try:
        t = agents.load_transcript(
            best["provider"],
            best["path"],
            include_tools=False,
            include_thinking=False,
        )
    except Exception:
        return None

    highlights: List[str] = []
    for m in t.messages[-12:]:
        if m.role not in ("user", "assistant"):
            continue
        body = (m.text or "").strip()
        if not body:
            continue
        line = body.splitlines()[0].strip()
        if len(line) > 140:
            line = line[:137] + "…"
        highlights.append(f"[{m.role}] {line}")

    display_title = best.get("title") or t.title
    if str(display_title).endswith(".jsonl"):
        display_title = highlights[0].split("] ", 1)[-1] if highlights else display_title

    return {
        "provider": t.meta.get("provider") or t.source,
        "title": display_title,
        "session_id": t.session_id,
        "message_count": t.message_count,
        "score": best_score,
        "highlights": highlights[-8:],
    }
