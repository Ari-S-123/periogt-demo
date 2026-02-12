from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

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


def test_setup_recovers_from_stale_downloading_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ckpt = tmp_path / "checkpoints"
    (ckpt / "finetuned_ckpt" / "eps").mkdir(parents=True)
    (ckpt / "pretrained_ckpt").mkdir(parents=True)
    (ckpt / "finetuned_ckpt" / "eps" / "best_model.pth").write_bytes(b"x")
    (ckpt / "pretrained_ckpt" / "pretrain.pth").write_bytes(b"x")

    marker = ckpt / ".downloading"
    marker.write_text("downloading", encoding="utf-8")
    old_timestamp = marker.stat().st_mtime - 600
    os.utime(marker, (old_timestamp, old_timestamp))
    monkeypatch.setenv("PERIOGT_CHECKPOINT_DOWNLOAD_STALE_SECONDS", "300")

    index = ensure_checkpoints(volume=None, checkpoint_dir=ckpt, skip_download=True)

    assert "eps" in index
    assert (ckpt / ".ready").exists()
    assert not marker.exists()


def test_setup_blocks_when_downloading_marker_is_fresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ckpt = tmp_path / "checkpoints"
    (ckpt / "finetuned_ckpt" / "eps").mkdir(parents=True)
    (ckpt / "pretrained_ckpt").mkdir(parents=True)
    (ckpt / "finetuned_ckpt" / "eps" / "best_model.pth").write_bytes(b"x")
    (ckpt / "pretrained_ckpt" / "pretrain.pth").write_bytes(b"x")

    marker = ckpt / ".downloading"
    marker.write_text("downloading", encoding="utf-8")
    monkeypatch.setenv("PERIOGT_CHECKPOINT_DOWNLOAD_STALE_SECONDS", "300")

    with pytest.raises(RuntimeError, match="Another container is currently downloading checkpoints"):
        ensure_checkpoints(volume=None, checkpoint_dir=ckpt, skip_download=True)
