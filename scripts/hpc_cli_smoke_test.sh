#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export DGLBACKEND="${DGLBACKEND:-pytorch}"
export PYTHONPATH="${REPO_ROOT}/services/modal-api:${REPO_ROOT}/services/hpc:${PYTHONPATH:-}"
export PERIOGT_RUNTIME_PACKAGE_DIR="${REPO_ROOT}/services/modal-api"
export PERIOGT_SRC_DIR="${PERIOGT_SRC_DIR:-${REPO_ROOT}/services/modal-api/periogt_src/source_code/PerioGT_common}"
export PERIOGT_DEVICE="${PERIOGT_DEVICE:-cpu}"

if [[ $# -gt 0 ]]; then
  export PERIOGT_CHECKPOINT_DIR="$1"
fi

if [[ -z "${PERIOGT_CHECKPOINT_DIR:-}" ]]; then
  echo "Usage: bash scripts/hpc_cli_smoke_test.sh <PERIOGT_CHECKPOINT_DIR>" >&2
  exit 2
fi

TMP_DIR="$(mktemp -d)"
INPUT_CSV="${TMP_DIR}/input.csv"
OUTPUT_CSV="${TMP_DIR}/out.csv"

cat > "${INPUT_CSV}" <<EOF
id,smiles
1,*CC*
2,*CC(*)C
EOF

echo "Running periogt_hpc doctor..."
python -m periogt_hpc doctor

echo "Running periogt_hpc predict..."
python -m periogt_hpc predict --smiles "*CC*" --property tg --format json >/dev/null

echo "Running periogt_hpc batch..."
python -m periogt_hpc batch --input "${INPUT_CSV}" --property tg --output "${OUTPUT_CSV}"

echo "Smoke test complete: ${OUTPUT_CSV}"

