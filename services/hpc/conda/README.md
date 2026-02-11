# Conda Fallback Environment

Use this path when Apptainer is unavailable or not preferred on your cluster.

## Install

```bash
bash services/hpc/conda/install.sh periogt
conda activate periogt
```

## What `install.sh` Does

1. Creates or updates a base env from `environment.yml`.
2. Installs GPU-specific PyTorch and DGL wheels via pip indexes.
3. Installs additional runtime/test deps (`dgllife`, `mordred`, `pytest`).
4. Installs local package `services/hpc`.
5. Writes `activate.d/periogt.sh` with:
   - `DGLBACKEND=pytorch`
   - `PYTHONPATH` including `services/modal-api` and `services/hpc`
   - `PERIOGT_RUNTIME_PACKAGE_DIR`
   - `PERIOGT_SRC_DIR`

This two-step approach is intentional because pip wheel index flags are not reliably represented inside conda `environment.yml` for this setup.

## Verify Environment

```bash
python -m periogt_hpc doctor
```

## Smoke Test

```bash
bash scripts/hpc_cli_smoke_test.sh <PERIOGT_CHECKPOINT_DIR>
# or
pwsh scripts/hpc_cli_smoke_test.ps1 <PERIOGT_CHECKPOINT_DIR>
```

## Notes

- CUDA mode still depends on host GPU/driver compatibility (`>= 560.28` for CUDA 12.6).
- Use `PERIOGT_DEVICE=cpu` explicitly on CPU-only nodes.
