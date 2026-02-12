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
MODAL_KEY=wk_your_proxy_token_id
MODAL_SECRET=ws_your_proxy_token_secret
# Optional aliases (smoke tests accept these too):
# MODAL_TOKEN_ID=wk_your_proxy_token_id
# MODAL_TOKEN_SECRET=ws_your_proxy_token_secret
```

- `MODAL_KEY`/`MODAL_SECRET` (or `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET`) must be **workspace Proxy Auth tokens**.
- `ak...` / `as...` account API tokens do **not** satisfy Modal proxy auth for this backend.

## Modal Proxy Auth Setup (Smoke Tests)

The backend is deployed with `requires_proxy_auth=True`, so direct calls to `*.modal.run` must include proxy auth headers.

1. Create a workspace Proxy Auth token in Modal dashboard (token ID starts with `wk`, secret starts with `ws`).
2. Add credentials in `apps/web/.env.local`:
   ```dotenv
   MODAL_KEY=wk_...
   MODAL_SECRET=ws_...
   ```
3. Optional: export per shell session instead of `.env.local`.
   ```powershell
   $env:MODAL_KEY="wk_..."
   $env:MODAL_SECRET="ws_..."
   pwsh scripts/smoke_test.ps1 "https://<workspace>--periogt-api-periogt-api-<env>.modal.run"
   ```
   ```bash
   export MODAL_KEY="wk_..."
   export MODAL_SECRET="ws_..."
   bash scripts/smoke_test.sh "https://<workspace>--periogt-api-periogt-api-<env>.modal.run"
   ```

Both smoke scripts auto-load `apps/web/.env.local` if variables are not already set.

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
