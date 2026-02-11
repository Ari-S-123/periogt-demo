from __future__ import annotations

from pathlib import Path

from periogt_runtime.runtime_config import get_checkpoint_dir, get_src_dir


def test_checkpoint_default(monkeypatch) -> None:
    monkeypatch.delenv("PERIOGT_CHECKPOINT_DIR", raising=False)
    assert str(get_checkpoint_dir()) == str(Path("/vol/checkpoints").resolve())


def test_checkpoint_override(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "ckpts"
    monkeypatch.setenv("PERIOGT_CHECKPOINT_DIR", str(custom))
    assert get_checkpoint_dir() == custom.resolve()


def test_src_default(monkeypatch) -> None:
    monkeypatch.delenv("PERIOGT_SRC_DIR", raising=False)
    assert str(get_src_dir()) == str(Path("/root/periogt_src/source_code/PerioGT_common").resolve())


def test_src_override(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "source"
    monkeypatch.setenv("PERIOGT_SRC_DIR", str(custom))
    assert get_src_dir() == custom.resolve()

