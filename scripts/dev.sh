#!/usr/bin/env bash
# Run the API and the dashboard together, in the foreground, until Ctrl-C.
#
# Both halves have to be up for the screens to show anything, and on demo day
# that is two terminals to babysit. This is one.
#
#   ./scripts/dev.sh              # ports 8799 and 3000
#   API_PORT=9000 ./scripts/dev.sh
set -euo pipefail

cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8799}"
WEB_PORT="${WEB_PORT:-3000}"
DB="${ONRECORD_DB:-data/onrecord.db}"

if [ ! -f "$DB" ]; then
  echo "seeding $DB from the recorded calls…"
  uv run onrecord --replay --schema schemas/supplier_delivery.yaml --db "$DB" >/dev/null
  uv run onrecord --replay --schema schemas/reference_check.yaml --db "$DB" >/dev/null
fi

# Job control so each half lands in its own process group. Without it, killing
# `npm run dev` leaves the `next-server` it spawned behind, holding the port.
set -m

# Stop both when this script does, however it exits.
api_pid=""
web_pid=""
stop() {
  [ -z "$1" ] && return 0
  # The group first, then the process, in case job control was unavailable.
  kill -TERM -- "-$1" 2>/dev/null || kill -TERM "$1" 2>/dev/null
  return 0
}

port_holders() {
  command -v lsof >/dev/null 2>&1 || return 0
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null || true
}

# Next spawns its dev server into a session of its own, so neither the child
# pid nor its process group reaches it and it keeps the port after Ctrl-C.
# Whatever is still listening gets released by port.
release_port() {
  local holders
  holders=$(port_holders "$1")
  [ -n "$holders" ] && kill $holders 2>/dev/null
  sleep 1
  # Escalate for anything that ignored the first signal mid-compile.
  holders=$(port_holders "$1")
  [ -n "$holders" ] && kill -9 $holders 2>/dev/null
  return 0
}

cleanup() {
  trap - EXIT INT TERM
  stop "$api_pid"
  stop "$web_pid"
  sleep 1
  release_port "$API_PORT"
  release_port "$WEB_PORT"
  wait 2>/dev/null
  return 0
}
trap cleanup EXIT INT TERM

uv run onrecord serve --db "$DB" --port "$API_PORT" &
api_pid=$!

NEXT_PUBLIC_API_BASE="http://127.0.0.1:${API_PORT}" npm --prefix web run dev -- --port "$WEB_PORT" &
web_pid=$!

echo
echo "  dashboard  http://localhost:${WEB_PORT}"
echo "  api        http://127.0.0.1:${API_PORT}/api/meta"
echo "  ctrl-c to stop both"
echo

# Hold until either half stops serving, rather than leaving half a stack up.
# Watching the ports rather than the pids: `uv` and `npm` are wrappers that
# outlive the server they launched, so a dead server does not mean a dead pid.
# (Polling because macOS's bash 3.2 has no `wait -n`.)
grace=25
while :; do
  sleep 1
  kill -0 "$api_pid" 2>/dev/null || break
  kill -0 "$web_pid" 2>/dev/null || break
  if [ "$grace" -gt 0 ]; then
    grace=$((grace - 1))       # both halves still binding their ports
  else
    [ -n "$(port_holders "$API_PORT")" ] || break
    [ -n "$(port_holders "$WEB_PORT")" ] || break
  fi
done
echo "one half stopped serving — shutting the other down" >&2
