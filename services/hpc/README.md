# PerioGT HPC Backend

HPC deployment surface for PerioGT inference, built on the shared runtime in `services/modal-api/periogt_runtime`.

## Modes

- CLI batch/single prediction: `python -m periogt_hpc ...`
- Optional server mode: `python -m periogt_hpc.server`
- Artifact setup: `python -m periogt_hpc setup`

## Required Environment

- `DGLBACKEND=pytorch`
- `PYTHONPATH` must include `services/modal-api` so `periogt_runtime` is importable
- Artifacts under `PERIOGT_CHECKPOINT_DIR`:
  - `pretrained_ckpt/`
  - `finetuned_ckpt/`
  - `label_stats.json`
  - `descriptor_scaler.pkl`
  - `index.json`

## Configuration Variables

- `PERIOGT_BASE_DIR` (default: `$HOME/periogt`)
- `PERIOGT_CHECKPOINT_DIR` (default: `$PERIOGT_BASE_DIR/checkpoints`)
- `PERIOGT_RESULTS_DIR` (default: `$PERIOGT_BASE_DIR/results`)
- `PERIOGT_SRC_DIR` (path to `PerioGT_common` source tree)
- `PERIOGT_DEVICE` (`auto`, `cpu`, `cuda`)
- `PERIOGT_HOST` / `PERIOGT_PORT` (server mode)
- `PERIOGT_API_KEY` (optional server auth)
- `PERIOGT_RUNTIME_PACKAGE_DIR` (default autodiscovered; points at `services/modal-api`)

## Quick Start (Conda/Local)

```bash
cd services/hpc
bash conda/install.sh
conda activate periogt
export DGLBACKEND=pytorch
export PYTHONPATH="$(pwd)/../modal-api:${PYTHONPATH}"
python -m periogt_hpc doctor
```

## Setup and Predict

```bash
python -m periogt_hpc setup
python -m periogt_hpc predict --smiles "*CC*" --property tg --format json
python -m periogt_hpc batch --input /path/input.csv --property eps
```

## Optional Server

```bash
export PERIOGT_HOST=0.0.0.0
export PERIOGT_PORT=8000
python -m periogt_hpc.server
```

For tunneled usage, optionally set `PERIOGT_API_KEY` and include `X-Api-Key` in requests.

