#!/usr/bin/env bash
#SBATCH --job-name=periogt-batch
#SBATCH --output=periogt-batch-%j.out
#SBATCH --error=periogt-batch-%j.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#
# CADES CPU example:
#SBATCH --partition=batch_cnms
#
# CADES / Explorer GPU example:
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1

set -euo pipefail

INPUT_CSV="${INPUT_CSV:-}"
PROPERTY="${PROPERTY:-}"
OUTPUT_CSV="${OUTPUT_CSV:-}"

if [[ -z "${INPUT_CSV}" ]]; then
  echo "INPUT_CSV is required. Example: sbatch --export=INPUT_CSV=/path/in.csv,PROPERTY=tg services/hpc/slurm/batch.sbatch" >&2
  exit 2
fi
if [[ -z "${PROPERTY}" ]]; then
  echo "PROPERTY is required." >&2
  exit 2
fi
if [[ ! -f "${INPUT_CSV}" ]]; then
  echo "INPUT_CSV does not exist: ${INPUT_CSV}" >&2
  exit 2
fi

source services/hpc/slurm/setup_env.sh

if [[ -z "${OUTPUT_CSV}" ]]; then
  base_name="$(basename "${INPUT_CSV}")"
  OUTPUT_CSV="${PERIOGT_RESULTS_DIR}/${base_name%.csv}_predictions.csv"
fi

if [[ "${USE_APPTAINER}" == "1" ]]; then
  if [[ ! -f "${PERIOGT_CONTAINER}" ]]; then
    echo "Container not found: ${PERIOGT_CONTAINER}" >&2
    exit 2
  fi
  apptainer exec --nv --bind "${APPTAINER_BIND}" "${PERIOGT_CONTAINER}" \
    python -m periogt_hpc batch --input "${INPUT_CSV}" --property "${PROPERTY}" --output "${OUTPUT_CSV}"
else
  python -m periogt_hpc batch --input "${INPUT_CSV}" --property "${PROPERTY}" --output "${OUTPUT_CSV}"
fi

echo "Batch output: ${OUTPUT_CSV}"

