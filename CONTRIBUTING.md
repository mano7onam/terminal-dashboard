# Contributing to Terminal Dashboard

Thanks for helping. This project is intentionally small and dependency-free so contributors can ship useful changes without fighting a huge toolchain.

## Code of conduct (short)

- Be respectful and concrete in reviews  
- Prefer small, focused PRs  
- Never commit secrets, session transcripts, or personal paths in fixtures  

---

## Ways to contribute

| Priority | Idea |
|----------|------|
| High | New **terminal scanner** (`terminal_dashboard/scanners/`) |
| High | Better **focus** for best-effort apps / IDE workspaces |
| High | New **agent export** backend (Cursor history, Aider, Continue, …) |
| Medium | **IDE** openers in `ides.py` |
| Medium | UI polish / a11y / i18n |
| Medium | Docs, screenshots, GIF demo |
| Always | Bug reports with macOS version + app version + repro |

---

## Development setup

```bash
git clone https://github.com/mano7onam/terminal-dashboard.git
cd terminal-dashboard

# Run the dashboard
python3 server.py
# → http://localhost:8080

# Optional helpers
make health    # GET /api/health
make scan      # pretty-print /api/terminals (server must be running)
```

**Requirements**

- macOS (core features use AppleScript / process APIs)  
- Python 3.9+  
- No `pip install` for core development  

**Build the desktop app** (optional):

```bash
# needs swiftc (Xcode Command Line Tools)
./scripts/build_dmg.sh
```

See [BUILD.md](BUILD.md).

---

## Project map (where to edit)

| Path | Responsibility |
|------|----------------|
| `terminal_dashboard/scanners/*.py` | Discover + focus one terminal app |
| `terminal_dashboard/export/` | Claude/Codex parsers + md/html/pdf/zip |
| `terminal_dashboard/preview.py` | Session brief (text) |
| `terminal_dashboard/ides.py` | Detect/open IDEs |
| `terminal_dashboard/browser.py` | Reuse browser tab |
| `terminal_dashboard/actions.py` | Focus / open folder / open terminal |
| `terminal_dashboard/httpd.py` | HTTP API + static `index.html` |
| `index.html` | UI |
| `native/StatusBarHost.swift` | Menu bar + Dock host |
| `scripts/build_dmg.sh` | Packaging |

---

## Adding a terminal scanner

1. Create `terminal_dashboard/scanners/myapp.py`:

```python
def scan() -> list[dict]:
    """Return session dicts (may be empty). Never raise — return []."""
    ...

def focus(params: dict) -> dict:
    """Return {"status": "success"|"error", "message": "..."}."""
    ...
```

2. Register in `terminal_dashboard/scanners/__init__.py`:
   - `SCANNERS` list  
   - `detected_apps()` entry  

3. Wire focus in `terminal_dashboard/actions.py` → `FOCUS_HANDLERS`.

4. Add a color in `index.html` → `APP_STYLES`.

5. Document support level in `README.md` (native API vs best-effort).

### Session fields

**Required**

| Field | Type | Notes |
|-------|------|--------|
| `app` | str | Display name |
| `title` | str | Human label |
| `cwd` | str | Absolute path or `"Unknown/Remote"` |
| `active` | bool | Prefer true only for frontmost focused surface |

**Recommended**

| Field | Notes |
|-------|--------|
| `tty` | e.g. `/dev/ttys012` |
| `processes` | Non-shell process names |
| `contents` | Short console snippet (optional) |
| stable ids | `terminalId`, `sessionId`, `paneId`, `windowId` for focus |

`uid` and `folderName` are filled by `finalize_session`.

### Focus quality bar

Prefer, in order:

1. Official scripting API / CLI with **stable IDs**  
2. TTY match  
3. Title / CWD heuristics  

**Never** use bare `activate` on an app that may have a **fullscreen** window before focusing the target — macOS will jump to the wrong Space (Ghostty gotcha).

**Never** rely only on titles that change every second (spinners).

### Process-tree helper

```python
from ..process_utils import sessions_from_app_process_tree, is_app_running

def scan():
    if not is_app_running([r"/MyApp\.app/"]):
        return []
    return sessions_from_app_process_tree("MyApp", [r"/MyApp\.app/"])
```

One broken scanner must not crash the whole list (`scan_all` isolates failures).

---

## Adding an IDE opener

Edit `terminal_dashboard/ides.py` → `_IDE_SPECS`:

- `apps` / `open_a`: `.app` names under `/Applications` or `~/Applications`  
- `cli`: binaries on `PATH` (`code`, `cursor`, `idea`, …)  

Only **installed** IDEs are shown in the UI.

---

## Adding an agent export source

1. Parser under `terminal_dashboard/export/` (or extend `agents.py`)  
2. Title/CWD matching that does **not** steal the “latest session in folder” when titles differ  
3. Wire into `export/service.py`  
4. Document in README  

Do **not** commit real user transcripts in tests — use tiny anonymized fixtures.

---

## UI changes

- Prefer **event delegation** + `data-action` (already used)  
- Don’t put full session JSON into HTML attributes  
- **Select ≠ focus** — never call focus on sidebar click  
- Cache-Control for `index.html` is `no-store` — still ask reviewers to hard-refresh  

Primary actions (purple chips): use sparingly — **Markdown** / **.md** only for export.

---

## Testing checklist (before PR)

- [ ] `python3 server.py` starts; UI loads at `http://localhost:8080`  
- [ ] `/api/health` returns version + apps (+ ides)  
- [ ] Sidebar select does **not** steal focus  
- [ ] **Open this terminal** focuses the intended Ghostty/Terminal (try with one fullscreen Ghostty open)  
- [ ] Export Markdown succeeds for a project with Claude/Codex data (if present)  
- [ ] If you touch packaging: `./scripts/build_dmg.sh` still produces a DMG  

Manual is fine — there is no heavy CI suite yet (PRs that add lightweight tests are welcome).

---

## Pull request process

1. Fork + branch from `main`  
2. Keep the PR focused (one scanner / one fix)  
3. Fill the PR description:
   - What / why  
   - Apps tested + **macOS version**  
   - Screenshots if UI changed  
4. Link related issues  

### Good PR title examples

- `feat(scanners): add Rio terminal support`  
- `fix(ghostty): avoid fullscreen Space on activate`  
- `docs: Gatekeeper steps for DMG install`  

---

## Reporting bugs

Include:

- Terminal Dashboard version (`/api/health` → `version`)  
- macOS version  
- Terminal apps involved (Ghostty version helps)  
- Steps to reproduce  
- Expected vs actual  
- Relevant logs from Console / `dist/swiftc.log` only if packaging-related  

Security-sensitive issues: see [SECURITY.md](SECURITY.md).

---

## License

By contributing, you agree your contributions are licensed under the MIT License (same as the project).
