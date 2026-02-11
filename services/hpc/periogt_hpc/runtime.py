"""Shared runtime bootstrap for CLI and server execution."""

from __future__ import annotations

import json
import logging
import os
import pickle
from dataclasses import dataclass

from .config import HpcConfig, ensure_runtime_package_path
from .errors import PerioGTError

logger = logging.getLogger(__name__)


@dataclass
class RuntimeState:
    models: object
    scaler: object
    label_mean: dict[str, float]
    label_std: dict[str, float]
    property_index: dict


def _load_label_stats(checkpoint_dir) -> tuple[dict[str, float], dict[str, float]]:
    path = checkpoint_dir / "label_stats.json"
    if not path.exists():
        raise PerioGTError(
            "checkpoint_missing",
            "Required artifact missing: label_stats.json",
            details={"path": str(path)},
        )
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return ({k: float(v["mean"]) for k, v in raw.items()}, {k: float(v["std"]) for k, v in raw.items()})


def _load_scaler(checkpoint_dir):
    path = checkpoint_dir / "descriptor_scaler.pkl"
    if not path.exists():
        raise PerioGTError(
            "checkpoint_missing",
            "Required artifact missing: descriptor_scaler.pkl",
            details={"path": str(path)},
        )
    with path.open("rb") as handle:
        return pickle.load(handle)


def _load_property_index(checkpoint_dir) -> dict:
    path = checkpoint_dir / "index.json"
    if not path.exists():
        raise PerioGTError(
            "checkpoint_missing",
            "Required artifact missing: index.json. Run periogt_hpc setup first.",
            details={"path": str(path)},
        )
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not data:
        raise PerioGTError(
            "checkpoint_missing",
            "index.json exists but is empty or invalid.",
            details={"path": str(path)},
        )
    return data


def load_runtime_state(cfg: HpcConfig) -> RuntimeState:
    """Load shared runtime dependencies and all inference artifacts/models."""
    ensure_runtime_package_path(cfg.runtime_package_dir)
    os.environ["PERIOGT_CHECKPOINT_DIR"] = str(cfg.checkpoint_dir)
    os.environ["PERIOGT_SRC_DIR"] = str(cfg.src_dir)
    os.environ["PERIOGT_DEVICE"] = cfg.device.type

    try:
        from periogt_runtime.model_loader import load_all_models
    except Exception as exc:
        raise PerioGTError(
            "model_load_failed",
            "Failed to import periogt_runtime.model_loader.",
            details={"error": str(exc)},
        ) from exc

    property_index = _load_property_index(cfg.checkpoint_dir)
    label_mean, label_std = _load_label_stats(cfg.checkpoint_dir)
    scaler = _load_scaler(cfg.checkpoint_dir)

    models = load_all_models(
        property_index=property_index,
        pretrained_dir=str(cfg.checkpoint_dir),
        device=cfg.device.type,
    )
    if models.pretrained_model is None or not models.finetuned_models:
        raise PerioGTError(
            "model_load_failed",
            "Model loading did not produce required pretrained and finetuned models.",
            details={"loaded_properties": sorted(models.finetuned_models.keys())},
        )

    logger.info("Loaded %d finetuned models.", len(models.finetuned_models))
    return RuntimeState(
        models=models,
        scaler=scaler,
        label_mean=label_mean,
        label_std=label_std,
        property_index=property_index,
    )

