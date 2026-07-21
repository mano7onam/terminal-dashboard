"""tmux panes via CLI."""

from __future__ import annotations

from typing import List

from ..process_utils import get_processes_for_tty, normalize_path, run_cmd, which
from ..scripting import run_jxa


def scan() -> List[dict]:
    if not which("tmux"):
        return []
    out = run_cmd([
        "tmux", "list-panes", "-a",
        "-F",
        "#{session_name}||#{window_index}||#{pane_index}||#{pane_tty}||"
        "#{pane_current_path}||#{window_name}||#{pane_active}||#{window_active}||#{session_attached}",
    ])
    if not out:
        return []

    sessions = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split("||")
        if len(parts) < 6:
            continue
        sess_name, win_idx, pane_idx, pane_tty, pane_path, win_name = parts[:6]
        pane_active = parts[6] == "1" if len(parts) > 6 else True
        window_active = parts[7] == "1" if len(parts) > 7 else True
        session_attached = parts[8] != "0" if len(parts) > 8 else True

        snippet = ""
        cap = run_cmd(["tmux", "capture-pane", "-p", "-t", f"{sess_name}:{win_idx}.{pane_idx}"])
        if cap:
            snippet = "\n".join(cap.splitlines()[-15:])

        pane_path_n = normalize_path(pane_path) or pane_path
        sessions.append({
            "app": "Tmux",
            "sessionName": sess_name,
            "windowIndex": int(win_idx),
            "paneIndex": int(pane_idx),
            "tty": pane_tty,
            "title": f"tmux {sess_name}:{win_idx} ({win_name})",
            "active": bool(pane_active and window_active and session_attached),
            "contents": snippet,
            "cwd": pane_path_n or "Unknown/Remote",
            "processes": get_processes_for_tty(pane_tty),
        })
    return sessions


def focus(params: dict) -> dict:
    import json

    session_name = params.get("sessionName")
    window_index = params.get("windowIndex")
    pane_index = params.get("paneIndex")
    if not session_name:
        return {"status": "error", "message": "Missing tmux session name"}

    target = f"{session_name}:{window_index}.{pane_index}" if window_index is not None else session_name
    if window_index is not None:
        run_cmd(["tmux", "select-window", "-t", f"{session_name}:{window_index}"])
        if pane_index is not None:
            run_cmd(["tmux", "select-pane", "-t", target])
    else:
        run_cmd(["tmux", "switch-client", "-t", session_name])

    clients = run_cmd(["tmux", "list-clients", "-t", session_name, "-F", "#{client_tty}"])
    client_ttys = [l.strip() for l in (clients or "").splitlines() if l.strip()]

    if client_ttys:
        # Discover host Terminal/iTerm sessions and focus matching TTY
        from . import iterm, terminal_app
        hosts = []
        try:
            hosts.extend(terminal_app.scan())
        except Exception:
            pass
        try:
            hosts.extend(iterm.scan())
        except Exception:
            pass
        for tty in client_ttys:
            full = tty if tty.startswith("/dev/") else f"/dev/{tty}"
            for term in hosts:
                if term.get("tty") in (full, tty):
                    if term["app"] == "Terminal":
                        return terminal_app.focus(term)
                    if term["app"] == "iTerm2":
                        return iterm.focus(term)

    # Fallback: attach in new Terminal window
    attach = f"tmux attach -t {json.dumps(session_name)[1:-1]}"
    if window_index is not None:
        attach = f"tmux attach -t {session_name} \\; select-window -t {window_index}"
        if pane_index is not None:
            attach += f" \\; select-pane -t {pane_index}"
    jxa = f"""
    var app = Application("Terminal");
    app.activate();
    app.doScript({json.dumps(attach)});
    """
    run_jxa(jxa)
    return {"status": "success", "message": f"Attached to tmux {target}"}
