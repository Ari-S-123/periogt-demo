"""Error taxonomy and mapping for PerioGT HPC CLI/server."""

from __future__ import annotations

from dataclasses import dataclass

ERROR_HTTP_STATUS: dict[str, int] = {
    "validation_error": 422,
    "unsupported_property": 422,
    "checkpoint_missing": 500,
    "checksum_mismatch": 500,
    "model_load_failed": 500,
    "cuda_unavailable": 500,
    "gpu_unsupported": 500,
    "driver_incompatible": 500,
    "internal_error": 500,
}

ERROR_EXIT_CODE: dict[str, int] = {
    "validation_error": 2,
    "unsupported_property": 2,
    "checkpoint_missing": 2,
    "checksum_mismatch": 2,
    "model_load_failed": 2,
    "cuda_unavailable": 2,
    "gpu_unsupported": 2,
    "driver_incompatible": 2,
    "internal_error": 2,
}


@dataclass
class PerioGTError(Exception):
    """Typed error that carries stable code + operator-facing metadata."""

    code: str
    message: str
    details: dict | list | str | None = None

    @property
    def http_status(self) -> int:
        return ERROR_HTTP_STATUS.get(self.code, 500)

    @property
    def exit_code(self) -> int:
        return ERROR_EXIT_CODE.get(self.code, 2)

    def to_dict(self) -> dict:
        payload = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


def _classify_value_error(message: str) -> PerioGTError:
    text = message.lower()
    if "unsupported property" in text:
        return PerioGTError("unsupported_property", message)
    if "smiles" in text or "connection point" in text:
        return PerioGTError("validation_error", message)
    return PerioGTError("validation_error", message)


def map_exception(exc: Exception) -> PerioGTError:
    """Map an arbitrary exception into a stable taxonomy code."""
    if isinstance(exc, PerioGTError):
        return exc

    msg = str(exc)
    if isinstance(exc, ValueError):
        return _classify_value_error(msg)

    lower_msg = msg.lower()
    if "checksum mismatch" in lower_msg:
        return PerioGTError("checksum_mismatch", msg)
    if "cuda" in lower_msg and "unavailable" in lower_msg:
        return PerioGTError("cuda_unavailable", msg)
    if "compute capability" in lower_msg:
        return PerioGTError("gpu_unsupported", msg)
    if "driver" in lower_msg and "560.28" in lower_msg:
        return PerioGTError("driver_incompatible", msg)
    if "checkpoint" in lower_msg and "missing" in lower_msg:
        return PerioGTError("checkpoint_missing", msg)
    if "model" in lower_msg and "load" in lower_msg:
        return PerioGTError("model_load_failed", msg)

    return PerioGTError("internal_error", msg or exc.__class__.__name__)

