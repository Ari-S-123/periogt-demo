"""Download, verify, and manage PerioGT checkpoints on a Modal Volume."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

VOLUME_ROOT = "/vol/checkpoints"
READY_SENTINEL = os.path.join(VOLUME_ROOT, ".ready")
DOWNLOADING_MARKER = os.path.join(VOLUME_ROOT, ".downloading")

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


def _compute_md5(filepath: str) -> str:
    """Compute MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _download_and_verify(name: str, info: dict[str, str]) -> str:
    """Download a zip file and verify its MD5 checksum. Returns the local path."""
    zip_path = os.path.join(VOLUME_ROOT, name)
    logger.info("Downloading %s from %s", name, info["url"])

    urlretrieve(info["url"], zip_path)

    actual_md5 = _compute_md5(zip_path)
    if actual_md5 != info["md5"]:
        os.remove(zip_path)
        raise RuntimeError(
            f"Checksum mismatch for {name}: expected {info['md5']}, got {actual_md5}. "
            "File deleted. Re-deploy to retry."
        )
    logger.info("Checksum verified for %s: %s", name, actual_md5)
    return zip_path


def _extract_zip(zip_path: str, dest_dir: str) -> None:
    """Extract a zip file to destination directory."""
    logger.info("Extracting %s to %s", zip_path, dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    # Remove zip after extraction to save space
    os.remove(zip_path)
    logger.info("Extracted and removed %s", zip_path)


def _build_property_index() -> dict:
    """Scan the finetuned checkpoint directory and build an index mapping property -> checkpoint path."""
    index: dict[str, dict] = {}
    finetuned_root = os.path.join(VOLUME_ROOT, "finetuned_ckpt")

    if not os.path.isdir(finetuned_root):
        # Try nested extraction structure
        for candidate in Path(VOLUME_ROOT).rglob("*.pth"):
            parts = candidate.parts
            # Look for pattern like .../property_name/best_model.pth
            if candidate.name.startswith("best_model"):
                prop_id = parts[-2]  # directory name = property id
                meta = PROPERTY_METADATA.get(prop_id, (prop_id, ""))
                index[prop_id] = {
                    "checkpoint": str(candidate),
                    "label": meta[0],
                    "units": meta[1],
                }
        if not index:
            logger.warning("No finetuned checkpoints found under %s", VOLUME_ROOT)
        return index

    for entry in os.listdir(finetuned_root):
        entry_path = os.path.join(finetuned_root, entry)
        if os.path.isdir(entry_path):
            # Each subdirectory is a property (e.g., eps/, tg/, density/)
            for f in os.listdir(entry_path):
                if f.endswith(".pth"):
                    prop_id = entry
                    meta = PROPERTY_METADATA.get(prop_id, (prop_id, ""))
                    index[prop_id] = {
                        "checkpoint": os.path.join(entry_path, f),
                        "label": meta[0],
                        "units": meta[1],
                    }
                    break
        elif entry.endswith(".pth"):
            prop_id = entry.replace(".pth", "").replace("best_model_", "")
            meta = PROPERTY_METADATA.get(prop_id, (prop_id, ""))
            index[prop_id] = {
                "checkpoint": entry_path,
                "label": meta[0],
                "units": meta[1],
            }

    return index


def ensure_checkpoints(volume) -> dict:
    """
    Ensure all checkpoints are downloaded, verified, and extracted on the Volume.
    Returns the property index mapping.

    Must be called with a Modal Volume reference for commit/reload.
    """
    # Reload to see latest state from other containers
    volume.reload()

    # Check if already bootstrapped
    if os.path.exists(READY_SENTINEL):
        index_path = os.path.join(VOLUME_ROOT, "index.json")
        if os.path.exists(index_path):
            with open(index_path) as f:
                return json.load(f)
        # Sentinel exists but index is missing — rebuild index
        index = _build_property_index()
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)
        volume.commit()
        return index

    # Check if another container is already downloading
    if os.path.exists(DOWNLOADING_MARKER):
        raise RuntimeError(
            "Another container is currently downloading checkpoints. "
            "This container will retry on next request."
        )

    # Start download
    os.makedirs(VOLUME_ROOT, exist_ok=True)

    # Write downloading marker
    with open(DOWNLOADING_MARKER, "w") as f:
        f.write("downloading")
    volume.commit()

    try:
        for name, info in ARTIFACTS.items():
            zip_path = _download_and_verify(name, info)
            _extract_zip(zip_path, VOLUME_ROOT)

        # Build and save property index
        index = _build_property_index()
        index_path = os.path.join(VOLUME_ROOT, "index.json")
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

        # Write ready sentinel
        with open(READY_SENTINEL, "w") as f:
            f.write("ready")

        # Clean up downloading marker
        if os.path.exists(DOWNLOADING_MARKER):
            os.remove(DOWNLOADING_MARKER)

        # Commit all writes to Volume
        volume.commit()
        logger.info("Checkpoint bootstrap complete. Properties: %s", list(index.keys()))
        return index

    except Exception:
        # Clean up on failure
        if os.path.exists(DOWNLOADING_MARKER):
            os.remove(DOWNLOADING_MARKER)
        volume.commit()
        raise
