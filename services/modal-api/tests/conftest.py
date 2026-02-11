from __future__ import annotations

import sys
from pathlib import Path


MODAL_API_DIR = Path(__file__).resolve().parents[1]
if str(MODAL_API_DIR) not in sys.path:
    sys.path.insert(0, str(MODAL_API_DIR))

