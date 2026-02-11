from __future__ import annotations

import json
from pathlib import Path

from periogt_runtime.checkpoint_manager import ensure_checkpoints, missing_required_artifacts


def test_setup_skip_download_is_idempotent(tmp_path: Path) -> None:
    ckpt = tmp_path / "checkpoints"
    (ckpt / "finetuned_ckpt" / "eps").mkdir(parents=True)
    (ckpt / "pretrained_ckpt").mkdir(parents=True)
    (ckpt / "finetuned_ckpt" / "eps" / "best_model.pth").write_bytes(b"x")
    (ckpt / "pretrained_ckpt" / "pretrain.pth").write_bytes(b"x")

    first = ensure_checkpoints(volume=None, checkpoint_dir=ckpt, skip_download=True)
    second = ensure_checkpoints(volume=None, checkpoint_dir=ckpt, skip_download=True)

    assert first == second
    index = json.loads((ckpt / "index.json").read_text(encoding="utf-8"))
    assert "eps" in index


def test_missing_required_artifacts(tmp_path: Path) -> None:
    missing = missing_required_artifacts(tmp_path)
    assert "index_json" in missing
    assert "descriptor_scaler_pkl" in missing

