from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from app.core.config import get_db_path
from app.models.database_models import SCHEMA_SQL


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a SQLite connection with row factory and foreign keys enabled."""
    target_path = db_path or get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add `column` to `table` if the table exists and does not yet have `column`."""
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table});").fetchall()}
    if cols and column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")


def _apply_column_migrations(conn: sqlite3.Connection) -> None:
    """Ensure existing databases created before Stage 2 have all new columns."""
    _ensure_column(conn, "users", "username", "TEXT")
    _ensure_column(conn, "users", "password_hash", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "users", "role", "TEXT NOT NULL DEFAULT 'customer'")
    _ensure_column(conn, "users", "simulated_balance", "REAL NOT NULL DEFAULT 10000.0")
    _ensure_column(conn, "users", "home_ip_prefix", "TEXT NOT NULL DEFAULT '103.21.244.'")

    _ensure_column(conn, "user_sessions", "geo_location", "TEXT NOT NULL DEFAULT 'IN-Mumbai'")
    _ensure_column(conn, "user_sessions", "device_label", "TEXT NOT NULL DEFAULT 'Primary Web Session'")
    _ensure_column(conn, "user_sessions", "network_type", "TEXT NOT NULL DEFAULT 'home_broadband'")
    _ensure_column(conn, "user_sessions", "is_known_ip", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "user_sessions", "is_known_device", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "user_sessions", "is_home_location", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "user_sessions", "failed_logins_1h", "INTEGER NOT NULL DEFAULT 0")

    _ensure_column(conn, "transactions", "status", "TEXT NOT NULL DEFAULT 'COMPLETED'")
    _ensure_column(
        conn,
        "transactions",
        "decision_reason",
        "TEXT NOT NULL DEFAULT 'Approved under baseline simulation policy.'",
    )
    _ensure_column(conn, "transactions", "notes", "TEXT")
    _ensure_column(conn, "transactions", "idempotency_key", "TEXT")
    _ensure_column(conn, "transactions", "balance_deducted", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "transactions", "session_id", "TEXT")

    _ensure_column(conn, "verification_requests", "requires_admin_release", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "verification_requests", "admin_decision", "TEXT")
    _ensure_column(conn, "verification_requests", "admin_id", "TEXT")
    _ensure_column(conn, "verification_requests", "admin_notes", "TEXT")
    _ensure_column(conn, "verification_requests", "admin_decided_at_utc", "TEXT")


def init_db(db_path: Optional[Path] = None) -> None:
    """Create all TRACE-Fin database tables and apply idempotent column migrations."""
    with get_connection(db_path) as conn:
        _apply_column_migrations(conn)
        conn.executescript(SCHEMA_SQL)
        _apply_column_migrations(conn)
        conn.commit()
