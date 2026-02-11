from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HPC_DIR = REPO_ROOT / "services" / "hpc"
MODAL_API_DIR = REPO_ROOT / "services" / "modal-api"

for p in (str(HPC_DIR), str(MODAL_API_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

