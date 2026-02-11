"""CSV parsing/writing helpers for HPC batch inference."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .errors import PerioGTError


@dataclass
class BatchInputRow:
    row_index: int
    smiles: str
    id_value: str


OUTPUT_COLUMNS = [
    "id",
    "smiles",
    "property",
    "prediction_value",
    "prediction_units",
    "ok",
    "error_code",
    "error_message",
    "request_id",
]


def read_batch_input_csv(path: str | Path) -> list[BatchInputRow]:
    csv_path = Path(path).resolve()
    if not csv_path.exists():
        raise PerioGTError(
            "validation_error",
            "Input CSV does not exist.",
            details={"input": str(csv_path)},
        )

    rows: list[BatchInputRow] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise PerioGTError("validation_error", "Input CSV has no header row.")
        if "smiles" not in reader.fieldnames:
            raise PerioGTError(
                "validation_error",
                "Input CSV must include a 'smiles' column.",
                details={"columns": reader.fieldnames},
            )

        for i, raw in enumerate(reader, start=1):
            smiles = (raw.get("smiles") or "").strip()
            if not smiles:
                rows.append(BatchInputRow(row_index=i, smiles="", id_value=str(i)))
                continue

            id_value = (raw.get("id") or "").strip() or str(i)
            rows.append(BatchInputRow(row_index=i, smiles=smiles, id_value=id_value))
    return rows


def default_output_path(input_path: str | Path) -> Path:
    resolved = Path(input_path).resolve()
    return resolved.with_name(f"{resolved.stem}_predictions.csv")


def write_batch_output_csv(path: str | Path, rows: list[dict]) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in OUTPUT_COLUMNS})
    return out

