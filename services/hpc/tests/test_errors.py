from __future__ import annotations

from periogt_hpc.errors import PerioGTError, map_exception


def test_map_unsupported_property() -> None:
    err = map_exception(ValueError("Unsupported property 'foo'"))
    assert err.code == "unsupported_property"


def test_map_validation_error() -> None:
    err = map_exception(ValueError("SMILES must include polymer connection points using '*'"))
    assert err.code == "validation_error"


def test_map_passthrough() -> None:
    original = PerioGTError("checkpoint_missing", "Missing checkpoint")
    err = map_exception(original)
    assert err is original

