"""Capture full terminal scrollback from supported apps."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..process_utils import run_cmd
from ..scripting import jxa_escape, run_applescript, run_jxa


def capture_scrollback(session: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return {text, source, meta} with the fullest scrollback we can get.
    """
    app = session.get("app")
    if app == "Terminal":
        return _capture_terminal_app(session)
    if app == "iTerm2":
        return _capture_iterm(session)
    if app == "Tmux":
        return _capture_tmux(session)
    if app == "Ghostty":
        return _capture_ghostty(session)
    if app == "WezTerm":
        return _capture_wezterm(session)
    if app == "Kitty":
        return _capture_kitty(session)
    # Fallback: whatever was already in the session card
    text = session.get("contents") or ""
    return {
        "text": text,
        "source": "preview",
        "meta": {"note": "Full scrollback not available for this app; used live preview."},
    }


def _capture_terminal_app(session: Dict[str, Any]) -> Dict[str, Any]:
    tty = jxa_escape(session.get("tty") or "")
    win_id = json.dumps(session.get("windowId"))
    tab_idx = int(session.get("tabIndex") or 1)
    jxa = f"""
    function run() {{
        var app = Application("Terminal");
        var windows = app.windows();
        var text = "";
        var ttyNeedle = "{tty}";
        for (var i = 0; i < windows.length; i++) {{
            var tabs = windows[i].tabs();
            for (var t = 0; t < tabs.length; t++) {{
                try {{
                    var tab = tabs[t];
                    var match = false;
                    if (ttyNeedle && tab.tty() === ttyNeedle) match = true;
                    if (!match && String(windows[i].id()) === String({win_id}) && (t+1) === {tab_idx}) match = true;
                    if (match) {{
                        try {{ text = tab.history() || tab.contents() || ""; }}
                        catch (e1) {{ try {{ text = tab.contents() || ""; }} catch (e2) {{}} }}
                        return JSON.stringify({{ok:true, text:text, len:text.length}});
                    }}
                }} catch (e) {{}}
            }}
        }}
        return JSON.stringify({{ok:false, text:"", len:0}});
    }}
    """
    raw = run_jxa(jxa)
    try:
        data = json.loads(raw or "{}")
    except Exception:
        data = {"ok": False, "text": session.get("contents") or ""}
    return {
        "text": data.get("text") or "",
        "source": "Terminal.history" if data.get("ok") else "preview",
        "meta": {"chars": len(data.get("text") or "")},
    }


def _capture_iterm(session: Dict[str, Any]) -> Dict[str, Any]:
    sess_id = jxa_escape(session.get("sessionId") or "")
    tty = jxa_escape(session.get("tty") or "")
    jxa = f"""
    function run() {{
        var app = Application("iTerm");
        var windows = app.windows();
        var sessNeedle = "{sess_id}";
        var ttyNeedle = "{tty}";
        for (var w = 0; w < windows.length; w++) {{
            var tabs = windows[w].tabs();
            for (var t = 0; t < tabs.length; t++) {{
                var sessions = tabs[t].sessions();
                for (var s = 0; s < sessions.length; s++) {{
                    var session = sessions[s];
                    try {{
                        var sid = String(session.id());
                        var stty = "";
                        try {{ stty = session.tty(); }} catch (e) {{}}
                        if ((sessNeedle && sid === sessNeedle) || (ttyNeedle && stty === ttyNeedle)) {{
                            var text = "";
                            try {{ text = session.contents() || ""; }} catch (e) {{}}
                            return JSON.stringify({{ok:true, text:text, len:text.length}});
                        }}
                    }} catch (e) {{}}
                }}
            }}
        }}
        return JSON.stringify({{ok:false, text:""}});
    }}
    """
    raw = run_jxa(jxa)
    try:
        data = json.loads(raw or "{}")
    except Exception:
        data = {"ok": False, "text": session.get("contents") or ""}
    return {
        "text": data.get("text") or "",
        "source": "iTerm2.contents" if data.get("ok") else "preview",
        "meta": {"chars": len(data.get("text") or "")},
    }


def _capture_tmux(session: Dict[str, Any]) -> Dict[str, Any]:
    sess = session.get("sessionName")
    win = session.get("windowIndex")
    pane = session.get("paneIndex")
    if sess is None:
        return {"text": session.get("contents") or "", "source": "preview", "meta": {}}
    target = f"{sess}:{win}.{pane}"
    # Entire history (-S - means start of history)
    out = run_cmd(["tmux", "capture-pane", "-p", "-J", "-S", "-", "-t", target])
    if out is None:
        out = run_cmd(["tmux", "capture-pane", "-p", "-t", target]) or ""
    return {
        "text": out or "",
        "source": "tmux.capture-pane",
        "meta": {"target": target, "chars": len(out or "")},
    }


def _capture_ghostty(session: Dict[str, Any]) -> Dict[str, Any]:
    # Ghostty AppleScript has no scrollback API yet — try select-all / clipboard is invasive.
    # Prefer agent transcript when available; otherwise return preview note.
    return {
        "text": session.get("contents") or "",
        "source": "preview",
        "meta": {
            "note": (
                "Ghostty does not expose scrollback via AppleScript yet. "
                "Use Agent transcript export for Claude/Codex chats in this folder."
            ),
        },
    }


def _capture_wezterm(session: Dict[str, Any]) -> Dict[str, Any]:
    pane_id = session.get("paneId")
    if pane_id is not None:
        out = run_cmd(["wezterm", "cli", "get-text", "--pane-id", str(pane_id), "--start-line", "-100000"])
        if out:
            return {"text": out, "source": "wezterm.cli", "meta": {"chars": len(out)}}
    return {"text": session.get("contents") or "", "source": "preview", "meta": {}}


def _capture_kitty(session: Dict[str, Any]) -> Dict[str, Any]:
    wid = session.get("windowId") or session.get("paneId")
    if wid is not None:
        for base in (["kitten", "@"], ["kitty", "@"]):
            out = run_cmd(base + ["get-text", "--match", f"id:{wid}", "--extent", "all"])
            if out:
                return {"text": out, "source": "kitty.remote", "meta": {"chars": len(out)}}
    return {"text": session.get("contents") or "", "source": "preview", "meta": {}}
