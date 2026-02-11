from __future__ import annotations

from pathlib import Path

import pytest

from periogt_hpc.config import resolve_config
from periogt_hpc.errors import PerioGTError


class _CpuDevice:
    type = "cpu"


def test_resolve_config_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "base"
    checkpoints = base / "checkpoints"
    results = base / "results"
    src = tmp_path / "src" / "PerioGT_common"
    runtime = tmp_path / "runtime"
    (runtime / "periogt_runtime").mkdir(parents=True)
    checkpoints.mkdir(parents=True)
    src.mkdir(parents=True)

    monkeypatch.setattr("periogt_hpc.config._resolve_device", lambda _: _CpuDevice())
    monkeypatch.setenv("PERIOGT_BASE_DIR", str(base))
    monkeypatch.setenv("PERIOGT_CHECKPOINT_DIR", str(checkpoints))
    monkeypatch.setenv("PERIOGT_RESULTS_DIR", str(results))
    monkeypatch.setenv("PERIOGT_SRC_DIR", str(src))
    monkeypatch.setenv("PERIOGT_RUNTIME_PACKAGE_DIR", str(runtime))

    cfg = resolve_config()
    assert cfg.base_dir == base.resolve()
    assert cfg.checkpoint_dir == checkpoints.resolve()
    assert cfg.results_dir == results.resolve()
    assert cfg.src_dir == src.resolve()
    assert cfg.device.type == "cpu"


def test_missing_checkpoint_dir_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "src" / "PerioGT_common"
    src.mkdir(parents=True)

    monkeypatch.setattr("periogt_hpc.config._resolve_device", lambda _: _CpuDevice())
    monkeypatch.setenv("PERIOGT_CHECKPOINT_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("PERIOGT_SRC_DIR", str(src))

    with pytest.raises(PerioGTError) as exc:
        resolve_config(require_checkpoint_dir=True, require_source_dir=True)
    assert exc.value.code == "checkpoint_missing"

