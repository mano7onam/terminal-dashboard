"""iTerm2 scanner + focus."""

from __future__ import annotations

import json
from typing import List

from ..process_utils import get_cwd_for_tty, get_processes_for_tty, get_tty_to_cwd, is_app_running
from ..scripting import jxa_escape, run_jxa


def scan() -> List[dict]:
    if not is_app_running([r"/iTerm2?\.app/"]):
        return []

    jxa = r"""
    function run() {
        var result = [];
        var frontApp = "";
        try {
            frontApp = Application("System Events").processes.whose({frontmost: true})[0].name();
        } catch (e) {}
        var isFront = (frontApp === "iTerm2" || frontApp === "iTerm");
        try {
            var app = Application("iTerm");
            var windows = app.windows();
            for (var w = 0; w < windows.length; w++) {
                var win = windows[w];
                try {
                    var winId = win.id();
                    var tabs = win.tabs();
                    for (var t = 0; t < tabs.length; t++) {
                        var tab = tabs[t];
                        try {
                            var tabId = String(tab.id());
                            var sessions = tab.sessions();
                            var activeSession = null;
                            try { activeSession = tab.currentSession(); } catch (e) {}
                            var activeSessionId = activeSession ? String(activeSession.id()) : null;
                            for (var s = 0; s < sessions.length; s++) {
                                var session = sessions[s];
                                try {
                                    var content = "";
                                    try { content = session.contents() || ""; } catch (e) {}
                                    var sid = String(session.id());
                                    result.push({
                                        app: "iTerm2",
                                        windowId: winId,
                                        tabId: tabId,
                                        tabIndex: t + 1,
                                        sessionId: sid,
                                        tty: session.tty(),
                                        title: session.name() || "iTerm2",
                                        active: isFront && activeSessionId === sid,
                                        contents: content.split("\n").slice(-15).join("\n")
                                    });
                                } catch (e) {}
                            }
                        } catch (e) {}
                    }
                } catch (e) {}
            }
        } catch (e) {}
        return JSON.stringify(result);
    }
    """
    raw = run_jxa(jxa)
    if not raw:
        return []
    try:
        sessions = json.loads(raw)
    except Exception:
        return []

    tty_to_cwd = get_tty_to_cwd()
    for s in sessions:
        tty = s.get("tty")
        if tty and not str(tty).startswith("/dev/"):
            tty = f"/dev/{tty}"
            s["tty"] = tty
        cwd = tty_to_cwd.get(tty) if tty else None
        if not cwd and tty:
            cwd = get_cwd_for_tty(tty)
        s["cwd"] = cwd or "Unknown/Remote"
        s["processes"] = get_processes_for_tty(tty)
    return sessions


def focus(params: dict) -> dict:
    win_id = params.get("windowId")
    tab_id = jxa_escape(params.get("tabId"))
    sess_id = jxa_escape(params.get("sessionId"))
    tty = jxa_escape(params.get("tty") or "")
    jxa = f"""
    var app = Application("iTerm");
    app.activate();
    var windows = app.windows();
    var found = false;
    var ttyNeedle = "{tty}";
    var sessNeedle = "{sess_id}";
    var tabNeedle = "{tab_id}";
    function selectSession(win, tab, session) {{
        try {{ win.select(); }} catch (e) {{}}
        try {{ tab.select(); }} catch (e) {{}}
        try {{ session.select(); }} catch (e) {{}}
        found = true;
    }}
    for (var w = 0; w < windows.length && !found; w++) {{
        var win = windows[w];
        var tabs = win.tabs();
        for (var t = 0; t < tabs.length && !found; t++) {{
            var tab = tabs[t];
            var sessions = tab.sessions();
            for (var s = 0; s < sessions.length && !found; s++) {{
                var session = sessions[s];
                try {{
                    var sid = String(session.id());
                    var stty = "";
                    try {{ stty = session.tty(); }} catch (e) {{}}
                    if ((sessNeedle && sid === sessNeedle) || (ttyNeedle && stty === ttyNeedle)) {{
                        selectSession(win, tab, session);
                    }}
                }} catch (e) {{}}
            }}
        }}
    }}
    if (!found) {{
        for (var w = 0; w < windows.length && !found; w++) {{
            var win = windows[w];
            try {{
                if (String(win.id()) !== String({json.dumps(win_id)})) continue;
                var tabs = win.tabs();
                for (var t = 0; t < tabs.length && !found; t++) {{
                    var tab = tabs[t];
                    if (String(tab.id()) === tabNeedle) {{
                        var sessions = tab.sessions();
                        for (var s = 0; s < sessions.length; s++) {{
                            if (String(sessions[s].id()) === sessNeedle || !sessNeedle) {{
                                selectSession(win, tab, sessions[s]); break;
                            }}
                        }}
                    }}
                }}
            }} catch (e) {{}}
        }}
    }}
    found ? "ok" : "not_found";
    """
    out = run_jxa(jxa)
    if out == "ok":
        return {"status": "success", "message": f"Focused iTerm2 session {params.get('sessionId')}"}
    return {"status": "error", "message": "iTerm2 session not found"}
