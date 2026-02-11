"""HPC configuration, compatibility checks, and diagnostics."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import torch
except Exception:  # pragma: no cover - optional during setup-only environments
    torch = None  # type: ignore[assignment]

from .errors import PerioGTError

logger = logging.getLogger(__name__)

MIN_DRIVER_VERSION = (560, 28)
MIN_COMPUTE_CAPABILITY = (7, 0)


@dataclass
class HpcConfig:
    base_dir: Path
    checkpoint_dir: Path
    results_dir: Path
    src_dir: Path
    device_request: str
    device: Any
    runtime_package_dir: Path


@dataclass
class DoctorReport:
    info: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    fatals: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if self.fatals:
            return 2
        if self.warnings:
            return 1
        return 0

    @property
    def verdict(self) -> str:
        if self.fatals:
            return "FAIL"
        if self.warnings:
            return "WARN"
        return "PASS"


def _parse_version_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return tuple()
    parts: list[int] = []
    for token in value.strip().split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _version_lt(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    max_len = max(len(left), len(right))
    l = left + (0,) * (max_len - len(left))
    r = right + (0,) * (max_len - len(right))
    return l < r


def find_repo_root() -> Path | None:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "services" / "modal-api" / "periogt_runtime").exists():
            return parent
    return None


def _default_src_dir(repo_root: Path | None) -> Path:
    candidates = []
    if repo_root:
        candidates.append(
            repo_root
            / "services"
            / "modal-api"
            / "periogt_src"
            / "source_code"
            / "PerioGT_common"
        )
    candidates.extend(
        [
            Path("/opt/periogt/services/modal-api/periogt_src/source_code/PerioGT_common"),
            Path("/root/periogt_src/source_code/PerioGT_common"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _default_runtime_package_dir(repo_root: Path | None) -> Path:
    candidates = []
    if repo_root:
        candidates.append(repo_root / "services" / "modal-api")
    candidates.extend(
        [
            Path("/opt/periogt/services/modal-api"),
            Path.cwd(),
        ]
    )
    for candidate in candidates:
        if (candidate / "periogt_runtime").exists():
            return candidate.resolve()
    return candidates[0].resolve()


def ensure_runtime_package_path(runtime_package_dir: Path) -> Path:
    """Ensure periogt_runtime is importable by adding its parent directory to sys.path."""
    resolved = runtime_package_dir.resolve()
    if not (resolved / "periogt_runtime").exists():
        raise PerioGTError(
            "checkpoint_missing",
            "Could not locate periogt_runtime package directory.",
            details={"runtime_package_dir": str(resolved)},
        )
    as_str = str(resolved)
    if as_str not in sys.path:
        sys.path.insert(0, as_str)
    return resolved


def detect_driver_version() -> str | None:
    """Read NVIDIA driver version from nvidia-smi if available."""
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if proc.returncode != 0:
        return None

    first_line = (proc.stdout or "").strip().splitlines()
    if not first_line:
        return None
    return first_line[0].strip()


def _mk_device(kind: str):
    if torch is None:
        class _Device:
            def __init__(self, t: str):
                self.type = t

        return _Device(kind)
    return torch.device(kind)


def detect_gpu_details() -> dict[str, Any]:
    details: dict[str, Any] = {
        "cuda_available": bool(torch is not None and torch.cuda.is_available()),
        "gpu_name": None,
        "compute_capability": None,
        "driver_version": detect_driver_version(),
    }
    if not details["cuda_available"]:
        return details

    try:
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        details["gpu_name"] = name
        details["compute_capability"] = f"{cap[0]}.{cap[1]}"
    except Exception:
        pass

    return details


def _resolve_device(mode: str):
    request = (mode or "auto").lower().strip()
    if request not in {"auto", "cpu", "cuda"}:
        raise PerioGTError(
            "validation_error",
            "PERIOGT_DEVICE must be one of: auto, cpu, cuda.",
            details={"PERIOGT_DEVICE": mode},
        )

    gpu = detect_gpu_details()
    driver_tuple = _parse_version_tuple(gpu["driver_version"])

    if request == "cpu":
        return _mk_device("cpu")

    if request == "cuda":
        if torch is None:
            raise PerioGTError(
                "cuda_unavailable",
                "PyTorch is not installed in this environment.",
            )
        if not gpu["cuda_available"]:
            raise PerioGTError(
                "cuda_unavailable",
                "PERIOGT_DEVICE=cuda requested but CUDA is unavailable. "
                "Set PERIOGT_DEVICE=cpu or ensure --nv GPU support is enabled.",
            )
        cap = torch.cuda.get_device_capability(0)
        if cap < MIN_COMPUTE_CAPABILITY:
            raise PerioGTError(
                "gpu_unsupported",
                "Detected GPU does not meet minimum compute capability 7.0.",
                details={
                    "gpu_name": gpu["gpu_name"],
                    "compute_capability": f"{cap[0]}.{cap[1]}",
                    "minimum": "7.0",
                },
            )
        if driver_tuple and _version_lt(driver_tuple, MIN_DRIVER_VERSION):
            raise PerioGTError(
                "driver_incompatible",
                "NVIDIA driver is too old for CUDA 12.6.",
                details={
                    "detected": gpu["driver_version"],
                    "minimum": "560.28",
                },
            )
        return _mk_device("cuda")

    # auto
    if not gpu["cuda_available"]:
        logger.warning("CUDA unavailable; falling back to CPU.")
        return _mk_device("cpu")

    cap = torch.cuda.get_device_capability(0)
    if cap < MIN_COMPUTE_CAPABILITY:
        logger.warning(
            "GPU %s has compute capability %s.%s (< 7.0); falling back to CPU.",
            gpu["gpu_name"],
            cap[0],
            cap[1],
        )
        return _mk_device("cpu")

    if driver_tuple and _version_lt(driver_tuple, MIN_DRIVER_VERSION):
        logger.warning(
            "Driver %s is older than minimum 560.28; falling back to CPU.",
            gpu["driver_version"],
        )
        return _mk_device("cpu")

    return _mk_device("cuda")


def resolve_config(
    *,
    require_checkpoint_dir: bool = True,
    require_source_dir: bool = True,
    create_results_dir: bool = True,
) -> HpcConfig:
    """Resolve and validate runtime configuration for HPC execution."""
    repo_root = find_repo_root()
    home = Path.home()

    base_dir = Path(os.environ.get("PERIOGT_BASE_DIR", str(home / "periogt"))).expanduser().resolve()
    checkpoint_dir = Path(
        os.environ.get("PERIOGT_CHECKPOINT_DIR", str(base_dir / "checkpoints"))
    ).expanduser().resolve()
    results_dir = Path(
        os.environ.get("PERIOGT_RESULTS_DIR", str(base_dir / "results"))
    ).expanduser().resolve()
    src_dir = Path(
        os.environ.get("PERIOGT_SRC_DIR", str(_default_src_dir(repo_root)))
    ).expanduser().resolve()
    runtime_package_dir = Path(
        os.environ.get("PERIOGT_RUNTIME_PACKAGE_DIR", str(_default_runtime_package_dir(repo_root)))
    ).expanduser().resolve()

    device_request = os.environ.get("PERIOGT_DEVICE", "auto")
    device = _resolve_device(device_request)

    if require_checkpoint_dir and not checkpoint_dir.exists():
        raise PerioGTError(
            "checkpoint_missing",
            "Required checkpoint directory does not exist.",
            details={"checkpoint_dir": str(checkpoint_dir)},
        )
    if require_source_dir and not src_dir.exists():
        raise PerioGTError(
            "checkpoint_missing",
            "Required PerioGT source directory does not exist.",
            details={"src_dir": str(src_dir)},
        )

    if create_results_dir:
        results_dir.mkdir(parents=True, exist_ok=True)

    cfg = HpcConfig(
        base_dir=base_dir,
        checkpoint_dir=checkpoint_dir,
        results_dir=results_dir,
        src_dir=src_dir,
        device_request=device_request,
        device=device,
        runtime_package_dir=runtime_package_dir,
    )

    logger.info("PERIOGT_BASE_DIR=%s", cfg.base_dir)
    logger.info("PERIOGT_CHECKPOINT_DIR=%s", cfg.checkpoint_dir)
    logger.info("PERIOGT_RESULTS_DIR=%s", cfg.results_dir)
    logger.info("PERIOGT_SRC_DIR=%s", cfg.src_dir)
    logger.info("PERIOGT_DEVICE=%s -> %s", cfg.device_request, cfg.device.type)
    logger.info("PERIOGT_RUNTIME_PACKAGE_DIR=%s", cfg.runtime_package_dir)

    return cfg


def _estimate_checkpoint_size_bytes(checkpoint_dir: Path) -> int:
    total = 0
    for path in checkpoint_dir.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def run_doctor(cfg: HpcConfig) -> DoctorReport:
    report = DoctorReport()
    gpu = detect_gpu_details()

    report.info["python_version"] = platform.python_version()
    report.info["platform"] = platform.platform()
    report.info["torch_version"] = getattr(torch, "__version__", "unavailable")
    report.info["torch_cuda_version"] = getattr(getattr(torch, "version", None), "cuda", None)
    report.info["dglbackend"] = os.environ.get("DGLBACKEND", "")
    report.info["cuda_available"] = gpu["cuda_available"]
    report.info["gpu_name"] = gpu["gpu_name"]
    report.info["compute_capability"] = gpu["compute_capability"]
    report.info["driver_version"] = gpu["driver_version"]
    report.info["device"] = cfg.device.type
    report.info["checkpoint_dir"] = str(cfg.checkpoint_dir)
    report.info["results_dir"] = str(cfg.results_dir)
    report.info["src_dir"] = str(cfg.src_dir)
    report.info["runtime_package_dir"] = str(cfg.runtime_package_dir)

    if report.info["dglbackend"] != "pytorch":
        report.warnings.append(
            "DGLBACKEND is not set to 'pytorch'. Set DGLBACKEND=pytorch in your environment."
        )

    if not cfg.src_dir.exists():
        report.fatals.append(f"Source directory missing: {cfg.src_dir}")
    if not cfg.checkpoint_dir.exists():
        report.fatals.append(f"Checkpoint directory missing: {cfg.checkpoint_dir}")

    driver_tuple = _parse_version_tuple(gpu["driver_version"])
    if gpu["cuda_available"] and driver_tuple and _version_lt(driver_tuple, MIN_DRIVER_VERSION):
        report.fatals.append(
            f"Driver incompatible: detected {gpu['driver_version']}, required >= 560.28 for CUDA 12.6."
        )
    if gpu["cuda_available"] and torch is not None:
        cap = torch.cuda.get_device_capability(0)
        if cap < MIN_COMPUTE_CAPABILITY:
            report.fatals.append(
                f"Unsupported GPU compute capability {cap[0]}.{cap[1]} (< 7.0)."
            )

    if not gpu["cuda_available"] and cfg.device_request.lower() == "cuda":
        report.fatals.append("PERIOGT_DEVICE=cuda requested but CUDA unavailable.")

    if gpu["driver_version"] and not gpu["cuda_available"]:
        report.warnings.append(
            "Driver detected but torch.cuda.is_available() is false; check Apptainer --nv and nvliblist.conf."
        )

    try:
        ensure_runtime_package_path(cfg.runtime_package_dir)
        from periogt_runtime.checkpoint_manager import missing_required_artifacts

        missing = missing_required_artifacts(cfg.checkpoint_dir)
        if missing:
            report.fatals.append(
                "Missing artifacts: "
                + ", ".join(f"{k}={v}" for k, v in sorted(missing.items()))
            )
        report.info["checkpoint_size_bytes"] = _estimate_checkpoint_size_bytes(cfg.checkpoint_dir)
        report.info["checkpoint_size_gb"] = round(report.info["checkpoint_size_bytes"] / (1024**3), 3)
    except Exception as exc:
        report.fatals.append(f"Artifact diagnostics failed: {exc}")

    try:
        import dgl  # type: ignore

        report.info["dgl_version"] = getattr(dgl, "__version__", "unknown")
    except Exception as exc:
        report.fatals.append(f"DGL import failed: {exc}")

    return report
