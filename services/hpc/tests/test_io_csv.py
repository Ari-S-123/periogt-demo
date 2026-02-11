from __future__ import annotations

from pathlib import Path

import pytest

from periogt_hpc.errors import PerioGTError
from periogt_hpc.io_csv import read_batch_input_csv, write_batch_output_csv


def test_read_batch_input_csv(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    input_csv.write_text("id,smiles\nabc,*CC*\n,*CC(*)C\n", encoding="utf-8")

    rows = read_batch_input_csv(input_csv)
    assert len(rows) == 2
    assert rows[0].id_value == "abc"
    assert rows[1].id_value == "2"
    assert rows[1].smiles == "*CC(*)C"


def test_read_batch_input_requires_smiles_column(tmp_path: Path) -> None:
    input_csv = tmp_path / "bad.csv"
    input_csv.write_text("id,value\n1,foo\n", encoding="utf-8")
    with pytest.raises(PerioGTError) as exc:
        read_batch_input_csv(input_csv)
    assert exc.value.code == "validation_error"


def test_write_batch_output_csv(tmp_path: Path) -> None:
    output_csv = tmp_path / "out.csv"
    write_batch_output_csv(
        output_csv,
        [
            {
                "id": "1",
                "smiles": "*CC*",
                "property": "tg",
                "prediction_value": 1.23,
                "prediction_units": "K",
                "ok": "true",
                "error_code": "",
                "error_message": "",
                "request_id": "req",
            }
        ],
    )
    text = output_csv.read_text(encoding="utf-8")
    assert "prediction_value" in text
    assert "*CC*" in text

