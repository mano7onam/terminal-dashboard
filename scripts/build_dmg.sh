#!/usr/bin/env bash
# Build Terminal Dashboard.app + a classic macOS DMG
# (app icon on the left, Applications on the right — drag to install).
#
# Usage:
#   ./scripts/build_dmg.sh
#   ./scripts/build_dmg.sh --sign
#
# Output:
#   dist/Terminal Dashboard.app
#   dist/Terminal-Dashboard-<version>.dmg

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_NAME="Terminal Dashboard"
BUNDLE_ID="dev.terminaldashboard.app"
VERSION="$(python3 -c "from terminal_dashboard.version import __version__; print(__version__)")"
DIST="$ROOT/dist"
APP="$DIST/${APP_NAME}.app"
DMG_NAME="Terminal-Dashboard-${VERSION}.dmg"
DMG="$DIST/$DMG_NAME"
RW_DMG="$DIST/_rw.dmg"
VOL_NAME="Terminal Dashboard"
SIGN=0

for arg in "$@"; do
  case "$arg" in
    --sign) SIGN=1 ;;
    -h|--help) echo "Usage: $0 [--sign]"; exit 0 ;;
  esac
done

echo "==> Building $APP_NAME v$VERSION"
rm -rf "$APP" "$DMG" "$RW_DMG" "$DIST/dmg-stage" "$DIST/AppIcon.iconset"
mkdir -p "$APP/Contents/MacOS" \
         "$APP/Contents/Resources" \
         "$APP/Contents/Resources/app" \
         "$DIST"

# ── Payload ──────────────────────────────────────────────────────────────
rsync -a \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
  --exclude 'dist' --exclude '*.dmg' \
  "$ROOT/terminal_dashboard" "$APP/Contents/Resources/app/"

cp "$ROOT/index.html" "$ROOT/server.py" "$APP/Contents/Resources/app/"
cp "$ROOT/LICENSE" "$APP/Contents/Resources/app/" 2>/dev/null || true
mkdir -p "$APP/Contents/Resources/app/assets"
if [[ -f "$ROOT/assets/AppIcon-1024.png" ]]; then
  cp "$ROOT/assets/AppIcon-1024.png" "$APP/Contents/Resources/app/assets/"
fi

# ── Native host (Swift): menu bar + Dock, spawns Python server ───────────
echo "==> Compiling native host (Swift: menu bar + WKWebView app window)"
python3 "$ROOT/scripts/make_menubar_icon.py"
swiftc -O \
  -target "arm64-apple-macosx11.0" \
  -framework WebKit -framework Cocoa \
  "$ROOT/native/StatusBarHost.swift" \
  -o "$APP/Contents/MacOS/Terminal Dashboard" \
  2>"$DIST/swiftc.log" || {
    # Fallback: also try universal / default target
    echo "warn: arm64 build failed, trying default target (see dist/swiftc.log)"
    swiftc -O -framework WebKit -framework Cocoa \
      "$ROOT/native/StatusBarHost.swift" \
      -o "$APP/Contents/MacOS/Terminal Dashboard"
  }
chmod +x "$APP/Contents/MacOS/Terminal Dashboard"

# Standalone WebView helper for python -m / run.sh (optional, cached under Resources)
swiftc -O -framework WebKit -framework Cocoa \
  "$ROOT/native/StandaloneWebView.swift" \
  -o "$APP/Contents/Resources/TerminalDashboardWebView" 2>/dev/null || true
if [[ -x "$APP/Contents/Resources/TerminalDashboardWebView" ]]; then
  chmod +x "$APP/Contents/Resources/TerminalDashboardWebView"
fi

# Menu bar template icon
if [[ -f "$ROOT/assets/MenuBarIcon.png" ]]; then
  cp "$ROOT/assets/MenuBarIcon.png" "$APP/Contents/Resources/MenuBarIcon.png"
fi

# ── Info.plist ───────────────────────────────────────────────────────────
cat > "$APP/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleVersion</key>
  <string>${VERSION}</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>Terminal Dashboard</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>LSUIElement</key>
  <false/>
  <key>NSSupportsAutomaticGraphicsSwitching</key>
  <true/>
  <key>NSAppleEventsUsageDescription</key>
  <string>Terminal Dashboard controls terminal apps to list, focus, preview, and export sessions.</string>
  <key>NSAppleScriptEnabled</key>
  <true/>
  <key>CFBundleDocumentTypes</key>
  <array/>
</dict>
</plist>
PLIST
echo -n 'APPL????' > "$APP/Contents/PkgInfo"

# ── App icon (.icns) ─────────────────────────────────────────────────────
ICON_SRC="$ROOT/assets/AppIcon-1024.png"
if [[ ! -f "$ICON_SRC" ]]; then
  echo "warn: no assets/AppIcon-1024.png — generating placeholder"
  python3 - <<'PY'
import struct, zlib, pathlib
w = h = 1024
r, g, b, a = 79, 70, 229, 255
row = bytes([0] + [r, g, b, a] * w)
raw = row * h
def chunk(tag, data):
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(raw, 9))
png += chunk(b'IEND', b'')
pathlib.Path("assets").mkdir(exist_ok=True)
pathlib.Path("assets/AppIcon-1024.png").write_bytes(png)
PY
  ICON_SRC="$ROOT/assets/AppIcon-1024.png"
