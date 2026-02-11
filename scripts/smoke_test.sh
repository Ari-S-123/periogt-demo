#!/usr/bin/env bash
# Smoke test for PerioGT API endpoints.
# Usage: bash scripts/smoke_test.sh <BASE_URL>
# Example: bash scripts/smoke_test.sh https://your-workspace--periogt-api-periogt-api.modal.run
#
# Requires: curl, jq
# For Modal proxy auth, set MODAL_KEY and MODAL_SECRET env vars.
# For HPC server mode auth, set PERIOGT_API_KEY env var.

set -euo pipefail

BASE_URL="${1:?Usage: smoke_test.sh <BASE_URL>}"
AUTH_HEADERS=""

if [[ -n "${MODAL_KEY:-}" && -n "${MODAL_SECRET:-}" ]]; then
  AUTH_HEADERS="-H 'Modal-Key: ${MODAL_KEY}' -H 'Modal-Secret: ${MODAL_SECRET}'"
fi

if [[ -n "${PERIOGT_API_KEY:-}" ]]; then
  AUTH_HEADERS="$AUTH_HEADERS -H 'X-Api-Key: ${PERIOGT_API_KEY}'"
fi

pass=0
fail=0

run_test() {
  local name="$1"
  local cmd="$2"
  local expect_status="${3:-200}"

  echo -n "  $name ... "
  local http_code
  http_code=$(eval "$cmd" -o /tmp/smoke_body.json -w '%{http_code}' -s)

  if [[ "$http_code" == "$expect_status" ]]; then
    echo "OK ($http_code)"
    ((pass++))
  else
    echo "FAIL (expected $expect_status, got $http_code)"
    cat /tmp/smoke_body.json 2>/dev/null || true
    echo
    ((fail++))
  fi
}

echo "PerioGT Smoke Test — $BASE_URL"
echo "================================"

run_test "GET /v1/health" \
  "curl $AUTH_HEADERS '$BASE_URL/v1/health'"

run_test "GET /v1/properties" \
  "curl $AUTH_HEADERS '$BASE_URL/v1/properties'"

run_test "POST /v1/predict (valid)" \
  "curl $AUTH_HEADERS -X POST '$BASE_URL/v1/predict' -H 'Content-Type: application/json' -d '{\"smiles\": \"*CC*\", \"property\": \"tg\"}'"

run_test "POST /v1/predict (invalid SMILES)" \
  "curl $AUTH_HEADERS -X POST '$BASE_URL/v1/predict' -H 'Content-Type: application/json' -d '{\"smiles\": \"invalid\", \"property\": \"tg\"}'" \
  "422"

run_test "POST /v1/embeddings" \
  "curl $AUTH_HEADERS -X POST '$BASE_URL/v1/embeddings' -H 'Content-Type: application/json' -d '{\"smiles\": \"*CC*\"}'"

run_test "POST /v1/predict/batch" \
  "curl $AUTH_HEADERS -X POST '$BASE_URL/v1/predict/batch' -H 'Content-Type: application/json' -d '{\"items\": [{\"smiles\": \"*CC*\", \"property\": \"tg\"}, {\"smiles\": \"*CC(*)C\", \"property\": \"tg\"}]}'"

echo "================================"
echo "Results: $pass passed, $fail failed"

if [[ $fail -gt 0 ]]; then
  exit 1
fi
