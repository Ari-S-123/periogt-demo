#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
ENV_NAME="${1:-periogt}"
ENV_FILE="${SCRIPT_DIR}/environment.yml"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found on PATH." >&2
  exit 2
fi

echo "Creating/updating conda environment: ${ENV_NAME}"
conda env create -f "${ENV_FILE}" -n "${ENV_NAME}" || conda env update -f "${ENV_FILE}" -n "${ENV_NAME}"

echo "Installing GPU wheels via pip (PyTorch + DGL)"
conda run -n "${ENV_NAME}" python -m pip install --upgrade pip
conda run -n "${ENV_NAME}" python -m pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.6.0
conda run -n "${ENV_NAME}" python -m pip install --find-links https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html dgl
conda run -n "${ENV_NAME}" python -m pip install dgllife mordred pytest

echo "Installing local HPC package"
conda run -n "${ENV_NAME}" python -m pip install "${REPO_ROOT}/services/hpc"

ENV_PREFIX="$(conda run -n "${ENV_NAME}" python -c 'import sys; print(sys.prefix)')"
ACTIVATE_D="${ENV_PREFIX}/etc/conda/activate.d"
mkdir -p "${ACTIVATE_D}"
cat > "${ACTIVATE_D}/periogt.sh" <<EOF
export DGLBACKEND=pytorch
export PYTHONPATH="${REPO_ROOT}/services/modal-api:${REPO_ROOT}/services/hpc:\${PYTHONPATH}"
export PERIOGT_RUNTIME_PACKAGE_DIR="${REPO_ROOT}/services/modal-api"
export PERIOGT_SRC_DIR="${REPO_ROOT}/services/modal-api/periogt_src/source_code/PerioGT_common"
EOF

echo "Done. Activate with: conda activate ${ENV_NAME}"
echo "Then run: python -m periogt_hpc doctor"

