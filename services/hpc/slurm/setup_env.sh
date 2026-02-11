#!/usr/bin/env bash
set -euo pipefail

# Common runtime defaults
export DGLBACKEND="${DGLBACKEND:-pytorch}"
export PERIOGT_BASE_DIR="${PERIOGT_BASE_DIR:-$HOME/periogt}"
export PERIOGT_CHECKPOINT_DIR="${PERIOGT_CHECKPOINT_DIR:-${PERIOGT_BASE_DIR}/checkpoints}"
export PERIOGT_RESULTS_DIR="${PERIOGT_RESULTS_DIR:-${PERIOGT_BASE_DIR}/results}"
export PERIOGT_CONTAINER="${PERIOGT_CONTAINER:-services/hpc/apptainer/periogt.sif}"
export USE_APPTAINER="${USE_APPTAINER:-1}"
export PERIOGT_HOST="${PERIOGT_HOST:-0.0.0.0}"
export PERIOGT_PORT="${PERIOGT_PORT:-8000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

export PYTHONPATH="${REPO_ROOT}/services/modal-api:${REPO_ROOT}/services/hpc:${PYTHONPATH:-}"
export PERIOGT_RUNTIME_PACKAGE_DIR="${REPO_ROOT}/services/modal-api"
export PERIOGT_SRC_DIR="${PERIOGT_SRC_DIR:-${REPO_ROOT}/services/modal-api/periogt_src/source_code/PerioGT_common}"

mkdir -p "${PERIOGT_RESULTS_DIR}"

# Bind points for Apptainer. Customize for your cluster filesystem paths.
export APPTAINER_BIND="${APPTAINER_BIND:-${PERIOGT_CHECKPOINT_DIR}:${PERIOGT_CHECKPOINT_DIR},${PERIOGT_RESULTS_DIR}:${PERIOGT_RESULTS_DIR},${REPO_ROOT}:${REPO_ROOT}}"

HOST="$(hostname)"
if command -v module >/dev/null 2>&1; then
  # CADES baseline example
  if [[ "${HOST}" == *"baseline"* || "${HOST}" == *"cades"* ]]; then
    module purge || true
    module load apptainer || true
  fi
  # Explorer example
  if [[ "${HOST}" == *"explorer"* || "${HOST}" == *"neu"* ]]; then
    module purge || true
    module load apptainer || true
  fi
fi

