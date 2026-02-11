"""Runtime configuration helpers shared by Modal and HPC entrypoints."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = "/vol/checkpoints"
DEFAULT_SRC_DIR = "/root/periogt_src/source_code/PerioGT_common"


def get_checkpoint_dir() -> Path:
    """Resolve checkpoint directory with backward-compatible defaults."""
    return Path(os.environ.get("PERIOGT_CHECKPOINT_DIR", DEFAULT_CHECKPOINT_DIR)).resolve()


def get_src_dir() -> Path:
    """Resolve vendored PerioGT source directory with backward-compatible defaults."""
    return Path(os.environ.get("PERIOGT_SRC_DIR", DEFAULT_SRC_DIR)).resolve()


def add_src_dir_to_syspath(src_dir: Path | None = None) -> Path:
    """Ensure PerioGT source directory is importable and return resolved path."""
    resolved = (src_dir or get_src_dir()).resolve()
    as_str = str(resolved)
    if as_str not in sys.path:
        sys.path.insert(0, as_str)
        logger.info("Added PerioGT source dir to PYTHONPATH: %s", as_str)
    return resolved


def get_model_config_path(src_dir: Path | None = None) -> Path:
    """Return path to the vendored PerioGT config.yaml."""
    return add_src_dir_to_syspath(src_dir) / "config.yaml"


def get_requested_device(default: str = "auto") -> str:
    """Read requested device from env (cpu|cuda|auto)."""
    raw = os.environ.get("PERIOGT_DEVICE", default).strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw not in {"cpu", "cuda"}:
        logger.warning("Invalid PERIOGT_DEVICE=%s, defaulting to auto", raw)
        return "auto"
    return raw


def resolve_torch_device(requested: str | None = None):
    """Resolve torch device while preserving existing auto behavior."""
    import torch

    mode = (requested or get_requested_device()).lower()
    cuda_available = torch.cuda.is_available()

    if mode == "cpu":
        return torch.device("cpu")
    if mode == "cuda":
        if not cuda_available:
            raise RuntimeError(
                "PERIOGT_DEVICE=cuda requested but CUDA is unavailable. "
                "Set PERIOGT_DEVICE=cpu or run with GPU support."
            )
        return torch.device("cuda")

    if cuda_available:
        return torch.device("cuda")

    logger.warning("CUDA unavailable; falling back to CPU inference.")
    return torch.device("cpu")
