"""PerioGT HPC command-line interface."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import click

from .config import resolve_config, run_doctor, ensure_runtime_package_path
from .errors import PerioGTError, map_exception
from .io_csv import default_output_path, read_batch_input_csv, write_batch_output_csv
from .log import configure_logging
from .runtime import load_runtime_state


def _emit_error_and_exit(exc: Exception) -> None:
    err = map_exception(exc)
    click.echo(json.dumps({"error": err.to_dict()}, indent=2), err=True)
    raise SystemExit(err.exit_code)


@click.group()
def cli() -> None:
    """PerioGT HPC CLI."""
    configure_logging()


@cli.command("predict")
@click.option("--smiles", required=True, type=str, help="Polymer repeat-unit SMILES.")
@click.option("--property", "property_id", required=True, type=str, help="Property ID.")
@click.option("--return-embedding", is_flag=True, default=False, help="Include embedding in response.")
@click.option("--format", "output_format", type=click.Choice(["json", "csv"]), default="json")
def predict(smiles: str, property_id: str, return_embedding: bool, output_format: str) -> None:
    """Predict one property for one SMILES."""
    try:
        cfg = resolve_config(require_checkpoint_dir=True, require_source_dir=True)
        state = load_runtime_state(cfg)
        ensure_runtime_package_path(cfg.runtime_package_dir)

        from periogt_runtime.inference import predict_property

        request_id = str(uuid.uuid4())
        result = predict_property(
            smiles=smiles,
            property_id=property_id,
            models=state.models,
            scaler=state.scaler,
            label_mean=state.label_mean,
            label_std=state.label_std,
            return_embedding=return_embedding,
            request_id=request_id,
        )
        payload = result.model_dump()
        if output_format == "json":
            click.echo(json.dumps(payload, indent=2))
            return

        line = ",".join(
            [
                payload["smiles"],
                payload["property"],
                str(payload["prediction"]["value"]),
                payload["prediction"]["units"],
                payload["request_id"],
            ]
        )
        click.echo(line)
    except Exception as exc:  # noqa: BLE001
        _emit_error_and_exit(exc)


@cli.command("embeddings")
@click.option("--smiles", required=True, type=str, help="Polymer repeat-unit SMILES.")
def embeddings(smiles: str) -> None:
    """Compute graph embedding for one SMILES."""
    try:
        cfg = resolve_config(require_checkpoint_dir=True, require_source_dir=True)
        state = load_runtime_state(cfg)
        ensure_runtime_package_path(cfg.runtime_package_dir)

        from periogt_runtime.inference import compute_embedding

        result = compute_embedding(
            smiles=smiles,
            models=state.models,
            scaler=state.scaler,
            request_id=str(uuid.uuid4()),
        )
        click.echo(json.dumps(result.model_dump(), indent=2))
    except Exception as exc:  # noqa: BLE001
        _emit_error_and_exit(exc)


@cli.command("batch")
@click.option("--input", "input_csv", required=True, type=click.Path(path_type=Path), help="Input CSV path.")
@click.option("--property", "property_id", required=True, type=str, help="Property ID.")
@click.option(
    "--output",
    "output_csv",
    required=False,
    type=click.Path(path_type=Path),
    help="Output CSV path (default: <input>_predictions.csv).",
)
def batch(input_csv: Path, property_id: str, output_csv: Path | None) -> None:
    """Run batch prediction from CSV input."""
    try:
        cfg = resolve_config(require_checkpoint_dir=True, require_source_dir=True)
        state = load_runtime_state(cfg)
        ensure_runtime_package_path(cfg.runtime_package_dir)
        from periogt_runtime.inference import predict_property

        input_rows = read_batch_input_csv(input_csv)
        out_rows: list[dict] = []
        failures = 0

        for row in input_rows:
            request_id = str(uuid.uuid4())
            try:
                if not row.smiles.strip():
                    raise PerioGTError(
                        "validation_error",
                        "SMILES is empty.",
                        details={"row_index": row.row_index},
                    )
                result = predict_property(
                    smiles=row.smiles,
                    property_id=property_id,
                    models=state.models,
                    scaler=state.scaler,
                    label_mean=state.label_mean,
                    label_std=state.label_std,
                    return_embedding=False,
                    request_id=request_id,
                )
                out_rows.append(
                    {
                        "id": row.id_value,
                        "smiles": row.smiles,
                        "property": property_id,
                        "prediction_value": result.prediction.value,
                        "prediction_units": result.prediction.units,
                        "ok": "true",
                        "error_code": "",
                        "error_message": "",
                        "request_id": request_id,
                    }
                )
            except Exception as row_exc:  # noqa: BLE001
                failures += 1
                err = map_exception(row_exc)
                out_rows.append(
                    {
                        "id": row.id_value,
                        "smiles": row.smiles,
                        "property": property_id,
                        "prediction_value": "",
                        "prediction_units": "",
                        "ok": "false",
                        "error_code": err.code,
                        "error_message": err.message,
                        "request_id": request_id,
                    }
                )

        out_path = output_csv.resolve() if output_csv else default_output_path(input_csv)
        written = write_batch_output_csv(out_path, out_rows)
        click.echo(f"Wrote batch results: {written}")

        if failures:
            click.echo(f"Completed with {failures} row-level failures.", err=True)
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _emit_error_and_exit(exc)


@cli.command("doctor")
def doctor() -> None:
    """Print runtime diagnostics and compatibility verdict."""
    try:
        cfg = resolve_config(require_checkpoint_dir=False, require_source_dir=False)
        report = run_doctor(cfg)
        payload = {
            "verdict": report.verdict,
            "info": report.info,
            "warnings": report.warnings,
            "fatals": report.fatals,
        }
        click.echo(json.dumps(payload, indent=2))
        raise SystemExit(report.exit_code)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _emit_error_and_exit(exc)


@cli.command("setup")
@click.option("--skip-download", is_flag=True, default=False, help="Skip downloads and only build index.json.")
def setup(skip_download: bool) -> None:
    """Download/extract artifacts and generate checkpoint index."""
    try:
        cfg = resolve_config(require_checkpoint_dir=False, require_source_dir=False)
        cfg.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        ensure_runtime_package_path(cfg.runtime_package_dir)
        from periogt_runtime.checkpoint_manager import ensure_checkpoints

        index = ensure_checkpoints(
            volume=None,
            checkpoint_dir=cfg.checkpoint_dir,
            skip_download=skip_download,
        )
        click.echo(
            json.dumps(
                {
                    "checkpoint_dir": str(cfg.checkpoint_dir),
                    "properties": sorted(index.keys()),
                    "count": len(index),
                    "skip_download": skip_download,
                },
                indent=2,
            )
        )
    except Exception as exc:  # noqa: BLE001
        _emit_error_and_exit(exc)

