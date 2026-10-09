#!/usr/bin/env bash
# export_openapi.sh — export the live OpenAPI 3 schema from the Django code.
#
# The generated file IS the API documentation of record: it is derived from
# the serializers/views at this commit, so it can never drift from the code
# the way hand-written docs do. Regenerate and commit it whenever an endpoint,
# serializer field, or model changes:
#
#     ./export_openapi.sh            # writes docs/openapi-schema.yml
#
# Human-readable contract docs (docs/API_ENDPOINTS.md, LENDER_SUBSYSTEM_README.md)
# complement this file — the schema is the machine-checkable source of truth.
set -euo pipefail
cd "$(dirname "$0")"

OUT="../docs/openapi-schema.yml"

echo "Generating OpenAPI schema -> ${OUT}"
python manage.py spectacular --file "${OUT}" --format openapi

# Warn (do not fail) when the schema contains validation issues — drf-spectacular
# prints them to stderr and still writes the file.
python manage.py spectacular --format openapi --validate > /dev/null 2>/tmp/openapi_warnings.txt || true
if [ -s /tmp/openapi_warnings.txt ]; then
  echo "---- drf-spectacular warnings (review these) ----"
  head -30 /tmp/openapi_warnings.txt
fi

LINES=$(wc -l < "${OUT}")
echo "OK: ${OUT} written (${LINES} lines)."
echo "View interactively at /api/docs/ (Swagger UI) or /api/schema/ (raw)."
