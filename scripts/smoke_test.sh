#!/usr/bin/env bash
# Smoke test for PerioGT API endpoints.
# Usage: bash scripts/smoke_test.sh <BASE_URL>
# Example: bash scripts/smoke_test.sh https://your-workspace--periogt-api-periogt-api.modal.run
#
# Requires: curl
# For Modal proxy auth, set either:
#   - MODAL_KEY and MODAL_SECRET, or
#   - MODAL_TOKEN_ID and MODAL_TOKEN_SECRET
# For HPC server mode auth, set PERIOGT_API_KEY env var.

set -euo pipefail

BASE_URL="${1:?Usage: smoke_test.sh <BASE_URL>}"
BASE_URL="${BASE_URL%/}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOTENV_FILE="${REPO_ROOT}/apps/web/.env.local"

load_dotenv_if_needed() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"

    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" != *=* ]] && continue

    local key="${line%%=*}"
    local value="${line#*=}"

    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [[ ${#value} -ge 2 && "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ ${#value} -ge 2 && "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi

    case "$key" in
      MODAL_KEY|MODAL_SECRET|MODAL_TOKEN_ID|MODAL_TOKEN_SECRET|PERIOGT_API_KEY)
        if [[ -z "${!key:-}" && -n "$value" ]]; then
          export "$key=$value"
        fi
        ;;
    esac
  done < "$env_file"
}

load_dotenv_if_needed "${DOTENV_FILE}"

modal_key="${MODAL_KEY:-${MODAL_TOKEN_ID:-}}"
modal_secret="${MODAL_SECRET:-${MODAL_TOKEN_SECRET:-}}"

auth_args=()
if [[ -n "${modal_key}" && -n "${modal_secret}" ]]; then
  auth_args+=( -H "Modal-Key: ${modal_key}" )
  auth_args+=( -H "Modal-Secret: ${modal_secret}" )
fi

if [[ -n "${PERIOGT_API_KEY:-}" ]]; then
  auth_args+=( -H "X-Api-Key: ${PERIOGT_API_KEY}" )
fi

if [[ "${BASE_URL}" == *".modal.run"* ]]; then
  if [[ -n "${modal_key}" && -n "${modal_secret}" && "${modal_key}" == ak* && "${modal_secret}" == as* ]]; then
    echo "[WARN] MODAL_KEY/MODAL_SECRET look like account tokens (ak/as)."
    echo "[WARN] Modal proxy auth expects workspace Proxy Auth tokens (wk/ws)."
  fi

  if [[ -z "${modal_key}" || -z "${modal_secret}" ]]; then
    echo "[ERROR] Modal proxy credentials are required for this URL."
    echo "Set MODAL_KEY/MODAL_SECRET or MODAL_TOKEN_ID/MODAL_TOKEN_SECRET, then retry."
    exit 2
  fi
fi

body_file="$(mktemp)"
err_file="$(mktemp)"
trap 'rm -f "${body_file}" "${err_file}"' EXIT

pass=0
fail=0

run_test() {
  local name="$1"
  local method="$2"
  local path="$3"
  local json_body="${4:-}"
  local expect_status="${5:-200}"

  echo -n "  ${name} ... "

  local url="${BASE_URL}${path}"
  local -a curl_args=(curl "${auth_args[@]}" "${url}" -o "${body_file}" -w '%{http_code}' -sS)

  if [[ "${method}" == "POST" ]]; then
    curl_args=(
      curl
      "${auth_args[@]}"
      -X POST
      "${url}"
      -H "Content-Type: application/json"
      --data "${json_body}"
      -o "${body_file}"
      -w '%{http_code}'
      -sS
    )
  fi

  local http_code
  if ! http_code="$("${curl_args[@]}" 2>"${err_file}")"; then
    echo "FAIL (request error)"
    cat "${err_file}"
    echo
    ((fail+=1))
    return
  fi

  if [[ "${http_code}" == "${expect_status}" ]]; then
    echo "OK (${http_code})"
    ((pass+=1))
  else
    echo "FAIL (expected ${expect_status}, got ${http_code})"
    cat "${body_file}" 2>/dev/null || true
    if [[ "${http_code}" == "401" ]] && grep -qi "proxy authorization" "${body_file}"; then
      echo "[HINT] Modal proxy auth expects a workspace Proxy Auth Token in Modal-Key/Modal-Secret."
    fi
    echo
    ((fail+=1))
  fi
}

echo "PerioGT Smoke Test - ${BASE_URL}"
echo "================================"

run_test "GET /v1/health" "GET" "/v1/health"
run_test "GET /v1/properties" "GET" "/v1/properties"
run_test "POST /v1/predict (valid)" "POST" "/v1/predict" '{"smiles":"*CC*","property":"tg"}'
run_test "POST /v1/predict (invalid SMILES)" "POST" "/v1/predict" '{"smiles":"invalid","property":"tg"}' "422"
run_test "POST /v1/embeddings" "POST" "/v1/embeddings" '{"smiles":"*CC*"}'
run_test "POST /v1/predict/batch" "POST" "/v1/predict/batch" '{"items":[{"smiles":"*CC*","property":"tg"},{"smiles":"*CC(*)C","property":"tg"}]}'

echo "================================"
echo "Results: ${pass} passed, ${fail} failed"

if [[ ${fail} -gt 0 ]]; then
  exit 1
fi


