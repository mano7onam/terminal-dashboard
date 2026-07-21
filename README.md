# Terminal Dashboard

### See every terminal on your Mac — grouped by project. Focus. Export. Hand off to another agent.

[![macOS](https://img.shields.io/badge/platform-macOS-000000?logo=apple&logoColor=white)](#requirements)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](#requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![No npm](https://img.shields.io/badge/deps-stdlib%20only-informational)](#requirements)

**Ghostty · Terminal.app · iTerm2 · Warp · WezTerm · Kitty · tmux · VS Code / Cursor / JetBrains integrated terminals**

Zero npm. Zero pip packages for daily use. One local Python server + a clean web UI.

---

## The problem

If you live in terminals (and coding agents), you eventually have:

| Chaos | What you wanted |
|-------|-----------------|
| 6 Ghostty windows, 2 in the same repo | Jump to the *right* one |
| VS Code + Cursor shells still running jobs | See them by project folder |
| Claude Code chat you need in Codex tomorrow | Export full transcript as Markdown |
| “Which port was the dashboard on?” | Menu bar: Open / Copy URL / Quit |

**Terminal Dashboard** is a local macOS tool: scan → group by folder → inspect → open → export.

---

## Features at a glance

| | |
|--|--|
| **Project sidebar** | All sessions grouped by working directory |
| **Select ≠ open** | Click to inspect; explicit **Open this terminal** to focus |
| **Session brief** | Title, path, processes, recent lines, matched agent chat — no Screen Recording |
| **New terminal** | Ghostty or Terminal.app in any folder (Browse… dialog) |
| **Open in IDE** | Only IDEs you have installed (VS Code, Cursor, PyCharm, IDEA, Zed, …) |
| **Export** | Markdown (primary), text, HTML, PDF, JSON, ZIP — Claude Code & Codex aware |
| **Desktop app** | Optional `.app` + DMG: Dock + menu bar, reuse browser tab |

---

## Demo (mental model)

```
┌─────────────┐     inspect      ┌──────────────────────────┐
│  Sidebar    │ ───────────────► │  Session detail          │
│  by folder  │                  │  · brief / recent output │
│             │   Open terminal  │  · focus / Finder / IDEs │
│             │ ───────────────► │  · export Markdown       │
└─────────────┘                  └──────────────────────────┘
```

> **Tip for screenshots:** a short GIF of “select session → copy Markdown → paste into another agent” converts better than feature lists alone. Drop one in `docs/` when you can.

---

## Quick start (from source) — 30 seconds

```bash
git clone https://github.com/mano7onam/terminal-dashboard.git
cd terminal-dashboard
python3 server.py
```

Open **http://localhost:8080**

```bash
python3 server.py --port 9090          # custom port
python3 -m terminal_dashboard          # same entry
make run
```

### Requirements

- **macOS** 11+
- **Python 3.9+** (system / Xcode CLT / python.org)
- **Automation** when macOS prompts (control terminals, optional browser tab reuse)

No `pip install` for core use.

---

## Install the macOS app (DMG)

If a release includes a DMG (or you built one with `./scripts/build_dmg.sh`):

### 1. Open the disk image

```bash
open Terminal-Dashboard-*.dmg
# or double-click the file in Finder
```

### 2. Install

Drag **Terminal Dashboard** onto **Applications** (classic macOS layout).

### 3. First launch & Gatekeeper (important)

Apple does **not** distribute this app via the App Store. Unsigned or ad-hoc signed builds are **blocked by default**. That is normal.

**If macOS says the app “can’t be opened” / “unidentified developer”:**

#### Option A — Right‑click Open (recommended once)

1. Open **Finder → Applications**
2. **Right‑click** (or Control‑click) **Terminal Dashboard**
3. Choose **Open**
4. In the dialog, click **Open** again  

After that, normal double‑click usually works.

#### Option B — System Settings

1. Try to open the app once (it may fail)
2. **System Settings → Privacy & Security**
3. Scroll to the message about Terminal Dashboard
4. Click **Open Anyway**
5. Confirm **Open**

#### Option C — Terminal (if A/B fail)

```bash
# Remove quarantine flag from a downloaded DMG/app
xattr -dr com.apple.quarantine "/Applications/Terminal Dashboard.app"

# Then open
open -a "Terminal Dashboard"
```

Only do this for builds you trust (your own release or a known GitHub Release).

### 4. Permissions after install

When macOS asks, allow:

| Permission | Why |
|------------|-----|
| **Automation** (Ghostty, Terminal, browser, System Events) | List / focus sessions, export, folder picker, reuse browser tab |
| **Accessibility** (optional) | Some window / picker fallbacks |

**Screen Recording is not required.**

### 5. Using the app

| UI | Action |
|----|--------|
| **Dock** | Stays while the app runs; click again → open dashboard in browser |
| **Menu bar** (top-right) | **Open Dashboard (reuse tab)** · **Open in New Tab** · **Copy URL** · **Quit** |
| **Quit** | Stops the local server completely |

You never need to remember the port — use **Copy Dashboard URL** or **Open Dashboard**.

Building the `.app` yourself needs **swiftc** (Xcode Command Line Tools).  
Details: **[BUILD.md](BUILD.md)**.

---

## How to use (web UI)

1. **Left** — projects & terminals (click = inspect only)  
2. **Open this terminal** — focus the real app (or open the IDE on that folder for VS Code/Cursor shells)  
3. **What’s in this session** — short brief: path, processes, recent lines, matched agent chat  
4. **Save & copy** — **Markdown** is the main handoff format  
5. **New terminal in folder…** — any path → Ghostty or Terminal.app  

---

## Export agent chats (killer feature)

Paste a full Claude Code / Codex conversation into another agent:

| Button | Use for |
|--------|---------|
| **Markdown** (highlighted) | Best default for handoff |
| Plain text | Logs / tickets |
| `.md` download | Keep a file |
| `.html` / `.pdf` / `.json` / `.zip` | Archives & tooling |

**Sources**

- Claude Code: `~/.claude/projects/…/*.jsonl` (folder + title match)  
- Codex: `~/.codex/sessions/**/rollout-*.jsonl`  
- Terminal history: Terminal / iTerm / tmux / WezTerm / Kitty when APIs allow  

---

## Local API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/terminals` | All sessions |
| `GET` | `/api/health` | Version, apps, IDEs |
| `GET` | `/api/ides` | Installed IDEs |
| `POST` | `/api/focus` | Focus session / open IDE workspace |
| `POST` | `/api/open_terminal` | New Ghostty / Terminal in a path |
| `POST` | `/api/open_dir` | Finder / IDE / terminal |
| `POST` | `/api/export` | Export transcript |
| `POST` | `/api/preview` | Session brief |
| `POST` | `/api/open_browser` | `{ mode: "reuse" \| "new" }` |

```bash
curl -s http://localhost:8080/api/health | python3 -m json.tool
```

---

## Project layout

```text
server.py                      # python3 server.py
index.html                     # dashboard UI
terminal_dashboard/
  scanners/                    # one file per terminal app  ← easy PRs
  export/                      # Claude/Codex + formats
  preview.py                   # session brief
  ides.py                      # detect / open IDEs
  browser.py                   # reuse browser tab
native/StatusBarHost.swift     # Dock + menu bar host
scripts/build_dmg.sh           # app + DMG
CONTRIBUTING.md                # how to contribute
BUILD.md                       # packaging details
```

---

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| Empty list | Open at least one terminal; open `/api/health` |
| App “can’t be opened” | [Gatekeeper steps](#3-first-launch--gatekeeper-important) |
| Wrong Ghostty window / fullscreen | Update to latest; focus order was fixed |
| Browse… fails | Automation for osascript; or paste path |
| Port in use | `python3 server.py --port 8081` |
| Too many browser tabs | Menu: **Open Dashboard (reuse tab)** |
| UI looks outdated | Hard refresh **Cmd+Shift+R** or close tab and reopen |

---

## Contributing

We want this to be the default “terminal cockpit” for agent-heavy macOS workflows.

**High-impact PR ideas**

- Scanner for another terminal / IDE  
- Better title matching for agent exports  
- Linux (Kitty / WezTerm / tmux)  
- Screenshots / GIF for the README  
- Homebrew cask (after a stable release)  

**Full guide:** **[CONTRIBUTING.md](CONTRIBUTING.md)**  
(setup, scanner checklist, PR template expectations, code style)

```bash
git clone https://github.com/mano7onam/terminal-dashboard.git
cd terminal-dashboard
python3 server.py
# edit → test → open a PR
```

---

## Star if this saved you a context switch

If Terminal Dashboard uncluttered your Ghostty/iTerm/agent setup, a ⭐ helps others find it — and motivates more scanners and releases.

Issues and PRs are welcome. Be kind; macOS Automation is finicky enough already.

---

## License

[MIT](LICENSE) — free to use, fork, and ship.

---

## Topics (for GitHub)

Suggested repository topics:

`macos` · `terminal` · `ghostty` · `iterm2` · `tmux` · `developer-tools` · `claude-code` · `codex` · `productivity` · `python` · `dashboard` · `warp` · `kitty`
