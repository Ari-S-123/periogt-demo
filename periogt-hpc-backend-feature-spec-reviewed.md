# PerioGT Demo — Backend HPC Deployment Support (ORNL CNMS / CADES Baseline + NEU Explorer)
**Feature Spec Sheet (Implementation-Ready)**  
**Version:** 0.2 (Reviewed)  
**Date:** February 05, 2026  
**Repo:** https://github.com/Ari-S-123/periogt-demo (existing)

---

## 0. What this adds (in one paragraph)

Today the backend is optimized for **Modal + FastAPI** (public HTTPS endpoint, persistent-ish service model, Modal Volumes, and Modal auth headers). This spec adds a **second deployment surface** for the same inference core that runs on traditional HPC infrastructure: **Slurm + Apptainer** (primary) and **Slurm + Conda** (fallback). The HPC deployment is designed to work in three modes:
1) **Batch / CLI mode** (recommended; natural for HPC),  
2) **Optional interactive server mode** (FastAPI on a compute node, reached via SSH tunnel or Open OnDemand on Explorer), and
3) **Setup mode** (one-time artifact download and preparation).

The goal is minimal duplication: **one shared inference engine**, multiple packaging + execution adapters.

---

## 1. Goals

### 1.1 MVP goals (must ship)
1. Run PerioGT inference on **Slurm + Apptainer** with NVIDIA GPUs (V100/A100/H100/H200 class; compute capability ≥ 7.0).
2. Provide **Slurm job templates** for:
   - Single prediction (one SMILES)
   - Batch prediction (CSV input → CSV output)
3. Provide a **CLI tool** that wraps the same prediction/embedding functionality already exposed via the Modal REST API.
4. Ensure **filesystem-based artifacts** (checkpoints, label stats, descriptor scaler) can be used instead of Modal Volume paths.
5. Provide a **cluster-agnostic configuration layer** (env vars + defaults), with **cluster-specific examples** for:
   - ORNL CNMS (CADES Baseline)
   - Northeastern Explorer

### 1.2 Non-goals (explicitly out of scope for MVP)
- Running an always-on public web service from inside HPC (clusters are not designed for public ingress).
- Multi-node distributed inference (PerioGT inference is single-node/single-GPU).
- Supporting AMD ROCm (Frontier/MI250X) in MVP. This can be a follow-on with a separate container and torch build.
- Replacing Modal as the cloud deployment target.

---

## 2. Target environments (reality constraints)

### 2.1 CADES Baseline (ORNL / CNMS usage)
- Job scheduler: **Slurm**
- Container runtime: **Apptainer v1.2.5**
- OS: **Red Hat Enterprise Linux (RHEL)**
- Module system: **Lmod** (default modules: gcc/12.4.0, openmpi/5.0.5)
- CNMS-owned partition (`batch_cnms`, nodes baseline[161-180]) is **CPU-only** (128 cores/node, 512 GB RAM, 2× AMD EPYC 7713); GPUs require negotiating access to the `gpu_acmhs` partition (8× H100, 1 TB RAM, single node) or using legacy SHPC Condo V100/P100 resources.
- Filesystems: NFS home (50 GB), GPFS scratch (Wolf2, shared 2.3 PB), NFS project directories.
- CNMS umbrella project ID: **MAT269**
- Compute nodes are **not publicly reachable**: you should assume **no inbound HTTP from the internet**.
- Login via SSH to `baseline.ccs.ornl.gov`.

### 2.2 Northeastern Explorer (successor to Discovery GPUs)
- Job scheduler: **Slurm**
- Container runtime: **Apptainer**
- OS: **Rocky Linux 9.3**
- Explorer GPU partitions include **H200** (32 chips, 140 GB HBM3e), **A100**, **V100-SXM2**, and legacy K40m/K80 (unsupported by this project).
- Partitions: `gpu` (1 GPU/job, 8h max, no approval), `multigpu` (up to 8 GPUs, 24h max, requires ServiceNow approval and scaling test), `gpu-interactive` (1 GPU, interactive only).
- Multi-GPU partition access is gated (application / approval required).
- Explorer supports **Open OnDemand** (JupyterLab, RStudio, VSCode), which can proxy interactive services.
- Filesystems: `/home` (limited quota), `/scratch` (ephemeral, subject to periodic purge), `/projects` (persistent, PI-managed).
- Package management: **Conda** (recommended by RC team), Spack, pip-within-Conda.
- Located at MGHPCC (Holyoke, MA).

### 2.3 Minimum NVIDIA driver requirements
Apptainer's `--nv` flag binds host NVIDIA driver libraries into the container at runtime. The container's CUDA toolkit version must be compatible with the host's installed driver. For CUDA 12.6, the host driver must be **≥ 560.28**. If the host has an older driver, CUDA calls will fail at runtime even if the container builds successfully. The `doctor` subcommand (F2) must verify this at startup.

