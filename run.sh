#!/usr/bin/env bash
# Start Terminal Dashboard and open the browser (macOS).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8080}"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use."
  echo "Open http://localhost:$PORT  or  PORT=8081 ./run.sh"
  open "http://localhost:$PORT" 2>/dev/null || true
  exit 0
fi

python3 server.py --port "$PORT" &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT INT TERM

# wait until the server answers
for _ in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.15
done

open "http://localhost:$PORT" 2>/dev/null || true
echo "Terminal Dashboard → http://localhost:$PORT  (pid $PID)"
echo "Press Ctrl+C to stop."
wait "$PID"
