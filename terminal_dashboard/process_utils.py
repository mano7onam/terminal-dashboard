"""Process / TTY / CWD helpers shared by all scanners."""

from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

SHELL_NAMES = frozenset({
    "zsh", "bash", "fish", "sh", "dash", "ksh", "tcsh", "csh",
    "-zsh", "-bash", "-fish", "-sh", "login",
})

IGNORE_PROCS = SHELL_NAMES | frozenset({
    "ps", "pgrep", "lsof", "osascript", "which", "tmux", "sshd",
    "login", "getty", "script", "script_sink",
})


def run_cmd(cmd: List[str], timeout: float = 8.0) -> Optional[str]:
    try:
        out = subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL, timeout=timeout,
        )
        return out
    except Exception:
        return None


def which(binary: str) -> Optional[str]:
    out = run_cmd(["which", binary])
    if not out:
        return None
    path = out.strip().splitlines()[0].strip()
    return path or None


def normalize_path(path: Optional[str]) -> Optional[str]:
    if not path or path in ("Unknown/Remote", "None", "null"):
        return None
    path = path.strip()
    if not path:
        return None
    path = os.path.expanduser(path)
    try:
        if os.path.isdir(path):
            return os.path.realpath(path)
    except OSError:
        pass
    return os.path.normpath(path)


def folder_name_for(path: Optional[str]) -> str:
    if not path:
        return "Remote/System"
    base = os.path.basename(path.rstrip("/"))
    return base or path


def full_tty(tty: Optional[str]) -> Optional[str]:
    if not tty or tty in ("??", "?", "-", " "):
        return None
    tty = tty.strip()
    if tty.startswith("/dev/"):
        return tty
    return f"/dev/{tty}"


def is_app_running(patterns: List[str]) -> bool:
    """True if any process command line matches one of the regex patterns."""
    out = run_cmd(["ps", "-Ax", "-o", "command="])
    if not out:
        return False
    for pat in patterns:
        if re.search(pat, out, re.IGNORECASE):
            return True
    return False


def app_installed(app_names: List[str]) -> bool:
    for name in app_names:
        for base in ("/Applications", "/System/Applications/Utilities",
                     os.path.expanduser("~/Applications")):
            if os.path.isdir(os.path.join(base, f"{name}.app")):
                return True
    return False


@lru_cache(maxsize=1)
def get_process_table() -> Dict[int, dict]:
    """pid -> {ppid, tty, comm, command}."""
    pid_to_info: Dict[int, dict] = {}
    out = run_cmd(["ps", "-A", "-o", "pid=,ppid=,tty=,comm="])
    if not out:
        return pid_to_info
    for line in out.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        tty = parts[2]
        comm = parts[3].split("/")[-1]
        pid_to_info[pid] = {"ppid": ppid, "tty": tty, "comm": comm}
    return pid_to_info


def clear_process_cache() -> None:
    get_process_table.cache_clear()
    get_shell_cwds.cache_clear()


@lru_cache(maxsize=1)
def get_shell_cwds() -> Dict[int, str]:
    """shell pid -> normalized cwd."""
    pid_to_cwd: Dict[int, str] = {}
    out = run_cmd([
        "lsof", "-a", "-d", "cwd", "-Fn",
        "-c", "zsh", "-c", "bash", "-c", "fish", "-c", "sh", "-c", "dash", "-c", "ksh",
    ])
    if not out:
        return pid_to_cwd
    current_pid = None
    is_cwd = False
    for line in out.splitlines():
        if line.startswith("p"):
            try:
                current_pid = int(line[1:])
            except ValueError:
                current_pid = None
            is_cwd = False
        elif line.startswith("f"):
            is_cwd = line[1:].strip() == "cwd"
        elif line.startswith("n") and is_cwd and current_pid is not None:
            raw = line[1:].strip()
            pid_to_cwd[current_pid] = normalize_path(raw) or raw
            is_cwd = False
    return pid_to_cwd


