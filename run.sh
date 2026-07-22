#!/usr/bin/env bash
# Start Terminal Dashboard as a native app window (WKWebView) by default.
# Use BROWSER=1 to open a browser tab instead.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8080}"
MODE_ARGS=()
if [[ "${BROWSER:-0}" == "1" ]] || [[ "${1:-}" == "--browser" ]]; then
  MODE_ARGS+=(--browser)
elif [[ "${1:-}" == "--no-open" ]]; then
  MODE_ARGS+=(--no-open)
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use."
  echo "Open app window / browser for http://localhost:$PORT"
  if [[ "${BROWSER:-0}" == "1" ]]; then
    open "http://localhost:$PORT" 2>/dev/null || true
  else
    python3 -c "from terminal_dashboard.app_window import open_app_window; open_app_window('http://127.0.0.1:$PORT')" 2>/dev/null \
      || open "http://localhost:$PORT" 2>/dev/null || true
  fi
  exit 0
fi

exec python3 -m terminal_dashboard --port "$PORT" "${MODE_ARGS[@]}"