### 2.4 Upstream dependency risk: DGL maintenance status
DGL (Deep Graph Library) is **no longer actively maintained** as of late 2024. The latest PyPI release is v2.2.1 (May 2024). The existing Modal deployment uses pre-built wheels from `https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html`, which are published outside PyPI but are the same wheels the production system already depends on. This is an inherited upstream risk shared with the Modal deployment, not a new risk introduced by HPC packaging. However, it means that if future PyTorch versions break DGL compatibility, there will be no upstream fix — the project would need to either pin PyTorch indefinitely or migrate away from DGL (a large effort outside this spec's scope).

---

## 3. User stories and workflows

### 3.1 Batch / CLI (primary HPC workflow)
**As a researcher**, I want to submit a Slurm job with an input file of repeat-unit SMILES and receive a CSV of predictions, so I can run many predictions without managing a web service.

**Workflow**
1. Run `periogt_hpc setup` once to download and extract checkpoints to a shared filesystem path (or place pre-downloaded artifacts manually).
2. Submit `sbatch services/hpc/slurm/batch.sbatch --export=INPUT_CSV=...,PROPERTY=...`
3. Collect results from the output path.

### 3.2 Single prediction (quick test)
**As a researcher**, I want a single command that returns a JSON or one-line output for one SMILES.

**Workflow**
- `apptainer exec --nv periogt.sif python -m periogt_hpc predict --smiles "*CC*" --property eps --format json`

### 3.3 Optional interactive server (advanced)
**As a developer**, I want to run the same FastAPI endpoints on a compute node for debugging and demos.

**Workflow (SSH tunnel)**
1. Submit `server.sbatch` and capture the compute node hostname from the logs.
2. Create tunnel: `ssh -L 8000:<node>:8000 <user>@<login-node>`
3. Open `http://localhost:8000/docs` locally.

**Workflow (Explorer Open OnDemand)**
- Launch the server through OOD's interactive app framework (optional follow-on).

---

## 4. Architectural changes (what must change / what stays the same)

### 4.1 What stays the same
- PerioGT inference logic (graph construction, preprocessing, model load, denormalization)
- Modal deployment path remains valid and unchanged for cloud usage
- API contract (where server mode is used) stays consistent with `/v1/*` endpoints

### 4.2 What must be added
Add a new HPC backend package and packaging assets:

```
services/
  modal-api/                 # existing
    periogt_runtime/         # shared inference library (source-of-truth)
  hpc/                       # NEW
    periogt_hpc/             # python package (CLI + optional server)
      __init__.py
      __main__.py            # enables `python -m periogt_hpc`
      cli.py
      server.py
      config.py
      io_csv.py
      errors.py
      log.py
    apptainer/
      apptainer.def
      build.sh
      README.md
    conda/
      environment.yml
      README.md
    slurm/
      batch.sbatch
      predict.sbatch
      server.sbatch
      setup_env.sh
      README.md
    pyproject.toml           # makes periogt_hpc pip-installable with extras
    README.md
```

### 4.3 What must change (minimally) in shared runtime
The shared runtime currently assumes Modal-specific pathing and mounts. You must parameterize these:
1. **Checkpoint base directory** — `checkpoint_manager.py` currently hardcodes `/vol/checkpoints`. Must accept a configurable root path, defaulting to `/vol/checkpoints` for backward compatibility with Modal.
2. **Vendored PerioGT source path** — `model_loader.py` currently inserts `/root/periogt_src/source_code/PerioGT_common` into `sys.path`. Must accept a configurable path via environment variable, defaulting to the existing path for Modal.
3. **Device selection** — `inference.py` should use `torch.device("cuda" if torch.cuda.is_available() else "cpu")` with an explicit log warning when falling back to CPU. Currently device is implicit.

This is a deliberate design constraint: keep runtime changes small and isolated, so Modal remains stable.

### 4.4 Cross-package import strategy
The HPC CLI (`services/hpc/periogt_hpc/`) must import from the shared runtime (`services/modal-api/periogt_runtime/`). Inside the Apptainer container, both directories are baked into the image at known paths (e.g., `/opt/periogt/`), so imports work naturally. For Conda/local development, `services/hpc/pyproject.toml` should declare a path dependency or the user must set `PYTHONPATH` to include `services/modal-api/`. The `setup_env.sh` script must handle this. The Slurm templates must set `PYTHONPATH` appropriately before invoking the CLI.

### 4.5 Environment variables required by DGL
DGL requires the `DGLBACKEND` environment variable to be set. The Apptainer def, Conda activation scripts, and all Slurm templates must export `DGLBACKEND=pytorch`. Without this, DGL defaults to searching for MXNet and fails.

---

## 5. Detailed functional requirements

### F1 — Cluster-agnostic configuration layer
**Requirement**
- Implement `services/hpc/periogt_hpc/config.py` that resolves:
  - `PERIOGT_BASE_DIR`
  - `PERIOGT_CHECKPOINT_DIR`
  - `PERIOGT_RESULTS_DIR`
  - `PERIOGT_SRC_DIR` (path to vendored PerioGT source for `sys.path` insertion)
  - `PERIOGT_DEVICE` (optional override: `cpu` or `cuda`)
- Provide safe defaults that work on any cluster home directory, but document cluster-specific recommended paths.
- All resolved paths must be logged at startup (at INFO level) so operators can verify configuration.

**Acceptance criteria**
- If required paths (checkpoint dir, source dir) do not exist, CLI errors out with a *clear* message listing which path was expected and where it looked, and exit code 2.
- If `PERIOGT_DEVICE=cuda` but no CUDA is available, exit code 2 (hard fail) with a message suggesting `PERIOGT_DEVICE=cpu` or checking `--nv` flag.
- If `PERIOGT_DEVICE=cuda` and CUDA is available but the GPU compute capability is < 7.0 (Kepler/Maxwell class), exit code 2 with a message naming the detected GPU and stating the minimum requirement.
- If `PERIOGT_DEVICE` is unset, auto-detect CUDA availability and log a warning when falling back to CPU.

---

### F2 — HPC CLI package (predict / embeddings / batch / doctor / setup)
**CLI framework:** `click` (already a transitive dependency of several scientific packages; lightweight, well-documented).

**Commands**
1. `periogt_hpc predict`
   - Inputs: `--smiles`, `--property`, `--return-embedding` (bool)
   - Output: JSON to stdout (default) or CSV line (`--format csv`)
2. `periogt_hpc embeddings`
   - Inputs: `--smiles`
   - Output: JSON with `embedding[]` and `dim`
3. `periogt_hpc batch`
   - Inputs: `--input` CSV path, `--property`, optional `--output` CSV path (defaults to `<input_stem>_predictions.csv`)
   - Behavior: Loads model once at startup, then iterates rows. Writes output CSV with per-row status. Must not re-initialize the model per row.
4. `periogt_hpc doctor`
   - Prints environment diagnostics: Python version, torch version, CUDA availability, GPU model and compute capability (if any), NVIDIA driver version (via `nvidia-smi` or `torch.cuda`), DGLBACKEND value, checkpoint paths resolved and whether each required artifact exists, DGL version, estimated memory footprint.
   - Exits 0 if all checks pass, 1 if warnings, 2 if fatal problems.
5. `periogt_hpc setup`
   - Downloads checkpoint archives from Zenodo to `PERIOGT_CHECKPOINT_DIR`, verifies MD5 checksums, extracts them, and generates `index.json`.
   - Skips download if archives already exist and checksums match (idempotent).
   - Requires outbound internet access (may not be available on all compute nodes — should be run from login nodes or data transfer nodes).
   - Accepts `--skip-download` flag to only run index generation on pre-placed artifacts.

**Batch CSV format**
- Input columns:
  - `smiles` (required)
  - optional `id` (preserved in output)
- Output columns:
  - `id` (if present in input, else auto-generated row index)
  - `smiles`
  - `property`
  - `prediction_value` (float)
  - `prediction_units` (string)
  - `ok` (`true`|`false`)
  - `error_code` (empty if ok)
  - `error_message` (empty if ok)
  - `request_id` (uuid)

**Acceptance criteria**
- Batch mode returns partial results even if some rows fail validation.
- Output is deterministic for identical inputs + checkpoints.
- Errors map to stable codes (see F6).
- Model loading happens exactly once before row iteration begins, not per-row.
- `setup` is idempotent: running it twice produces the same result.

---

### F3 — Optional HPC server mode (FastAPI) with parity to Modal endpoints
**Endpoints (match Modal PRD)**
- `GET /v1/health`
- `GET /v1/properties`
- `POST /v1/predict`
- `POST /v1/embeddings`
- `POST /v1/predict/batch`

**Notes**
- No Modal proxy auth headers in HPC mode.
- Optional `X-Api-Key` header authentication, enabled when `PERIOGT_API_KEY` environment variable is set. If the env var is unset, auth is disabled (suitable for SSH-tunneled usage on internal networks). If the env var is set, all requests must include a matching `X-Api-Key` header or receive a 401.
- Default bind: `0.0.0.0:8000`, configurable via `PERIOGT_HOST` and `PERIOGT_PORT`.

**Acceptance criteria**
- `scripts/smoke_test.sh` can be run against the HPC server URL after tunneling (with optional `-H "X-Api-Key: ..."` flag).
- Server mode respects the same validation rules as Modal (SMILES validation, property validation, max length).

---

### F4 — Apptainer packaging (primary HPC packaging)
**Requirement**
- Create `services/hpc/apptainer/apptainer.def` to build a `.sif` with:
  - Base image: `nvidia/cuda:12.6.0-runtime-ubuntu22.04` (**not** `-devel`; the runtime image is ~4 GB smaller and the CUDA compiler toolchain is not needed for inference)
  - Python 3.11
  - PyTorch 2.6.x CUDA 12.6 wheels (`--index-url https://download.pytorch.org/whl/cu126`)
  - DGL CUDA-matched wheels (`--find-links https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html`)
  - Scientific stack (numpy<2, scipy, scikit-learn, pandas, networkx, pyyaml, rdkit, dgllife, mordred)
  - fastapi + uvicorn + pydantic (for server mode)
  - click (for CLI)
  - The repo code **baked into the image** at `/opt/periogt/` (not bind-mounted; baking in is strongly preferred for reproducibility on HPC)
  - System packages: `libgl1-mesa-glx`, `libglib2.0-0` (RDKit rendering deps)
  - `DGLBACKEND=pytorch` set in `%environment`

**Build scripts**
- `services/hpc/apptainer/build.sh`:
  - Validates `apptainer` exists on `$PATH`
  - Builds `periogt.sif` from `apptainer.def`
  - Supports `--fakeroot` where available (required on shared systems without root)
  - Emits the built artifact path + sha256

**Runtime expectations**
- Must be invoked with `--nv` on GPU nodes.
- Must use `--bind` to mount checkpoint and results directories from the host filesystem into the container, since SIF images are read-only. Example: `apptainer exec --nv --bind /gpfs/wolf2/olcf/mat269:/data periogt.sif ...`
- If the code writes temporary files (e.g., `__pycache__`, temp extraction), the `--writable-tmpfs` flag must be documented as potentially necessary, or the code must be written to direct all temp I/O to a host-bound writable path (e.g., `TMPDIR`).

**Acceptance criteria**
- The container runs on both CADES Baseline and Explorer with `--nv`.
- `periogt_hpc doctor` shows CUDA available on GPU nodes.
- The container can be built with `--fakeroot` (no root required).

**Apptainer `nvliblist.conf` note**  
CADES Baseline runs Apptainer v1.2.5, whose default `nvliblist.conf` is tuned for CUDA 11. If CUDA 12.6 libraries are not automatically bound by `--nv`, the admin may need to update `/etc/apptainer/nvliblist.conf` on the GPU node, or users can set `APPTAINERENV_LD_LIBRARY_PATH` manually. The `doctor` command should detect this failure mode (CUDA reported available by driver but `torch.cuda.is_available()` returns false) and suggest the `nvliblist.conf` check.

---

### F5 — Conda environment packaging (fallback)
**Requirement**
- Provide `services/hpc/conda/environment.yml` aligned to the Modal PRD versions.
- **Critical: PyTorch + CUDA must be installed via pip, not conda channels.** The `pytorch-cuda` metapackage on the `pytorch` conda channel has been deprecated for recent PyTorch versions. The conda-forge channel ships CUDA-enabled PyTorch but does not allow pinning to a specific CUDA version reliably. The only reliable method is using pip with PyTorch's official wheel index.

**Corrected `environment.yml` structure:**
```yaml
name: periogt
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - numpy<2
  - scipy
  - scikit-learn
  - pandas
  - networkx
  - pyyaml
  - rdkit
  - click
  - pip
  - pip:
    - torch==2.6.0 --index-url https://download.pytorch.org/whl/cu126
    - dgl --find-links https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html
    - dgllife
    - mordred
    - fastapi
    - "uvicorn[standard]"
    - "pydantic>=2.8,<3"
```

**Important note on pip-in-conda syntax:** The `--index-url` and `--find-links` flags inside a conda `environment.yml` pip section are **not natively supported** by conda's pip integration. Users will need to run the pip installs manually after creating the base conda environment, or use a two-step install script. The `conda/README.md` must document this clearly, and a `conda/install.sh` helper script should be provided that creates the env and runs the pip commands separately.

**Activation script requirements:**
The conda environment's activation script (or a documented manual step) must export `DGLBACKEND=pytorch` and set `PYTHONPATH` to include the repo's `services/modal-api/` directory.

**Acceptance criteria**
- A user can create the environment in their project space and run the CLI without containers.
- `periogt_hpc doctor` passes within the Conda environment.

---

### F6 — Error taxonomy and operator-friendly messages
**Requirement**
- Define stable error codes:
  - `validation_error` — Invalid SMILES syntax, missing wildcard atoms, too long
  - `unsupported_property` — Property ID not in index.json
  - `checkpoint_missing` — Required artifact file not found at resolved path
  - `checksum_mismatch` — Downloaded archive MD5 does not match Zenodo's published hash
  - `model_load_failed` — PyTorch/DGL failed to deserialize checkpoint (corrupt file, version mismatch)
  - `cuda_unavailable` — User requested CUDA but no compatible GPU found
  - `gpu_unsupported` — GPU detected but compute capability < 7.0
  - `driver_incompatible` — NVIDIA driver version too old for CUDA 12.6 (< 560.28)
  - `internal_error` — Catch-all for unexpected failures
- All CLI and server errors must map to this taxonomy.

**Acceptance criteria**
- Batch mode never crashes with an unhandled exception; every row yields either a result or an error row.
- CLI exits with code 2 for configuration/setup errors, code 1 for partial failures (some rows failed in batch), code 0 for full success.

---

### F7 — Artifact management on filesystems (non-Modal)
**Requirement**
- Extend checkpoint bootstrap logic to support:
  - "artifacts already present on disk" (preferred for HPC — many clusters restrict outbound internet from compute nodes)
  - optional "download on demand" via the `setup` CLI subcommand (run from login/DTN nodes where internet is available)
- Minimum required artifacts (same as Modal PRD):
  - `pretrained_ckpt/` directory (extracted from `pretrained_ckpt.zip`)
  - `finetuned_ckpt/` directory (extracted from `finetuned_ckpt.zip`)
  - `label_stats.json`
  - `descriptor_scaler.pkl`
  - `index.json` (generated by scanning finetuned checkpoints)

**Index generation concurrency safety:**
Index generation (`index.json` creation) must use atomic write (write to a temp file, then `os.rename()` to the final path) to prevent corruption if two jobs start simultaneously. Alternatively, make index generation a dedicated step in `setup` that is run once before any batch jobs, and have batch jobs fail-fast if `index.json` is missing rather than attempting to generate it themselves.

**Acceptance criteria**
- A job fails early (before model loading or heavy compute) if any required artifact is missing, with an error message listing exactly which file is absent and where it was expected.
- Index generation is idempotent and safe under concurrent jobs.

**Filesystem location warnings:**
On Explorer, `/scratch` is subject to periodic purge. Checkpoints and `label_stats.json` / `descriptor_scaler.pkl` must be stored on `/projects` (persistent), not `/scratch`. Results may go to `/scratch` since they are ephemeral. The documentation and example defaults must call this out explicitly.

---

### F8 — Slurm job templates and cluster profiles
**Requirement**
- Provide Slurm templates that are explicitly easy to edit, with:
  - common directives at top
  - "CADES section" and "Explorer section" clearly separated with comments
  - environment setup script (`setup_env.sh`) that handles modules, `PYTHONPATH`, `DGLBACKEND`, and container path setup

**Files**
- `services/hpc/slurm/predict.sbatch`
- `services/hpc/slurm/batch.sbatch`
- `services/hpc/slurm/server.sbatch`
- `services/hpc/slurm/setup_env.sh`
- `services/hpc/slurm/README.md`

**Apptainer bind-mount requirements in templates:**
CADES Baseline GPFS paths (e.g., `/gpfs/wolf2/olcf/...`) and NFS project paths are **not** automatically mounted into Apptainer containers (Apptainer default mounts are `$HOME`, `/tmp`, `/proc`, `/sys`, `$PWD`). All Slurm templates using Apptainer must include explicit `--bind` directives for checkpoint and results directories. The templates must include a clearly commented `APPTAINER_BIND` variable that users customize for their filesystem layout.

**Acceptance criteria**
- Templates run without modification except for the user's project/account + paths.
- Templates support overriding:
  - container path (`PERIOGT_CONTAINER`)
  - base dir / checkpoint dir / results dir
  - requested GPU type (when Slurm gres naming differs)
- Templates include input validation (fail if required env vars are unset before submitting to the queue).
- Templates export `DGLBACKEND=pytorch` before invoking inference.
- Templates set `PYTHONPATH` if using Conda instead of Apptainer.

---

### F9 — GPU compatibility checks (guardrails)
**Requirement**
- On startup, detect GPU capability and provide explicit guidance:
  - Reject known-dead GPUs (Kepler class: K80/K40, compute capability < 7.0) when using CUDA 12 builds.
  - Check NVIDIA driver version against minimum (560.28 for CUDA 12.6).
  - Provide CPU fallback as an explicit opt-in (`PERIOGT_DEVICE=cpu`), not a silent accident.

**Acceptance criteria**
- If `PERIOGT_DEVICE=cuda` and GPU is unsupported (compute capability < 7.0), the program exits with a clear message naming the GPU and code 2.
- If `PERIOGT_DEVICE=cuda` and driver is too old, the program exits with a message stating the detected and required driver versions.
- `doctor` prints a compatibility verdict including: GPU name, compute capability, driver version, CUDA toolkit version (from `torch.version.cuda`), and a PASS/FAIL/WARN summary.

---

### F10 — Tests and validation (must be runnable without cluster)
**Requirement**
- Add unit tests that can run locally (CPU) for:
  - Config path resolution (including missing path error behavior)
  - CSV parsing / writing (including malformed input handling)
  - Error taxonomy mapping
  - "artifacts missing" behavior
  - GPU compatibility check logic (with mocked `torch.cuda` values)
- Add integration scripts:
  - `scripts/smoke_test.sh` remains the canonical API smoke test (works against Modal and HPC server).
  - `scripts/hpc_cli_smoke_test.sh` — runs `doctor`, a single `predict`, and a small `batch` on CPU mode.

**Acceptance criteria**
- `python -m pytest services/hpc/tests/` passes locally (CPU, no GPU required).
- Smoke test scripts run against an HPC server after tunneling.
- PR-1 (shared runtime changes) includes a regression test confirming Modal path defaults are preserved.

---

## 6. Step-by-step implementation plan (recommended PR sequence)

### PR-1: Extract and harden runtime path configurability
1. Identify all hardcoded path assumptions in `services/modal-api/periogt_runtime/`:
   - `checkpoint_manager.py`: `/vol/checkpoints` base path
   - `model_loader.py`: `/root/periogt_src/source_code/PerioGT_common` sys.path insertion
   - `inference.py`: implicit device selection
2. Introduce environment-variable overrides with non-breaking defaults that preserve Modal behavior. Specifically:
   - `PERIOGT_CHECKPOINT_DIR` → defaults to `/vol/checkpoints`
   - `PERIOGT_SRC_DIR` → defaults to `/root/periogt_src/source_code/PerioGT_common`
   - `PERIOGT_DEVICE` → defaults to auto-detect
3. Add unit tests that verify: (a) default paths are unchanged when env vars are unset, (b) custom paths are used when env vars are set.

**Deliverables**
- Runtime changes only; no new HPC code yet.
- **Hard requirement:** `modal serve` and `modal deploy` must still work identically after this PR. This is the acceptance gate.

---

### PR-2: Add `services/hpc/` package with CLI (no server mode yet)
1. Implement `periogt_hpc/config.py` with full path resolution and validation.
2. Implement `periogt_hpc/cli.py` with `predict`, `embeddings`, `batch`, `doctor`, `setup`.
3. Implement CSV IO module (`io_csv.py`) + error taxonomy (`errors.py`).
4. Implement `periogt_hpc/__main__.py` for `python -m periogt_hpc` invocation.
5. Add `pyproject.toml` with `click` as a dependency.

**Deliverables**
- Can run CLI locally on CPU if artifacts are present.
- Unit tests pass without GPU.

---

### PR-3: Add Apptainer packaging + build docs
1. Add `apptainer.def` using `nvidia/cuda:12.6.0-runtime-ubuntu22.04` base.
2. Add `build.sh` with fakeroot support.
3. Bake repo code into image at `/opt/periogt/`.
4. Set `DGLBACKEND=pytorch` and `PYTHONPATH` in `%environment`.
5. Document runtime usage, `--nv` requirement, `--bind` requirements for host filesystems, and `--writable-tmpfs` if needed.

---

### PR-4: Add Slurm templates for CADES and Explorer
1. Create `slurm/*.sbatch` templates with `DGLBACKEND`, `PYTHONPATH`, and `APPTAINER_BIND` set correctly.
2. Create `setup_env.sh` with cluster-detection logic (check hostname pattern or env vars to auto-select module loads).
3. Include robust input validation inside job scripts (fail before `srun` if required vars are missing).
4. Include a "results collection" step (log output path and naming conventions).
5. Add `conda/install.sh` helper for two-step Conda+pip environment creation.

---

### PR-5 (optional): Add FastAPI server mode for HPC + tunnel docs
1. Implement `server.py` (FastAPI) reusing the runtime and the same schemas.
2. Implement optional `X-Api-Key` auth middleware gated on `PERIOGT_API_KEY` env var.
3. Add `server.sbatch`.
4. Update smoke tests to accept optional API key header.

---

## 7. Acceptance criteria (Definition of Done)

### A. Functional
- On Explorer:
  - Can run `predict.sbatch` and get a correct prediction on a V100, A100, or H200.
  - Can run `batch.sbatch` and get a results CSV for at least 100 rows.
- On CADES Baseline:
  - Can run the same job scripts on CPU nodes (CPU mode) in the `batch_cnms` partition.
  - Can run on a GPU node **if the user has access to `gpu_acmhs`** (or SHPC Condo V100 resources).
- CLI:
  - `doctor` runs and provides actionable output with a clear PASS/FAIL verdict.
  - `setup` downloads and prepares artifacts idempotently.

### B. Operational
- No secrets are committed.
- `DGLBACKEND=pytorch` is set in every execution path (Apptainer, Conda, Slurm templates).
- Documentation is sufficient for a new lab member to run a prediction from zero (including Apptainer build, artifact setup, and job submission).

### C. Safety / correctness
- Clear rejection of unsupported GPU classes (compute capability < 7.0) when using CUDA 12 builds.
- Clear rejection of incompatible NVIDIA drivers (< 560.28).
- Deterministic outputs given fixed artifacts.
- PR-1 does not regress Modal deployment.

---

## 8. Open risks and mitigations (don't ignore these)

1. **GPU partition access at ORNL**  
   Mitigation: ship CPU mode + document the GPU partition requirement; keep ROCm work as follow-on. CPU inference is slow (~5-20× depending on model size) but functional for single predictions and small batches.

2. **Container build restrictions**  
   Mitigation: support both "build on workstation then upload" and "build on cluster with fakeroot" where allowed. CADES Baseline explicitly supports `apptainer build` with fakeroot.

3. **Filesystem performance + contention**  
   Mitigation: prefer local scratch for temporary extraction; keep checkpoints on parallel FS (GPFS on CADES, `/projects` on Explorer); avoid repeated unzip by using a "ready marker" file after successful extraction.

4. **Dependency ABI mismatch on HPC OS**  
   Mitigation: Use Ubuntu 22.04 base in container (not cluster-native RHEL/Rocky) because PyTorch/DGL/RDKit ship Ubuntu-targeting wheels. Apptainer's `--nv` binds only the GPU driver from the host; all other userspace libraries come from the container, so OS mismatch is not a concern for non-GPU libraries.

5. **DGL no longer actively maintained**  
   Mitigation: Pin DGL version and PyTorch version together. Monitor for breakage on new CUDA driver updates. If DGL wheels disappear from `data.dgl.ai`, archive the working `.whl` files in the project's artifact storage. Long-term, consider migration to PyG or pure-PyTorch graph operations (out of scope for this spec).

6. **Apptainer `nvliblist.conf` mismatch on CADES**  
   Mitigation: `doctor` command detects this. Document the workaround (ask CADES admins to update, or use `--nvccli` flag if `nvidia-container-cli` is installed).

7. **Conda pip-in-yaml limitations**  
   Mitigation: Provide `conda/install.sh` script that handles the two-step install correctly. Do not rely on `--index-url` or `--find-links` working inside `environment.yml`'s pip section.

8. **Explorer `/scratch` purge**  
   Mitigation: All documentation and templates store checkpoints on `/projects` (persistent). Only ephemeral results go to `/scratch`.

---

## 9. Reference links (operator-facing)
- PyTorch 2.6 release blog: https://pytorch.org/blog/pytorch2-6/
- PyTorch CUDA wheel index: https://download.pytorch.org/whl/cu126
- DGL wheel index (torch 2.6, CUDA 12.6): https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html
- Apptainer GPU support (`--nv`): https://apptainer.org/docs/user/1.2/gpu.html
- Apptainer admin config (`nvliblist.conf`): https://apptainer.org/docs/admin/1.2/configfiles.html
- CADES Baseline user guide (Apptainer v1.2.5, containers): https://docs.cades.olcf.ornl.gov/baseline_user_guide/baseline_user_guide.html
- CADES Baseline Slurm: https://docs.cades.olcf.ornl.gov/baseline_user_guide/baseline_user_guide.html#running-jobs
- NEU Explorer announcement (Rocky Linux 9.3, H200 GPUs): https://rc.northeastern.edu/2025/07/29/all-public-gpus-now-on-explorer/
- NEU Explorer GPU overview: https://rc-docs.northeastern.edu/en/latest/gpus/gpuoverview.html
- NEU H200 quick start: https://rc-docs.northeastern.edu/en/explorer-main/gpus/quickstart-h200.html
- NEU MultiGPU partition access guide: https://rc-docs.northeastern.edu/en/latest/gpus/multigpu-partition-access.html
- NVIDIA CUDA compatibility (driver requirements): https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/

---

## 10. Appendix — Cluster-specific "known good" starting defaults (templates)

### A. Explorer (example defaults)
- `PERIOGT_BASE_DIR=/projects/<pi_or_group>/periogt`
- `PERIOGT_CHECKPOINT_DIR=/projects/<pi_or_group>/periogt/checkpoints`
- `PERIOGT_RESULTS_DIR=/scratch/<user>/periogt/results`
- `PERIOGT_SRC_DIR=` (not needed if using Apptainer with code baked in)
- **Warning:** Do NOT place checkpoints on `/scratch`. It is subject to periodic purge.

### B. CADES Baseline (example defaults)
- `PERIOGT_BASE_DIR=/gpfs/wolf2/olcf/mat269/proj-shared/periogt` (or equivalent project dir)
- `PERIOGT_CHECKPOINT_DIR=/gpfs/wolf2/olcf/mat269/proj-shared/periogt/checkpoints`
- `PERIOGT_RESULTS_DIR=/gpfs/wolf2/olcf/mat269/scratch/<user>/periogt/results`
- `PERIOGT_SRC_DIR=` (not needed if using Apptainer with code baked in)
- **Note:** CNMS project code is `MAT269`. Your PI provides this.

> Replace placeholders. This spec intentionally does not hardcode project IDs or private paths.

---

## 11. GPU compatibility matrix (reference)

| GPU | Compute Capability | CUDA 12.6 | PyTorch 2.6 | Min Driver | Where Available |
|-----|-------------------|-----------|-------------|------------|-----------------|
| NVIDIA H200 | 9.0 | ✅ | ✅ | 560.28 | NEU Explorer |
| NVIDIA H100 | 9.0 | ✅ | ✅ | 560.28 | CADES gpu_acmhs (1 node, 8 GPUs) |
| NVIDIA A100 | 8.0 | ✅ | ✅ | 560.28 | NEU Explorer (multigpu, approval req.) |
| NVIDIA V100 | 7.0 | ✅ | ✅ | 560.28 | NEU Explorer, CADES SHPC Condo |
| NVIDIA P100 | 6.0 | ⚠️ | ⚠️ | 560.28 | CADES SHPC Condo (sm_60 may work but untested) |
| NVIDIA K80 | 3.7 | ❌ | ❌ | N/A | Legacy (PyTorch 2.x dropped sm_37) |
| NVIDIA K40m | 3.5 | ❌ | ❌ | N/A | NEU legacy (not supported) |
| CPU (any) | N/A | N/A | ✅ | N/A | All nodes |

---

## Appendix Z — Changelog from v0.1 to v0.2 (review alterations)

This section documents every substantive change made during review, with rationale.

**Z.1 — Added `setup` CLI subcommand (F2)**  
The v0.1 spec provided `predict`, `embeddings`, `batch`, and `doctor` but had no mechanism for initial artifact preparation. On HPC clusters, compute nodes often lack outbound internet access, so checkpoint download must be a separate, explicit step run from login or data transfer nodes. The `setup` subcommand fills this gap. It also accepts `--skip-download` for environments where artifacts are manually pre-placed. (Section 3.1 workflow also updated to reference this.)

**Z.2 — Added `__main__.py` to package structure (Section 4.2)**  
Required for `python -m periogt_hpc` invocation to work. The v0.1 structure omitted this file.

**Z.3 — Added `pyproject.toml` to package structure (Section 4.2)**  
Makes the HPC package pip-installable, which simplifies both Apptainer builds and Conda-based installs. Without this, users must manually manage `PYTHONPATH`.

**Z.4 — Added cross-package import strategy (Section 4.4)**  
The v0.1 spec stated that `periogt_runtime/` under `modal-api/` is the "source-of-truth" but did not explain how `services/hpc/periogt_hpc/` imports from it. This is a non-trivial problem because the two packages live in different directories. The solution (bake into container at known path, set `PYTHONPATH` for Conda) is now explicit.

**Z.5 — Added `DGLBACKEND=pytorch` requirement (Section 4.5)**  
DGL requires this environment variable to select its PyTorch backend. Without it, DGL attempts to import MXNet and fails. The v0.1 spec did not mention this. It must be set in the Apptainer def, Conda activation, and all Slurm templates.

**Z.6 — Expanded Section 2 with concrete hardware details**  
The v0.1 spec was vague about CADES Baseline hardware ("CNMS-owned partition is CPU-only; GPUs require using a non-CNMS GPU partition"). The review added specific node ranges, processor models, RAM, partition names, project codes, Apptainer version, OS, module defaults, filesystem paths, and login nodes. The same was done for Explorer. Operators need these details to write correct Slurm directives.

**Z.7 — Added minimum NVIDIA driver requirement (Section 2.3)**  
Apptainer `--nv` binds host driver libraries into the container. If the host driver is too old for CUDA 12.6 (< 560.28), inference fails at runtime with opaque CUDA errors. This is a common gotcha on HPC clusters where driver updates lag. Now documented as a hard requirement with `doctor` verification.

**Z.8 — Added DGL maintenance status warning (Section 2.4)**  
DGL's last PyPI release was May 2024 and the project is no longer actively maintained (confirmed by downstream projects like matgl explicitly migrating away). This is an inherited risk from the Modal deployment, not new to HPC, but it affects long-term viability of the Conda environment and Apptainer builds. Mitigation strategies documented in risk #5.

**Z.9 — Changed Apptainer base image from `-devel` to `-runtime` (F4)**  
The v0.1 spec did not specify the base image tag. The deployment analysis from the prior conversation used `nvidia/cuda:12.6.0-devel-ubuntu22.04`, which includes the full CUDA compiler toolchain (~4 GB). Since PerioGT only runs inference (no CUDA kernel compilation), the `-runtime` variant is sufficient and produces a significantly smaller `.sif` file, reducing build time and transfer time to the cluster.

**Z.10 — Added Apptainer bind-mount requirements (F4, F8)**  
SIF images are read-only. Apptainer's default mounts (`$HOME`, `/tmp`, `/proc`, `/sys`, `$PWD`) do not include GPFS paths on CADES or `/projects` on Explorer. Without explicit `--bind`, the container cannot access checkpoints or write results. The v0.1 spec mentioned `--nv` but not `--bind`. Now both are required in all templates, with a configurable `APPTAINER_BIND` variable.

**Z.11 — Added `--writable-tmpfs` documentation (F4)**  
Python writes `__pycache__` directories and other temp files. Inside a read-only SIF, these writes fail silently or raise errors. Either the code must redirect all temp I/O to a bound writable path, or users must pass `--writable-tmpfs`. Now documented.

**Z.12 — Added `nvliblist.conf` compatibility warning (F4)**  
CADES Baseline runs Apptainer v1.2.5, whose default `nvliblist.conf` is configured for CUDA 11 library names. CUDA 12 may require updated library patterns. The `doctor` command now has explicit guidance to detect and diagnose this.

**Z.13 — Corrected Conda `environment.yml` (F5)**  
The v0.1 spec listed `pytorch-cuda=12.6` as a conda dependency. This is broken: PyTorch has deprecated the `pytorch-cuda` metapackage on the `pytorch` channel as of early 2025, and `pytorch-cuda=12.6` does not resolve on conda-forge either. The corrected approach uses pip for PyTorch+CUDA wheels inside the conda environment. Additionally, `--index-url` and `--find-links` flags are not supported inside conda `environment.yml` pip sections, so a separate `install.sh` helper script is required.

**Z.14 — Added `gpu_unsupported` and `driver_incompatible` error codes (F6)**  
The v0.1 taxonomy had `cuda_unavailable` but did not distinguish between "no GPU at all" and "GPU present but too old" or "GPU present but driver too old." These are different failure modes with different user actions. Now three distinct codes.

**Z.15 — Specified CLI exit codes (F6)**  
The v0.1 spec mentioned exit code 2 for configuration errors in F1 but did not define a consistent exit code scheme across all commands. Now: 0 = success, 1 = partial failure (some batch rows failed), 2 = fatal setup/config error.

**Z.16 — Specified index.json atomic write strategy (F7)**  
The v0.1 spec noted that index generation should be "idempotent and safe under concurrent jobs" as an acceptance criterion but provided no mechanism. Now specifies atomic write via temp-file-then-rename, or alternatively making index generation a dedicated `setup` step.

**Z.17 — Added `/scratch` purge warning for Explorer (F7)**  
Explorer's `/scratch` filesystem is periodically purged. If a user places checkpoints there, they will lose them. The v0.1 appendix defaults were correct (`/projects` for base dir) but the warning was not explicit enough. Now called out in F7 and Appendix A.

**Z.18 — Specified `X-Api-Key` source (F3)**  
The v0.1 spec said "simple X-Api-Key (optional)" without specifying where the key comes from. Now explicitly gated on the `PERIOGT_API_KEY` environment variable, with clear disabled-by-default behavior.

**Z.19 — Added model loading timing requirement (F2)**  
Batch mode must load the model once at startup, then iterate rows. The v0.1 spec said "streaming read" but did not address whether model initialization happens per-row or once. Per-row loading would make batch mode unusable (minutes of overhead per row). Now an explicit acceptance criterion.

**Z.20 — Added CLI framework choice (F2)**  
The v0.1 spec listed CLI commands but did not name the CLI framework. Now specifies `click`.

**Z.21 — Added `hpc_cli_smoke_test.sh` integration test (F10)**  
The v0.1 spec only referenced the existing `smoke_test.sh` (which tests the HTTP API). Added a CLI-specific smoke test script for non-server workflows.

**Z.22 — Added PR-1 regression gate (Section 6)**  
PR-1 modifies shared runtime code that the production Modal deployment depends on. The v0.1 spec noted "non-breaking defaults" but did not make Modal stability an explicit acceptance criterion. Now stated as a hard gate.

**Z.23 — Corrected and expanded reference links (Section 9)**  
The v0.1 spec linked to Apptainer 1.0 docs. CADES Baseline runs 1.2.5, so the links now point to 1.2 docs. Added links for CADES Baseline user guide, Slurm docs, Explorer GPU overview, H200 quick start, and NVIDIA CUDA driver compatibility notes.

**Z.24 — Added GPU compatibility matrix (Section 11)**  
Concrete reference table mapping every GPU available on both clusters to its CUDA/PyTorch compatibility status, with minimum driver version. The v0.1 spec mentioned V100/A100/H100/H200 support in the goals but did not provide a matrix.

**Z.25 — Renamed `logging.py` to `log.py` (Section 4.2)**  
`logging` shadows Python's stdlib `logging` module. Importing `from periogt_hpc import logging` would break standard library logging throughout the application. Renamed to `log.py`.

**Z.26 — Added memory footprint note**  
The finetuned checkpoint archive is ~5.9 GB; when extracted and loaded into GPU memory alongside the pretrained model, the total GPU memory consumption is significant. The Slurm templates request 32 GB system RAM, which is adequate, but `doctor` should report estimated memory requirements so users can select appropriate GPU types (e.g., V100-16GB may be tight; V100-32GB, A100-40GB, H100-80GB, H200-140GB are all comfortable).
