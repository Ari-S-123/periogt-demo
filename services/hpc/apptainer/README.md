# Apptainer Packaging

Primary HPC packaging path for PerioGT (`nvidia/cuda:12.6.0-runtime-ubuntu22.04` base image).

## Build Image

```bash
# default output: services/hpc/apptainer/periogt.sif
bash services/hpc/apptainer/build.sh --fakeroot

# custom output path
bash services/hpc/apptainer/build.sh --fakeroot --output /path/periogt.sif
```

`build.sh` prints a SHA256 digest after successful build.

## Run Diagnostics

```bash
apptainer exec --nv \
  --bind /projects/mygroup/periogt/checkpoints:/projects/mygroup/periogt/checkpoints \
  --bind /projects/mygroup/periogt/results:/projects/mygroup/periogt/results \
  services/hpc/apptainer/periogt.sif \
  python -m periogt_hpc doctor
```

## Run Prediction

```bash
apptainer exec --nv \
  --bind /projects/mygroup/periogt:/projects/mygroup/periogt \
  services/hpc/apptainer/periogt.sif \
  python -m periogt_hpc predict --smiles "*CC*" --property tg --format json
```

## Required Runtime Flags

- `--nv`: required for GPU execution.
- `--bind`: required for checkpoint/results/repo paths not mounted by default.
- `--writable-tmpfs`: recommended if Python temp/cache writes fail due to read-only image filesystem.

## Compatibility Notes

- CUDA 12.6 runtime requires host NVIDIA driver `>= 560.28`.
- If `torch.cuda.is_available()` is false even with `--nv`, inspect host/container driver library binding and Apptainer `nvliblist.conf` compatibility for CUDA 12.
- Keep `DGLBACKEND=pytorch` in runtime environment (already set in container `%environment`).
