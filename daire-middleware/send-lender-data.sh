#!/usr/bin/env bash
# send-lender-data.sh — push lender borrower data to DAIRE Central.
#
# DAIRE Central exposes:
#   POST {CENTRAL}/api/lender-data/receive/
#
# The lender sends its data wrapped:
#   {
#     "lender_id": "LDR-DEMO-FLOW",      # exact lender_id registered in Central
#     "borrower_reference": "1001",      # Central's unique id (or nida_number to link)
#     "account_reference": "8834010",
#     "nida_number": "19551015157027220748",   # optional: global unique customer id
#     "payload": { ...full lender contract (LENDER_SUBSYSTEM_README.md) }
#   }
#
# Optional flat contract (lender fields at top level + lender_id) is also
# accepted. Push is keyless by default (REQUIRE_API_KEYS=false).
#
# Usage:
#   CENTRAL_URL=http://127.0.0.1:8000 ./send-lender-data.sh
#
# Environment:
#   CENTRAL_URL     Central base URL (default http://127.0.0.1:8000)
#   LENDER_ID       Lender identifier registered in Central (default LDR-DEMO-FLOW)
#   NIDA_NUMBER     Lender's national id for the borrower (optional)
#   PUSH_FILE       JSON file to push (default pull.json, then borrower_mock.json)
#
set -euo pipefail

cd "$(dirname "$0")"

CENTRAL_URL="${CENTRAL_URL:-http://127.0.0.1:8000}"
LENDER_ID="${LENDER_ID:-LDR-DEMO-FLOW}"
NIDA_NUMBER="${NIDA_NUMBER:-}"

# ---- pick the borrower payload to push -------------------------------------
PUSH_FILE="${PUSH_FILE:-}"
if [ -z "$PUSH_FILE" ]; then
  if [ -f pull.json ]; then
    PUSH_FILE="pull.json"
  elif [ -f borrower_mock.json ]; then
    PUSH_FILE="borrower_mock.json"
  else
    echo "ERROR: no pull.json / borrower_mock.json found in $(pwd)" >&2
    exit 1
  fi
fi

# unwrap pull.json {"borrowers":[...]} -> top-level object
PAYLOAD=$(python3 - "$PUSH_FILE" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as fh:
    data = json.load(fh)
if isinstance(data, dict) and isinstance(data.get("borrowers"), list):
    data = data["borrowers"][0]
print(json.dumps(data))
PYEOF
)

# ensure borrower_reference / account_reference are present
PAYLOAD=$(python3 - "$PAYLOAD" <<'PYEOF'
import json, sys
payload = json.loads(sys.argv[1])
borrower_reference = payload.get("borrower_reference") or payload.get("id") or ""
account_reference = payload.get("account_reference") or payload.get("account_number") or borrower_reference
if borrower_reference:
    payload["borrower_reference"] = borrower_reference
if not payload.get("account_reference"):
    payload["account_reference"] = account_reference
print(json.dumps(payload))
PYEOF
)

# ---- build the wrapped lender push body ------------------------------------
PAYLOAD_WRAPPED=$(python3 - "$PAYLOAD" <<'PYEOF'
import json, sys, os
payload = json.loads(sys.argv[1])
body = {
    "lender_id": os.environ.get("LENDER_ID", "LDR-DEMO-FLOW"),
    "borrower_reference": payload.get("borrower_reference", ""),
    "account_reference": payload.get("account_reference", ""),
    "nida_number": os.environ.get("NIDA_NUMBER", ""),
    "payload": payload,
}
print(json.dumps(body))
PYEOF
)

echo "[lender-data] pushing to ${CENTRAL_URL}/api/lender-data/receive/"
echo "  lender_id      = ${LENDER_ID}"
echo "  borrower_ref   = $(echo "${PAYLOAD}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("borrower_reference",""))')"
echo "  account_ref    = $(echo "${PAYLOAD}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("account_reference",""))')"
echo "  payload file   = ${PUSH_FILE}"

HTTP_CODE=$(curl -s -o /tmp/lender-push-body.json -w "%{http_code}" \
  -X POST "${CENTRAL_URL}/api/lender-data/receive/" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD_WRAPPED}")

echo "[lender-data] HTTP ${HTTP_CODE}"
cat /tmp/lender-push-body.json | python3 -m json.tool 2>/dev/null || cat /tmp/lender-push-body.json
echo
