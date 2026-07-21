"""Apple Terminal.app scanner + focus."""

from __future__ import annotations

import json
from typing import List, Optional

from ..process_utils import get_cwd_for_tty, get_processes_for_tty, get_tty_to_cwd, is_app_running
from ..scripting import jxa_escape, run_jxa


def scan() -> List[dict]:
    if not is_app_running([r"/Terminal\.app/"]):
        return []

    jxa = r"""
    function run() {
        var result = [];
        var frontApp = "";
        try {
            frontApp = Application("System Events").processes.whose({frontmost: true})[0].name();
        } catch (e) {}
        var isFront = frontApp === "Terminal";
        try {
            var app = Application("Terminal");
            var windows = app.windows();
            for (var w = 0; w < windows.length; w++) {
                var win = windows[w];
                try {
                    var winId = win.id();
                    var tabs = win.tabs();
                    for (var t = 0; t < tabs.length; t++) {
                        var tab = tabs[t];
                        try {
                            var content = "";
                            try { content = tab.contents() || ""; } catch (e) {}
                            var lines = content.split("\n");
                            result.push({
                                app: "Terminal",
                                windowId: winId,
                                tabIndex: t + 1,
                                tty: tab.tty(),
                                title: tab.customTitle() || "Terminal",
                                active: isFront && !!tab.selected(),
                                contents: lines.slice(-15).join("\n")
                            });
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
    tab_idx = params.get("tabIndex") or 1
    tty = jxa_escape(params.get("tty") or "")
    jxa = f"""
    var app = Application("Terminal");
    app.activate();
    var windows = app.windows();
    var targetWin = null, targetTab = null;
    var ttyNeedle = "{tty}";
    if (ttyNeedle) {{
        for (var i = 0; i < windows.length; i++) {{
            var tabs = windows[i].tabs();
            for (var t = 0; t < tabs.length; t++) {{
                try {{
                    if (tabs[t].tty() === ttyNeedle) {{
                        targetWin = windows[i]; targetTab = tabs[t]; break;
                    }}
                }} catch (e) {{}}
            }}
            if (targetTab) break;
        }}
    }}
    if (!targetTab) {{
        for (var i = 0; i < windows.length; i++) {{
            try {{
                if (String(windows[i].id()) === String({json.dumps(win_id)})) {{
                    targetWin = windows[i];
                    var tabs = windows[i].tabs();
                    var idx = {int(tab_idx)} - 1;
                    if (idx >= 0 && idx < tabs.length) targetTab = tabs[idx];
                    break;
                }}
            }} catch (e) {{}}
        }}
    }}
    if (targetWin && targetTab) {{
        targetWin.index = 1;
        targetTab.selected = true;
        "ok";
    }} else {{
        "not_found";
    }}
    """
    out = run_jxa(jxa)
    if out == "ok":
        return {"status": "success", "message": f"Focused Terminal (tty={params.get('tty') or tab_idx})"}
    return {"status": "error", "message": "Terminal tab not found (may have been closed)"}
