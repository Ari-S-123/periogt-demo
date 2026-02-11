"""Unit tests for local_paths.py helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from local_paths import _validate_directory_name, resolve_local_dir


class LocalPathsTests(unittest.TestCase):
    def test_validate_directory_name_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            _validate_directory_name("")

    def test_validate_directory_name_rejects_absolute(self) -> None:
        with self.assertRaises(ValueError):
            _validate_directory_name("/tmp/foo")

    def test_resolve_local_dir_rejects_nested(self) -> None:
        with self.assertRaises(ValueError):
            resolve_local_dir("a/b")


if __name__ == "__main__":
    unittest.main()
