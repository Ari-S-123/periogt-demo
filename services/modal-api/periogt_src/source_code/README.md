# Vendored PerioGT Source Tree

This directory contains the vendored upstream PerioGT project source used by the runtime in this repository.

It is consumed by:

- `services/modal-api/periogt_runtime` (Modal backend path)
- `services/hpc/periogt_hpc` (HPC CLI/server path via shared runtime imports)

## Local Integration Notes

- Runtime defaults expect `PerioGT_common` at:
  - Modal default: `/root/periogt_src/source_code/PerioGT_common`
  - HPC/local override: `PERIOGT_SRC_DIR`
- Shared runtime adds the resolved source dir to `sys.path` before model import.
- If this source tree is moved, update `PERIOGT_SRC_DIR` accordingly.

## Directory Overview

- `PerioGT_common/`: shared model/data code used by current inference runtime.
- `PerioGT_with_cond/`: conditional pipeline variant.
- `PerioGT_copolym/`: copolymer-focused variant.

## Upstream Workflow Context

The original source includes scripts for:

- pretraining (`PerioGT_common/scripts/pretrain.sh`)
- fine-tuning (`PerioGT_common/scripts/finetune.sh`)
- evaluation (`PerioGT_common/scripts/evaluation.sh`)
- dataset preparation (`prepare_pt_dataset.sh`, `prepare_ft_dataset.sh`)

In this repository, deployment paths primarily rely on pretrained and finetuned checkpoints plus runtime inference, not full retraining during normal operation.