fi

ICONSET="$DIST/AppIcon.iconset"
mkdir -p "$ICONSET"
for sz in 16 32 128 256 512; do
  sips -z "$sz" "$sz" "$ICON_SRC" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null
  sips -z $((sz * 2)) $((sz * 2)) "$ICON_SRC" --out "$ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
cp "$ICON_SRC" "$APP/Contents/Resources/AppIcon.png" 2>/dev/null || true

if [[ "$SIGN" -eq 1 ]]; then
  echo "==> Ad-hoc codesign"
  codesign --force --deep --sign - "$APP" || true
fi

# ── DMG background ───────────────────────────────────────────────────────
BG="$DIST/dmg-background.png"
python3 - <<'PY'
# Simple 600x400 dark background with subtle hint of arrow space
import struct, zlib, pathlib
w, h = 600, 400
# dark slate
pixels = bytearray()
for y in range(h):
    pixels.append(0)  # filter
    for x in range(w):
        # slight gradient
        t = y / h
        r = int(15 + 10 * t)
        g = int(23 + 12 * t)
        b = int(42 + 18 * t)
        # soft violet glow center-right for Applications side
        cx, cy = 420, 200
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if d < 120:
            f = (120 - d) / 120 * 0.15
            r = min(255, int(r + 99 * f))
            g = min(255, int(g + 102 * f))
            b = min(255, int(b + 241 * f))
        pixels.extend([r, g, b, 255])
raw = bytes(pixels)
def chunk(tag, data):
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(raw, 9))
png += chunk(b'IEND', b'')
pathlib.Path("dist/dmg-background.png").write_bytes(png)
print("bg ok")
PY

# ── Create RW DMG, layout icons, convert to compressed ───────────────────
echo "==> Creating DMG (drag-to-Applications layout)"

# Detach any previous volumes with the same name (common when rebuilding)
for v in "/Volumes/${VOL_NAME}" "/Volumes/${VOL_NAME} 1" "/Volumes/${VOL_NAME} 2"; do
  hdiutil detach "$v" -force >/dev/null 2>&1 || true
done
rm -f "$RW_DMG" "$DMG"

# Size: app is small; leave headroom. Explicit UDRW so it is writeable when mounted.
hdiutil create \
  -size 64m \
  -fs HFS+ \
  -volname "$VOL_NAME" \
  -type UDIF \
  -ov \
  "$RW_DMG" >/dev/null

ATTACH_OUT="$(hdiutil attach -readwrite -noverify -noautoopen "$RW_DMG")"
echo "$ATTACH_OUT"
DEVICE="$(echo "$ATTACH_OUT" | awk 'NF>=1 && $1 ~ /^\/dev\// {dev=$1} END {print dev}')"
MOUNT="/Volumes/$VOL_NAME"

# Wait for mount (and ensure writeable)
for _ in $(seq 1 40); do
  if [[ -d "$MOUNT" ]] && touch "$MOUNT/.write_test" 2>/dev/null; then
    rm -f "$MOUNT/.write_test"
    break
  fi
  sleep 0.1
done
if [[ ! -d "$MOUNT" ]]; then
  echo "error: failed to mount DMG at $MOUNT" >&2
  exit 1
fi
if ! touch "$MOUNT/.write_test" 2>/dev/null; then
  echo "error: volume is read-only: $MOUNT" >&2
  hdiutil detach "$MOUNT" -force >/dev/null 2>&1 || true
  exit 1
fi
rm -f "$MOUNT/.write_test"

# Copy contents
ditto "$APP" "$MOUNT/${APP_NAME}.app"
ln -sf /Applications "$MOUNT/Applications"
mkdir -p "$MOUNT/.background"
cp "$BG" "$MOUNT/.background/background.png"

# Finder view options — classic installer window
# shellcheck disable=SC2088
osascript <<EOF
tell application "Finder"
  tell disk "$VOL_NAME"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {200, 120, 800, 520}
    set viewOptions to the icon view options of container window
    set arrangement of viewOptions to not arranged
    set icon size of viewOptions to 128
    set background picture of viewOptions to file ".background:background.png"
    -- positions in window coordinates
    set position of item "${APP_NAME}.app" of container window to {140, 200}
    set position of item "Applications" of container window to {460, 200}
    update without registering applications
    delay 1
    close
    open
    delay 0.5
  end tell
end tell
EOF

sync
# Detach
hdiutil detach "$DEVICE" -quiet || hdiutil detach "$MOUNT" -force -quiet
sleep 0.5

# Compress to final UDZO
rm -f "$DMG"
hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG" >/dev/null
rm -f "$RW_DMG"
rm -rf "$ICONSET"

# Optional: bless for auto-open (best-effort)
# hdiutil internet-enable was removed on newer macOS

echo ""
echo "✓ Done"
echo "  App:  $APP"
echo "  DMG:  $DMG"
echo ""
echo "Install:"
echo "  open \"$DMG\""
echo "  → drag «${APP_NAME}» onto «Applications»"
echo ""
echo "Then open from Launchpad / Applications."
echo "A status window stays open while the server runs; Quit stops it."
