#!/usr/bin/env bash
# Keeps the DAIRE backend alive: restarts it within 2s if it ever exits.
# Usage:   ./run-backend-forever.sh   (leave the terminal open, or run with nohup)
set -u
cd "$(dirname "$0")"

while true; do
  echo "[watchdog] $(date '+%H:%M:%S') starting Django on :8000"
  venv/bin/python manage.py runserver 0.0.0.0:8000 >> /tmp/daire-backend.log 2>&1
  echo "[watchdog] $(date '+%H:%M:%S') backend exited — restarting in 2s"
  sleep 2
done
