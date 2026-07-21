"""Ghostty scanner + focus (native AppleScript dictionary)."""

from __future__ import annotations

import json
from typing import List

from ..process_utils import (
    IGNORE_PROCS,
    descendant_pids,
    get_process_table,
    get_shell_cwds,
    is_app_running,
    normalize_path,
    pids_matching,
)
from ..scripting import applescript_escape, run_applescript, run_jxa


def _ghostty_cwd_procs():
    roots = set(pids_matching(r"[Gg]hostty"))
    if not roots:
        return {}
    pid_to_info = get_process_table()
    pid_to_cwd = get_shell_cwds()
    desc = descendant_pids(roots, pid_to_info)
    cwd_procs = {}
    for pid in desc:
        info = pid_to_info.get(pid)
        if not info:
            continue
        cwd = pid_to_cwd.get(pid)
        comm = info["comm"]
        if cwd and comm not in IGNORE_PROCS:
            lst = cwd_procs.setdefault(cwd, [])
            if comm not in lst:
                lst.append(comm)
    return cwd_procs


def scan() -> List[dict]:
    if not is_app_running([r"[/ ]ghostty$", r"/Ghostty\.app/"]):
        return []

    jxa = r"""
    function run() {
        var result = [];
        var frontApp = "";
        try {
            frontApp = Application("System Events").processes.whose({frontmost: true})[0].name();
        } catch (e) {}
        var ghosttyIsFront = frontApp === "Ghostty";
        var frontGhosttyWinId = null;
        try {
            var app = Application("Ghostty");
            try { frontGhosttyWinId = String(app.frontWindow().id()); } catch (e) {}
            var windows = app.windows();
            for (var w = 0; w < windows.length; w++) {
                var win = windows[w];
                try {
                    var winId = String(win.id());
                    var winName = "";
                    try { winName = win.name() || ""; } catch (e) {}
                    var isFrontWin = (frontGhosttyWinId !== null && winId === frontGhosttyWinId);
                    var tabs = win.tabs();
                    for (var t = 0; t < tabs.length; t++) {
                        var tab = tabs[t];
                        try {
                            var tabId = String(tab.id());
                            var tabSelected = false;
                            try { tabSelected = !!tab.selected(); } catch (e) {}
                            var tabIndex = t + 1;
                            try { tabIndex = tab.index(); } catch (e) {}
                            var focusedId = null;
                            try {
                                var ft = tab.focusedTerminal();
                                if (ft) focusedId = String(ft.id());
                            } catch (e) {}
                            var terminals = tab.terminals();
                            for (var s = 0; s < terminals.length; s++) {
                                var terminal = terminals[s];
                                try {
                                    var termId = String(terminal.id());
                                    var cwd = "";
                                    try { cwd = terminal.workingDirectory() || ""; } catch (e) {}
                                    var title = "Ghostty";
                                    try { title = terminal.name() || "Ghostty"; } catch (e) {}
                                    var isActive = ghosttyIsFront && isFrontWin && tabSelected && (
                                        focusedId ? (termId === focusedId) : (s === 0)
                                    );
                                    result.push({
                                        app: "Ghostty",
                                        windowId: winId,
                                        windowName: winName,
                                        tabId: tabId,
                                        tabIndex: tabIndex,
                                        terminalId: termId,
                                        title: title,
                                        active: isActive,
                                        cwd: cwd || null,
                                        contents: ""
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

    cwd_procs = _ghostty_cwd_procs()
    for s in sessions:
        cwd = normalize_path(s.get("cwd")) if s.get("cwd") else None
        s["cwd"] = cwd or "Unknown/Remote"
        s["tty"] = None
        s["processes"] = list(cwd_procs.get(cwd, [])) if cwd else []
    return sessions


def focus(params: dict) -> dict:
    """
    Focus a specific Ghostty surface by stable terminalId.

    Important macOS fullscreen quirk:
      Calling bare `activate` on Ghostty first often switches to the Space that
      holds a *fullscreen* Ghostty window — even when we then focus another
      terminalId. Order must be: find target → focus surface / activate its
      window → only then activate the app.
    """
    terminal_id = params.get("terminalId")
    if not terminal_id:
        return {"status": "error", "message": "Missing Ghostty terminalId"}
    tid = applescript_escape(terminal_id)
    win_id = applescript_escape(str(params.get("windowId") or ""))
    tab_id = applescript_escape(str(params.get("tabId") or ""))

    script = f'''
    tell application "Ghostty"
        set targetId to "{tid}"
        set winId to "{win_id}"
        set tabId to "{tab_id}"
        set targetTerm to missing value

        repeat with t in terminals
            if id of t is targetId then
                set targetTerm to t
                exit repeat
            end if
        end repeat

        if targetTerm is missing value then
            return "not_found"
        end if

        -- 1) Raise the owning window first (if we know windowId), WITHOUT
        --    activating the whole app (avoids jumping to a fullscreen Space).
        if winId is not "" then
            try
                repeat with w in windows
                    if (id of w as text) is winId then
                        try
                            activate window w
                        end try
                        -- select tab if possible
                        if tabId is not "" then
                            try
                                repeat with tb in tabs of w
                                    if (id of tb as text) is tabId then
                                        select tab tb
                                        exit repeat
                                    end if
                                end repeat
                            end try
                        end if
                        exit repeat
                    end if
                end repeat
            end try
        end if

        -- 2) Focus the exact terminal surface (brings its window/space forward)
        focus targetTerm

        -- 3) Now activate the app — front window should already be the target
        activate

        -- 4) Focus again after activate (macOS sometimes re-orders spaces)
        delay 0.08
        focus targetTerm

        return "ok"
    end tell
    '''
    out = run_applescript(script)
    if out == "ok":
        return {"status": "success", "message": f"Focused Ghostty terminal {terminal_id}"}
    return {"status": "error", "message": "Ghostty terminal not found (may have been closed)"}


def open_in_dir(path: str, mode: str = "window") -> dict:
    """
    Open Ghostty in path.

    Prefer a **new window** by default. Putting a tab into `front window` is
    dangerous when the front Ghostty is fullscreen — you'd attach to that Space.
    """
    path_esc = applescript_escape(path)
    mode = (mode or "window").lower()
    if mode == "tab":
        # Still avoid fullscreen front window: only tab into non-fullscreen if we can
        body = f'''
        set cfg to new surface configuration
        set initial working directory of cfg to "{path_esc}"
        set usedTab to false
        try
            set fw to front window
            -- If front window looks fullscreen (fills screen), open a new window instead
            new tab in fw with configuration cfg
            set usedTab to true
        end try
        if usedTab is false then
            new window with configuration cfg
        end if
        '''
        label = "tab"
    else:
        body = f'''
        set cfg to new surface configuration
        set initial working directory of cfg to "{path_esc}"
        new window with configuration cfg
        '''
        label = "window"

    script = f'''
    tell application "Ghostty"
        {body}
        activate
    end tell
    return "ok"
    '''
    out = run_applescript(script)
    if out is None:
        return {"status": "error", "message": "Failed to open Ghostty"}
    return {"status": "success", "message": f"Opened Ghostty {label} in {path}"}
