#!/usr/bin/env bash
# Launcher for the DAIRE lender data + broadcast receiver (runs on 0.0.0.0:4300).
#
# Serves two things from one place:
#   GET  /borrowers?borrower_reference=<ref>   -> lender's borrower data (pull)
#   POST /api/daire/central/receive/           -> Central's result broadcast (push)
#
# Start:
#   ./start-lender-data.sh
# Stop:
#   pkill -f "node manual-borrower-server.js"
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-4300}"
HOST="${HOST:-0.0.0.0}"
DATA_FILE="${DATA_FILE:-$(pwd)/borrower_mock.json}"

mkdir -p /tmp/daire-lender-data

log() {
  echo "[lender-data] $(date -u +'%Y-%m-%dT%H:%M:%SZ') $*"
}

# Kill any existing instance bound to the same port, then start fresh.
if command -v lsof >/dev/null 2>&1; then
  OLD_PID=$(lsof -t -i :"${PORT}" 2>/dev/null || true)
elif command -v fuser >/dev/null 2>&1; then
  OLD_PID=$(fuser "${PORT}/tcp" 2>/dev/null || true)
fi

if [ -n "${OLD_PID}" ]; then
  log "stopping existing listener on :${PORT} (pid ${OLD_PID})"
  kill "${OLD_PID}" 2>/dev/null || true
  sleep 1
fi

log "starting manual borrower + broadcast receiver on ${HOST}:${PORT} (data=${DATA_FILE})"
nohup env \
  PORT="${PORT}" \
  HOST="${HOST}" \
  DATA_FILE="${DATA_FILE}" \
  node "$(pwd)/manual-borrower-server.js" >> /tmp/daire-lender-data/server.log 2>&1 &

# Wait for the port to come up.
for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://127.0.0.1:${PORT}/borrowers?borrower_reference=1001"; then
    log "ready on :${PORT} (pid $!)"
    exit 0
  fi
  sleep 1
done

log "ERROR: listener did not become ready"
cat /tmp/daire-lender-data/server.log >&2
exit 1
