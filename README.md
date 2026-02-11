# PerioGT Demo

PerioGT Demo is a polymer-property prediction system with one shared inference runtime and two deployment surfaces:

1. Modal-hosted FastAPI for web/API usage.
2. HPC-oriented CLI/server packaging for Slurm + Apptainer (primary) and Slurm + Conda (fallback).

## Architecture

```
Web path:
Browser -> Next.js Route Handlers (/api/*) -> Modal FastAPI (/v1/*) -> PerioGT inference

HPC path:
Slurm job -> Apptainer/Conda -> periogt_hpc (CLI or optional server) -> periogt_runtime -> PerioGT inference
```

- Frontend: Next.js 16 App Router, React 19, TypeScript, shadcn/ui, Tailwind v4.
- Shared runtime: `services/modal-api/periogt_runtime` (checkpoint management, model loading, inference, schemas).
- Modal backend: `services/modal-api/periogt_modal_app.py`.
- HPC backend: `services/hpc/periogt_hpc` with `predict`, `embeddings`, `batch`, `doctor`, `setup`.

## Quick Start (Web + Modal)

```bash
# 1) Install frontend workspace deps
bun install

# 2) Configure web env
cp apps/web/.env.example apps/web/.env.local

# 3) Start frontend
bun dev

# 4) Run backend in Modal dev mode (separate terminal)
modal serve services/modal-api/periogt_modal_app.py
```

## Quick Start (HPC CLI)

```bash
# Install fallback conda environment (if not using Apptainer)
bash services/hpc/conda/install.sh periogt
conda activate periogt

# Verify runtime and cluster compatibility
python -m periogt_hpc doctor

# Prepare/check artifacts and index.json
python -m periogt_hpc setup --skip-download

# Single prediction
python -m periogt_hpc predict --smiles "*CC*" --property tg --format json
```

## Key Commands

```bash
# Frontend workspace
bun dev
bun build
bun lint
bun format

# Modal backend
modal serve services/modal-api/periogt_modal_app.py
modal deploy services/modal-api/periogt_modal_app.py

# Python tests
python -m unittest services/modal-api/test_local_paths.py
pytest services/modal-api/tests
pytest services/hpc/tests

# API smoke tests (Modal or HPC server mode)
bash scripts/smoke_test.sh <BASE_URL>
pwsh scripts/smoke_test.ps1 <BASE_URL>

# HPC CLI smoke tests
bash scripts/hpc_cli_smoke_test.sh <PERIOGT_CHECKPOINT_DIR>
pwsh scripts/hpc_cli_smoke_test.ps1 <PERIOGT_CHECKPOINT_DIR>
```

## Environment Variables

Web server env (`apps/web/.env.local`):

```dotenv
MODAL_PERIOGT_URL=https://your-workspace--periogt-api-periogt-api.modal.run
MODAL_KEY=your-modal-key
MODAL_SECRET=your-modal-secret
```

HPC runtime env (set directly or via `services/hpc/slurm/setup_env.sh`):

- `DGLBACKEND=pytorch` (required by DGL)
- `PERIOGT_BASE_DIR`
- `PERIOGT_CHECKPOINT_DIR`
- `PERIOGT_RESULTS_DIR`
- `PERIOGT_SRC_DIR`
- `PERIOGT_DEVICE` (`auto`, `cpu`, `cuda`)
- `PERIOGT_RUNTIME_PACKAGE_DIR`
- `PERIOGT_API_KEY` (optional, server mode auth)

## HPC Operational Notes

- Minimum NVIDIA driver for CUDA 12.6 is `560.28`.
- Use explicit Apptainer bind mounts (`--bind`) for checkpoint/results paths.
- Explorer `/scratch` is purgeable; keep checkpoints on persistent storage (`/projects`).
- DGL is an inherited upstream dependency risk (maintenance is limited); keep PyTorch/DGL pins aligned with the current runtime.

Implementation details and rationale for the HPC surface are captured in `periogt-hpc-backend-feature-spec-reviewed.md`.

## Repository Structure

```text
periogt-demo/
  apps/web/                     Next.js frontend + BFF routes
  services/modal-api/           Modal FastAPI service + shared runtime
  services/hpc/                 HPC CLI/server package + Slurm/Apptainer/Conda assets
  scripts/                      Shell and PowerShell smoke tests
  periogt-hpc-backend-feature-spec-reviewed.md
```

## License

Model artifacts are sourced from Zenodo: https://zenodo.org/records/17035498 (CC-BY 4.0).
