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

# Stop both when this script does, however it exits.
pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uv run onrecord serve --db "$DB" --port "$API_PORT" &
pids+=($!)

NEXT_PUBLIC_API_BASE="http://127.0.0.1:${API_PORT}" npm --prefix web run dev -- --port "$WEB_PORT" &
pids+=($!)

echo
echo "  dashboard  http://localhost:${WEB_PORT}"
echo "  api        http://127.0.0.1:${API_PORT}/api/meta"
echo "  ctrl-c to stop both"
echo

# Exit as soon as either half dies, rather than leaving half a stack running.
wait -n
