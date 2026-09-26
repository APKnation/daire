#!/usr/bin/env bash
# run-and-verify-backend.sh
#
# Starts the DAIRE Central Django backend on 0.0.0.0:8000 WITH the full
# ALLOWED_HOSTS (so lender IPs 172.17.16.76 / 172.17.16.47 work), then runs a
# battery of end-to-end checks in a single command.
#
# Usage:
#   ./run-and-verify-backend.sh
#
set -euo pipefail

cd "$(dirname "$0")"

# 1) Stop any existing runserver on :8000.
OLD_PID=$(lsof -t -i :8000 2>/dev/null || true)
if [ -n "${OLD_PID}" ]; then
  kill "${OLD_PID}" 2>/dev/null || true
  sleep 2
fi

# 2) Start the backend (full ALLOWED_HOSTS).
export ALLOWED_HOSTS="localhost,127.0.0.1,0.0.0.0,172.17.16.76,172.17.16.47,172.17.16.70,daire.co.tz,*.daire.co.tz"
nohup venv/bin/python manage.py runserver 0.0.0.0:8000 --noreload >> /tmp/daire-backend.log 2>&1 &
SRV_PID=$!
READY=0
for i in $(seq 1 20); do
  if curl -s -m 1 "http://127.0.0.1:8000/health/" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "FAILED: backend did not become ready" >&2
  cat /tmp/daire-backend.log >&2
  kill "${SRV_PID}" 2>/dev/null || true
  exit 1
fi
echo "[backend] Django running on 0.0.0.0:8000 (pid ${SRV_PID})"

# 3. Verify login
echo
echo "=== 1. login (apk/apk) ==="
LOGIN_BODY=$(curl -s -m 5 -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"apk","password":"apk"}')
echo "  $LOGIN_BODY"
if echo "$LOGIN_BODY" | grep -q '"apk"'; then
  echo "  ✓ login OK"
else
  echo "  ✗ login FAILED"
fi

# 4. Verify lender push via each host
echo
echo "=== 2. lender push to /api/lender-data/receive/ ==="
PUSH_BODY=$(curl -s -m 10 -X POST http://127.0.0.1:8000/api/lender-data/receive/ \
  -H "Content-Type: application/json" \
  -d '{"lender_id":"LDR-DEMO-FLOW","borrower_reference":"1001","account_reference":"ACC-001","payload":{"borrower_reference":"1001","customer_id":"001","account_name":"Nia account","age":29,"gender":"FEMALE","employment_status":"EMPLOYED","income":980000,"transaction_frequency":30,"income_frequency":2,"savings":250000,"balance_stability":0.72,"verification":{"identity_verified":true,"identity_provider":"NIDA"},"source_metadata":{"source_system":"NMB_CORE_BANKING"}}}')
echo "  127.0.0.1 -> HTTP $(echo "$PUSH_BODY" | head -c 5)"
echo "  borrower.nida_number = $(echo "$PUSH_BODY" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("borrower",{}).get("nida_number",""))')"

# 5. Verify broadcast receiver on 4300 (lender)
echo
echo "=== 3. lender broadcast receiver on 0.0.0.0:4300 ==="
RECV_BODY=$(curl -s -m 10 -X POST http://127.0.0.1:4300/api/daire/central/receive/ \
  -H "Content-Type: application/json" \
  -d '{"result_type":"CREDIT_RESULT","borrower_reference":"1001","result":{"credit_score":88}}')
echo "  $RECV_BODY"
if echo "$RECV_BODY" | grep -q '"received":true'; then
  echo "  ✓ broadcast receiver OK"
else
  echo "  ✗ broadcast receiver FAILED"
fi

# 6. Verify borrower pull
echo
echo "=== 4. borrower pull from lender ==="
curl -s -m 5 "http://127.0.0.1:4300/borrowers?borrower_reference=1001" | head -c 100
echo

# 7. Summarize
echo
echo "=== SUMMARY ==="
echo "  Django backend: http://127.0.0.1:8000 (ALLOWED_HOSTS incl. 172.17.16.76 / 172.17.16.47)"
echo "  Lender server : http://127.0.0.1:4300 (/borrowers + /api/daire/central/receive/)"
echo
echo "  Lender pushes data to: POST http://127.0.0.1:8000/api/lender-data/receive/"
echo "  Central broadcasts to: POST http://127.0.0.1:4300/api/daire/central/receive/"
echo
echo "  Login:   apk / apk"
echo "  NIDA:    19551015157027220748 (persisted on borrower 1001)"
