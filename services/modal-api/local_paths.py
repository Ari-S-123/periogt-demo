"""Resolve local source directories for Modal image mounts.

These helpers keep path resolution stable regardless of the current
working directory used when running Modal CLI commands.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _validate_directory_name(name: str) -> None:
    """Validate that a directory name is a simple relative path segment.

    Args:
        name: Directory name to validate.

    Raises:
        ValueError: If the name is empty, absolute, or contains separators.
    """
    if not name or not name.strip():
        raise ValueError("Directory name must be a non-empty string.")

    path = Path(name)
    if path.is_absolute() or path.name != name:
        raise ValueError(
            "Directory name must be a simple relative name without separators."
        )


def resolve_local_dir(name: str) -> Path:
    """Resolve a local directory name to an absolute path next to this file.

    Args:
        name: Directory name located in the same folder as this module.

    Returns:
        Absolute path to the requested directory.

    Raises:
        ValueError: If the name fails validation.
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path exists but is not a directory.
    """
    _validate_directory_name(name)
    path = (BASE_DIR / name).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Local directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Expected a directory at: {path}")
    return path


PERIOGT_SRC_DIR = resolve_local_dir("periogt_src")
PERIOGT_RUNTIME_DIR = resolve_local_dir("periogt_runtime")
