# Slurm Templates

Slurm templates for PerioGT HPC workflows:

- `predict.sbatch` single SMILES prediction
- `batch.sbatch` CSV batch prediction
- `server.sbatch` optional FastAPI server mode
- `setup_env.sh` shared environment bootstrap for both CADES and Explorer style setups

## Cluster Notes

- Templates include both CADES and Explorer partition hints and must be edited for your allocation/account.
- Explorer checkpoint storage should be on `/projects` (persistent), not `/scratch` (purgeable).
- For GPU workflows with CUDA 12.6, ensure node driver version is `>= 560.28`.

## Required Environment

`setup_env.sh` configures defaults for:

- `DGLBACKEND`
- `PERIOGT_BASE_DIR`
- `PERIOGT_CHECKPOINT_DIR`
- `PERIOGT_RESULTS_DIR`
- `PERIOGT_CONTAINER`
- `USE_APPTAINER`
- `PYTHONPATH`
- `PERIOGT_RUNTIME_PACKAGE_DIR`
- `PERIOGT_SRC_DIR`
- `APPTAINER_BIND`

Critical values to verify before submitting jobs:

- `PERIOGT_CONTAINER` points to a valid `.sif` when `USE_APPTAINER=1`.
- `PERIOGT_CHECKPOINT_DIR` points to staged artifacts.
- `APPTAINER_BIND` includes checkpoint/results/repo paths.

## Initialize Environment

```bash
source services/hpc/slurm/setup_env.sh
```

## Submit Jobs

Single prediction:

```bash
sbatch --export=SMILES='*CC*',PROPERTY=tg services/hpc/slurm/predict.sbatch
```

Batch prediction:

```bash
sbatch --export=INPUT_CSV=/path/input.csv,PROPERTY=eps services/hpc/slurm/batch.sbatch
```

Optional server mode:

```bash
sbatch services/hpc/slurm/server.sbatch
```

## Access Server Mode

If running `server.sbatch`, connect via SSH tunnel:

```bash
ssh -L 8000:<compute-node>:8000 <user>@<login-node>
```

Then open `http://localhost:8000/v1/docs`.
