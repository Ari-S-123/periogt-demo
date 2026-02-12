"""Download, verify, and manage PerioGT checkpoints."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from .runtime_config import get_checkpoint_dir

logger = logging.getLogger(__name__)

ARTIFACTS: dict[str, dict[str, str]] = {
    "pretrained_ckpt.zip": {
        "url": "https://zenodo.org/records/17035498/files/pretrained_ckpt.zip?download=1",
        "md5": "7adbcfc4da134692e9a2965270321662",
    },
    "finetuned_ckpt.zip": {
        "url": "https://zenodo.org/records/17035498/files/finetuned_ckpt.zip?download=1",
        "md5": "f285c724142aa2c8919f6a736f6e6093",
    },
}

# Property metadata: id -> (label, units)
# The actual list of properties is discovered by scanning the finetuned checkpoint dir
PROPERTY_METADATA: dict[str, tuple[str, str]] = {
    "eat": ("Atomization energy", "eV"),
    "eps": ("Dielectric constant (ε)", ""),
    "density": ("Density", "g/cm³"),
    "tg": ("Glass transition temperature (Tg)", "K"),
    "nc": ("Refractive index (nc)", ""),
    "eea": ("Electron affinity", "eV"),
    "eip": ("Ionization potential", "eV"),
    "xi": ("Chi parameter", ""),
    "cp": ("Heat capacity (Cp)", "J/(mol·K)"),
    "e_amorph": ("Young's modulus (amorphous)", "GPa"),
    "egc": ("Band gap (chain)", "eV"),
    "egb": ("Band gap (bulk)", "eV"),
}


def _resolve_root(checkpoint_dir: str | Path | None = None) -> Path:
    if checkpoint_dir is None:
        return get_checkpoint_dir()
    return Path(checkpoint_dir).resolve()


def _paths(checkpoint_dir: str | Path | None = None) -> dict[str, Path]:
    root = _resolve_root(checkpoint_dir)
    return {
        "root": root,
        "ready": root / ".ready",
        "downloading": root / ".downloading",
        "index": root / "index.json",
        "label_stats": root / "label_stats.json",
        "scaler": root / "descriptor_scaler.pkl",
        "pretrained_dir": root / "pretrained_ckpt",
        "finetuned_dir": root / "finetuned_ckpt",
    }


def _compute_md5(filepath: str | Path) -> str:
    """Compute MD5 hash of a file."""
    md5 = hashlib.md5()
    with Path(filepath).open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _parse_positive_float_env(name: str, default: float, minimum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %.2f", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%r is too small; using minimum %.2f", name, raw, minimum)
        return minimum
    return value


def _download_and_verify(name: str, info: dict[str, str], root: Path) -> Path:
    """Download a zip file and verify its MD5 checksum. Returns the local path."""
    zip_path = root / name
    if zip_path.exists():
        existing_md5 = _compute_md5(zip_path)
        if existing_md5 == info["md5"]:
            logger.info("Using cached artifact %s (md5=%s)", zip_path, existing_md5)
            return zip_path
        logger.warning(
            "Cached artifact %s has checksum mismatch (%s != %s), re-downloading.",
            zip_path,
            existing_md5,
            info["md5"],
        )
        zip_path.unlink(missing_ok=True)

    logger.info("Downloading %s from %s", name, info["url"])

    urlretrieve(info["url"], str(zip_path))

    actual_md5 = _compute_md5(zip_path)
    if actual_md5 != info["md5"]:
        zip_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {name}: expected {info['md5']}, got {actual_md5}. "
            "File deleted. Re-run setup to retry."
        )
    logger.info("Checksum verified for %s: %s", name, actual_md5)
    return zip_path


def _extract_zip(zip_path: str | Path, dest_dir: str | Path) -> None:
    """Extract a zip file to destination directory."""
    zip_path = Path(zip_path)
    dest = Path(dest_dir)
    logger.info("Extracting %s to %s", zip_path, dest)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    # Remove zip after extraction to save space
    zip_path.unlink(missing_ok=True)
    logger.info("Extracted and removed %s", zip_path)


def _build_property_index(checkpoint_dir: str | Path | None = None) -> dict:
    """Scan the finetuned checkpoint directory and build an index mapping property -> checkpoint path."""
    index: dict[str, dict] = {}
    p = _paths(checkpoint_dir)
    root = p["root"]
    finetuned_root = p["finetuned_dir"]

    if not finetuned_root.is_dir():
        # Try nested extraction structure
        for candidate in root.rglob("*.pth"):
            # Look for pattern like .../property_name/best_model.pth
            if candidate.name.startswith("best_model") and len(candidate.parts) >= 2:
                prop_id = candidate.parent.name
                meta = PROPERTY_METADATA.get(prop_id, (prop_id, ""))
                index[prop_id] = {
                    "checkpoint": str(candidate),
                    "label": meta[0],
                    "units": meta[1],
                }
        if not index:
            logger.warning("No finetuned checkpoints found under %s", root)
        return index

    for entry in os.listdir(finetuned_root):
        entry_path = finetuned_root / entry
        if entry_path.is_dir():
            # Each subdirectory is a property (e.g., eps/, tg/, density/)
            for f in os.listdir(entry_path):
                if f.endswith(".pth"):
                    prop_id = entry
                    meta = PROPERTY_METADATA.get(prop_id, (prop_id, ""))
                    index[prop_id] = {
                        "checkpoint": str(entry_path / f),
                        "label": meta[0],
                        "units": meta[1],
                    }
                    break
        elif entry.endswith(".pth"):
            prop_id = entry.replace(".pth", "").replace("best_model_", "")
            meta = PROPERTY_METADATA.get(prop_id, (prop_id, ""))
            index[prop_id] = {
                "checkpoint": str(entry_path),
                "label": meta[0],
                "units": meta[1],
            }

    return index


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        dir=str(path.parent),
        prefix=f"{path.name}.",
        suffix=".tmp",
        encoding="utf-8",
    ) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def required_artifacts(checkpoint_dir: str | Path | None = None) -> dict[str, Path]:
    """Return required artifact paths for runtime inference."""
    p = _paths(checkpoint_dir)
    return {
        "pretrained_ckpt": p["pretrained_dir"],
        "finetuned_ckpt": p["finetuned_dir"],
        "label_stats_json": p["label_stats"],
        "descriptor_scaler_pkl": p["scaler"],
        "index_json": p["index"],
    }


def missing_required_artifacts(checkpoint_dir: str | Path | None = None) -> dict[str, Path]:
    """Return missing artifact paths keyed by artifact name."""
    missing: dict[str, Path] = {}
    for key, path in required_artifacts(checkpoint_dir).items():
        if not path.exists():
            missing[key] = path
    return missing


def ensure_checkpoints(volume=None, checkpoint_dir: str | Path | None = None, skip_download: bool = False) -> dict:
    """
    Ensure checkpoints are downloaded, verified, indexed, and ready.

    Returns the property index mapping.

    Args:
        volume: Optional Modal Volume object for reload/commit behavior.
        checkpoint_dir: Optional explicit checkpoint root path.
        skip_download: If True, skip archive download and only (re)build index.
    """
    p = _paths(checkpoint_dir)
    root = p["root"]
    ready_sentinel = p["ready"]
    downloading_marker = p["downloading"]
    index_path = p["index"]

    # Reload to see latest state from other containers
    if volume is not None:
        volume.reload()

    # Check if already bootstrapped
    if ready_sentinel.exists():
        if index_path.exists():
            with index_path.open() as f:
                return json.load(f)
        # Sentinel exists but index is missing — rebuild index
        index = _build_property_index(root)
        _write_json_atomic(index_path, index)
        if volume is not None:
            volume.commit()
        return index

    # Check if another container is already downloading
    if downloading_marker.exists():
        stale_after_s = _parse_positive_float_env(
            "PERIOGT_CHECKPOINT_DOWNLOAD_STALE_SECONDS",
            330.0,
            minimum=1.0,
        )
        try:
            marker_age_s = max(0.0, time.time() - downloading_marker.stat().st_mtime)
        except FileNotFoundError:
            marker_age_s = 0.0

        if marker_age_s >= stale_after_s:
            logger.warning(
                "Detected stale checkpoint download marker at %s (age %.1fs >= %.1fs); "
                "taking over bootstrap in this container.",
                downloading_marker,
                marker_age_s,
                stale_after_s,
            )
            downloading_marker.unlink(missing_ok=True)
            if volume is not None:
                volume.commit()
                volume.reload()
        else:
            raise RuntimeError(
                "Another container is currently downloading checkpoints. "
                "This process will retry later."
            )

    # Start download
    root.mkdir(parents=True, exist_ok=True)

    # Write downloading marker
    with downloading_marker.open("w", encoding="utf-8") as f:
        f.write("downloading")
    if volume is not None:
        volume.commit()

    try:
        if not skip_download:
            for name, info in ARTIFACTS.items():
                zip_path = _download_and_verify(name, info, root)
                _extract_zip(zip_path, root)
        else:
            logger.info("Skipping downloads; building index from pre-staged artifacts.")

        # Build and save property index
        index = _build_property_index(root)
        _write_json_atomic(index_path, index)

        # Write ready sentinel
        with ready_sentinel.open("w", encoding="utf-8") as f:
            f.write("ready")

        # Clean up downloading marker
        downloading_marker.unlink(missing_ok=True)

        # Commit all writes to Volume (if used)
        if volume is not None:
            volume.commit()
        logger.info("Checkpoint bootstrap complete. Properties: %s", list(index.keys()))
        return index

    except Exception:
        # Clean up on failure
        downloading_marker.unlink(missing_ok=True)
        if volume is not None:
            volume.commit()
        raise
