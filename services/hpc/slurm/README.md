# Slurm Templates

Templates target both CADES Baseline and Northeastern Explorer. Update partition/account/path fields before first use.

On Explorer, keep checkpoints on `/projects` (persistent). Do not store checkpoints on `/scratch` because it is purgeable.

## Required exports

- `PERIOGT_CONTAINER` path to `.sif` (if `USE_APPTAINER=1`)
- `PERIOGT_CHECKPOINT_DIR` persistent checkpoint path
- `PERIOGT_RESULTS_DIR` writable results path
- `APPTAINER_BIND` explicit host mounts

## Setup

```bash
source services/hpc/slurm/setup_env.sh
```

## Single Prediction

```bash
sbatch --export=SMILES='*CC*',PROPERTY=tg services/hpc/slurm/predict.sbatch
```

## Batch Prediction

```bash
sbatch --export=INPUT_CSV=/path/input.csv,PROPERTY=eps services/hpc/slurm/batch.sbatch
```

## Optional Server

```bash
sbatch services/hpc/slurm/server.sbatch
```

Use SSH tunneling to access from local machine:

```bash
ssh -L 8000:<compute-node>:8000 <user>@<login-node>
```
