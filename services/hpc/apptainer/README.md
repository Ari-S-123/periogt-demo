# Apptainer Packaging

Primary HPC packaging path for PerioGT.

## Build

```bash
bash services/hpc/apptainer/build.sh --fakeroot
```

## Run (GPU)

```bash
apptainer exec --nv \
  --bind /projects/mygroup/periogt:/data \
  services/hpc/apptainer/periogt.sif \
  python -m periogt_hpc doctor
```

## Runtime Notes

- Always use `--nv` on GPU nodes.
- Set `--bind` explicitly for checkpoint and results directories.
- If writes fail in read-only image mode, use `--writable-tmpfs` or set `TMPDIR` to a writable bound path.
- If `torch.cuda.is_available()` is false despite a visible driver, verify Apptainer `nvliblist.conf` supports CUDA 12 libraries on your cluster.

