#!/usr/bin/env bash
# Supervisor launcher for the DAIRE Central backend.
# Kills any existing runserver on :8000, then starts one clean instance
# with the FULL ALLOWED_HOSTS (so lender IPs work end-to-end).
set -euo pipefail

cd "$(dirname "$0")"

OLD_PID=$(lsof -t -i :8000 2>/dev/null || true)
if [ -n "${OLD_PID}" ]; then
  echo "[backend] stopping existing listener on :8000 (pid ${OLD_PID})"
  kill "${OLD_PID}" 2>/dev/null || true
  sleep 2
fi

if ! ss -tln | grep -q ":8000 "; then
  echo "[backend] starting on 0.0.0.0:8000"
  # setsid: fully detach from the invoking shell's session so the server
  # survives terminal/tool-session teardown, not just SIGHUP (nohup alone).
  setsid nohup env \
    SECRET_KEY="${SECRET_KEY:-daire-demo-secret}" \
    DEBUG="${DEBUG:-True}" \
    ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1,0.0.0.0,172.17.16.76,172.17.16.47,172.17.16.70,daire.co.tz,*.daire.co.tz}" \
    venv/bin/python manage.py runserver 0.0.0.0:8000 --noreload >> /tmp/daire-backend.log 2>&1 &
  echo "[backend] pid $!"
  for i in $(seq 1 15); do
    if ss -tln | grep -q ":8000 "; then
      echo "[backend] ready on :8000"
      exit 0
    fi
    sleep 1
  done
  echo "[backend] ERROR: did not become ready" >&2
  cat /tmp/daire-backend.log >&2
  exit 1
fi
