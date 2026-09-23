#!/usr/bin/env bash
# Stops the DAIRE backend watchdog and any runserver instances.
pkill -f "run-backend-forever.sh" 2>/dev/null
pkill -f "manage.py runserver 0.0.0.0:8000" 2>/dev/null
echo "DAIRE backend stopped."
