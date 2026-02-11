#!/usr/bin/env bash
#SBATCH --job-name=periogt-server
#SBATCH --output=periogt-server-%j.out
#SBATCH --error=periogt-server-%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#
# Explorer/CADES GPU example:
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1

set -euo pipefail

source services/hpc/slurm/setup_env.sh

echo "Server host: ${PERIOGT_HOST}"
echo "Server port: ${PERIOGT_PORT}"
echo "Node: $(hostname)"

if [[ "${USE_APPTAINER}" == "1" ]]; then
  if [[ ! -f "${PERIOGT_CONTAINER}" ]]; then
    echo "Container not found: ${PERIOGT_CONTAINER}" >&2
    exit 2
  fi
  apptainer exec --nv --bind "${APPTAINER_BIND}" "${PERIOGT_CONTAINER}" \
    python -m periogt_hpc.server
else
  python -m periogt_hpc.server
fi