def get_cwd_for_pid(pid: int) -> Optional[str]:
    shells = get_shell_cwds()
    if pid in shells:
        return shells[pid]
    out = run_cmd(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    if not out:
        return None
    is_cwd = False
    for line in out.splitlines():
        if line.startswith("f"):
            is_cwd = line[1:].strip() == "cwd"
        elif line.startswith("n") and is_cwd:
            return normalize_path(line[1:].strip()) or line[1:].strip()
    return None


def get_tty_to_cwd() -> Dict[str, str]:
    """Prefer highest-PID shell on each TTY."""
    pid_to_cwd = get_shell_cwds()
    pid_to_info = get_process_table()
    best: Dict[str, Tuple[int, str]] = {}
    for pid, cwd in pid_to_cwd.items():
        info = pid_to_info.get(pid)
        if not info:
            continue
        tty = full_tty(info["tty"])
        if not tty:
            continue
        prev = best.get(tty)
        if prev is None or pid > prev[0]:
            best[tty] = (pid, cwd)
    return {t: c for t, (_, c) in best.items()}


def get_cwd_for_tty(tty: Optional[str]) -> Optional[str]:
    if not tty:
        return None
    mapped = get_tty_to_cwd().get(tty if tty.startswith("/dev/") else f"/dev/{tty}")
    if mapped:
        return mapped
    tty_name = tty.replace("/dev/", "")
    out = run_cmd(["ps", "-t", tty_name, "-o", "pid="])
    if not out:
        return None
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            try:
                pids.append(int(line))
            except ValueError:
                pass
    for pid in sorted(pids, reverse=True):
        cwd = get_cwd_for_pid(pid)
        if cwd:
            return cwd
    return None


def get_processes_for_tty(tty: Optional[str]) -> List[str]:
    if not tty:
        return []
    tty_name = tty.replace("/dev/", "")
    out = run_cmd(["ps", "-t", tty_name, "-o", "comm="])
    if not out:
        return []
    seen = set()
    commands: List[str] = []
    for line in out.splitlines():
        comm = line.strip().split("/")[-1]
        if not comm or comm in IGNORE_PROCS or comm in seen:
            continue
        seen.add(comm)
        commands.append(comm)
    return commands


def pids_matching(pattern: str) -> List[int]:
    out = run_cmd(["pgrep", "-f", pattern])
    if not out:
        return []
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            try:
                pids.append(int(line))
            except ValueError:
                pass
    return pids


def descendant_pids(root_pids: Set[int], pid_to_info: Optional[Dict[int, dict]] = None) -> Set[int]:
    if pid_to_info is None:
        pid_to_info = get_process_table()
    children: Dict[int, List[int]] = {}
    for pid, info in pid_to_info.items():
        children.setdefault(info["ppid"], []).append(pid)

    found: Set[int] = set()
    stack = list(root_pids)
    while stack:
        pid = stack.pop()
        if pid in found:
            continue
        found.add(pid)
        stack.extend(children.get(pid, []))
    return found


def sessions_from_app_process_tree(
    app_name: str,
    root_patterns: List[str],
    title_prefix: Optional[str] = None,
) -> List[dict]:
    """
    Generic scanner: find root app PIDs, walk descendants, group shell TTYs into sessions.
    Works for Warp, Alacritty, Hyper, Tabby, Rio, Kitty (fallback), etc.
    """
    roots: Set[int] = set()
    for pat in root_patterns:
        roots.update(pids_matching(pat))
    if not roots:
        return []

    pid_to_info = get_process_table()
    pid_to_cwd = get_shell_cwds()
    descendants = descendant_pids(roots, pid_to_info)

    # tty -> best shell pid
    tty_shell: Dict[str, int] = {}
    tty_procs: Dict[str, List[str]] = {}

    for pid in descendants:
        info = pid_to_info.get(pid)
        if not info:
            continue
        tty = full_tty(info["tty"])
        if not tty:
            continue
        comm = info["comm"]
        if comm in SHELL_NAMES or pid in pid_to_cwd:
            prev = tty_shell.get(tty)
            if prev is None or pid > prev:
                tty_shell[tty] = pid
        if comm not in IGNORE_PROCS:
            lst = tty_procs.setdefault(tty, [])
            if comm not in lst:
                lst.append(comm)

    sessions = []
    for tty, shell_pid in sorted(tty_shell.items()):
        cwd = pid_to_cwd.get(shell_pid) or get_cwd_for_tty(tty)
        cwd_n = normalize_path(cwd) if cwd else None
        folder = folder_name_for(cwd_n)
        tty_short = tty.replace("/dev/", "") if tty else ""
        base = title_prefix or app_name
        if cwd_n:
            title = f"{base} · {folder}"
        else:
            title = base
        if tty_short:
            title = f"{title} ({tty_short})"
        sessions.append({
            "app": app_name,
            "tty": tty,
            "title": title,
            "active": False,
            "contents": "",
            "cwd": cwd_n or "Unknown/Remote",
            "folderName": folder,
            "processes": tty_procs.get(tty, []),
            "shellPid": shell_pid,
        })
    return sessions


def activate_app_by_name(app_name: str) -> bool:
    """Bring an app to front via AppleScript (works for most GUI apps)."""
    from .scripting import run_applescript, applescript_escape
    esc = applescript_escape(app_name)
    out = run_applescript(f'''
    tell application "{esc}"
        activate
    end tell
    return "ok"
    ''')
    return out == "ok"


def focus_window_by_title_hint(app_name: str, hints: List[str]) -> bool:
    """
    Activate app and raise a window whose AX title contains any hint.
    Best-effort for apps without a scripting dictionary.
    """
    from .scripting import run_jxa, jxa_escape
    hints_js = "[" + ", ".join(f'"{jxa_escape(h)}"' for h in hints if h) + "]"
    jxa = f"""
    var appName = "{jxa_escape(app_name)}";
    var hints = {hints_js};
    try {{
        var app = Application(appName);
        app.activate();
    }} catch (e) {{}}
    try {{
        var sys = Application("System Events");
        var procs = sys.processes.whose({{name: appName}});
        if (procs.length === 0) return "no_proc";
        var proc = procs[0];
        var windows = proc.windows();
        if (!windows.length) return "no_win";
        var best = null;
        for (var i = 0; i < windows.length; i++) {{
            var w = windows[i];
            var title = "";
            try {{ title = w.name(); }} catch (e) {{}}
            var hit = false;
            for (var h = 0; h < hints.length; h++) {{
                if (hints[h] && title.toLowerCase().indexOf(String(hints[h]).toLowerCase()) !== -1) {{
                    hit = true; break;
                }}
            }}
            if (hit) {{ best = w; break; }}
        }}
        if (!best) best = windows[0];
        try {{ best.actions.byName("AXRaise").perform(); }} catch (e) {{}}
        try {{ best.attributes.byName("AXMain").value = true; }} catch (e) {{}}
        return "ok";
    }} catch (e) {{
        return "err:" + String(e);
    }}
    """
    return (run_jxa(jxa) or "").startswith("ok")
