# Conda Fallback Environment

Use this path when Apptainer is unavailable.

## Install

```bash
bash services/hpc/conda/install.sh periogt
conda activate periogt
```

The install script performs a two-step install:

1. Create/update a base conda env from `environment.yml`.
2. Install PyTorch + DGL via pip using CUDA-specific wheel indexes.

This is required because `--index-url` / `--find-links` are not reliable directly inside `environment.yml` pip sections for this setup.

## Verify

```bash
python -m periogt_hpc doctor
```

