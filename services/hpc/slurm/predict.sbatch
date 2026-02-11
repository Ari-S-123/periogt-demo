#!/usr/bin/env bash
#SBATCH --job-name=periogt-predict
#SBATCH --output=periogt-predict-%j.out
#SBATCH --error=periogt-predict-%j.err
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#
# CADES GPU example:
#SBATCH --partition=gpu_acmhs
#SBATCH --gres=gpu:1
#
# Explorer GPU example:
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1

set -euo pipefail

SMILES="${SMILES:-}"
PROPERTY="${PROPERTY:-}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-json}"

if [[ -z "${SMILES}" ]]; then
  echo "SMILES is required. Example: sbatch --export=SMILES='*CC*',PROPERTY=tg services/hpc/slurm/predict.sbatch" >&2
  exit 2
fi
if [[ -z "${PROPERTY}" ]]; then
  echo "PROPERTY is required." >&2
  exit 2
fi

source services/hpc/slurm/setup_env.sh

if [[ "${USE_APPTAINER}" == "1" ]]; then
  if [[ ! -f "${PERIOGT_CONTAINER}" ]]; then
    echo "Container not found: ${PERIOGT_CONTAINER}" >&2
    exit 2
  fi
  apptainer exec --nv --bind "${APPTAINER_BIND}" "${PERIOGT_CONTAINER}" \
    python -m periogt_hpc predict --smiles "${SMILES}" --property "${PROPERTY}" --format "${OUTPUT_FORMAT}"
else
  python -m periogt_hpc predict --smiles "${SMILES}" --property "${PROPERTY}" --format "${OUTPUT_FORMAT}"
fi

