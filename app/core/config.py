from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "trace_fin.db"


def get_db_path() -> Path:
    """Return the configured SQLite database file path.

    Tests can override `TRACE_FIN_DB_PATH` via environment variable to use an
    isolated temporary database without touching `data/trace_fin.db`.
    """
    override = os.environ.get("TRACE_FIN_DB_PATH")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH
