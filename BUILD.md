# Building Terminal Dashboard

## Run from source

```bash
python3 server.py
# → http://localhost:8080
```

Requirements: macOS, Python 3.9+, Automation permissions for terminal apps.

---

## Package as `.app` + `.dmg` (classic macOS install)

[Handy](https://github.com/cjpais/Handy) uses Tauri for its DMG. We stay on **stdlib Python**, but ship the same user experience:

1. **`Terminal Dashboard.app`** — Dock icon + **status window** (Open Dashboard / Quit) + local server + browser UI  
2. **`Terminal-Dashboard-<version>.dmg`** — **drag app → Applications** layout (not a random folder dump)

### Build

```bash
./scripts/build_dmg.sh
# optional ad-hoc signature:
./scripts/build_dmg.sh --sign
```

Output:

```
dist/Terminal Dashboard.app
dist/Terminal-Dashboard-1.2.0.dmg
```

### Install (what you should see)

```bash
open dist/Terminal-Dashboard-*.dmg
```

Finder opens a window roughly like:

```
┌─────────────────────────────────────┐
│                                     │
│   [ Terminal Dashboard ]  →  [ Applications ]
│         .app                      folder
│                                     │
│     Drag the app onto Applications  │
└─────────────────────────────────────┘
```

Then open **Terminal Dashboard** from Applications / Launchpad.

### What happens when you launch the app

1. **Dock** shows Terminal Dashboard (native Swift host — not bare Python)  
2. **Menu bar** (top-right): Open Dashboard · Copy URL · **Quit**  
3. Python server starts on port 8080 (or free port)  
4. Browser opens the dashboard once  
5. Click Dock icon again → re-opens browser with the correct URL/port  

Requires system **python3** to *run*. Building the app needs `swiftc` (Xcode CLT).

### First launch (unsigned)

Gatekeeper may block unsigned apps:

1. Right-click the app → **Open** → **Open**  
2. Or: System Settings → Privacy & Security → **Open Anyway**

### Permissions after install

| Permission | Why |
|------------|-----|
| **Automation** | Control Ghostty / Terminal / System Events |
| **Screen Recording** | Ghostty window snapshots |
| **Accessibility** (optional) | Window bounds / folder picker fallback |

---

## Optional: full native shell like Handy (Tauri)

If you want a real WKWebView window instead of an external browser (Handy model):

1. Scaffold Tauri 2 app with the existing `index.html` as the frontend
2. Call the Python backend as a sidecar, **or** reimplement scanners in Rust
3. `bun run tauri build` → DMG with `bundle.targets: ["dmg", "app"]`

That’s a larger rewrite; the shell script above is the lightweight equivalent for this codebase.

---

## CI idea

```yaml
# .github/workflows/release.yml (sketch)
# runs-on: macos-latest
# - run: ./scripts/build_dmg.sh
# - uses: softprops/action-gh-release@v2
#   with:
#     files: dist/*.dmg
```
