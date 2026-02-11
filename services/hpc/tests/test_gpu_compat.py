from __future__ import annotations

import pytest

from periogt_hpc.config import _resolve_device
from periogt_hpc.errors import PerioGTError


class _FakeCuda:
    def __init__(self, available: bool, capability: tuple[int, int]):
        self._available = available
        self._capability = capability

    def is_available(self) -> bool:
        return self._available

    def get_device_capability(self, _idx: int) -> tuple[int, int]:
        return self._capability

    def get_device_name(self, _idx: int) -> str:
        return "Fake GPU"


class _FakeTorch:
    __version__ = "2.6.0"

    class version:
        cuda = "12.6"

    def __init__(self, available: bool, capability: tuple[int, int]):
        self.cuda = _FakeCuda(available, capability)

    @staticmethod
    def device(kind: str):
        class _Device:
            def __init__(self, t: str):
                self.type = t

        return _Device(kind)


def test_resolve_device_cuda_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("periogt_hpc.config.torch", _FakeTorch(False, (0, 0)))
    monkeypatch.setattr(
        "periogt_hpc.config.detect_gpu_details",
        lambda: {
            "cuda_available": False,
            "gpu_name": None,
            "compute_capability": None,
            "driver_version": None,
        },
    )
    with pytest.raises(PerioGTError) as exc:
        _resolve_device("cuda")
    assert exc.value.code == "cuda_unavailable"


def test_resolve_device_gpu_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("periogt_hpc.config.torch", _FakeTorch(True, (6, 0)))
    monkeypatch.setattr(
        "periogt_hpc.config.detect_gpu_details",
        lambda: {
            "cuda_available": True,
            "gpu_name": "Old GPU",
            "compute_capability": "6.0",
            "driver_version": "560.28",
        },
    )
    with pytest.raises(PerioGTError) as exc:
        _resolve_device("cuda")
    assert exc.value.code == "gpu_unsupported"


def test_resolve_device_driver_incompatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("periogt_hpc.config.torch", _FakeTorch(True, (8, 0)))
    monkeypatch.setattr(
        "periogt_hpc.config.detect_gpu_details",
        lambda: {
            "cuda_available": True,
            "gpu_name": "A100",
            "compute_capability": "8.0",
            "driver_version": "550.10",
        },
    )
    with pytest.raises(PerioGTError) as exc:
        _resolve_device("cuda")
    assert exc.value.code == "driver_incompatible"

