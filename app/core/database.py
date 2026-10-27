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


_VERIFICATION_REQUESTS_DDL = """
CREATE TABLE {name} (
    request_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'awaiting_admin_release', 'confirmed_legitimate', 'denied_suspicious')
    ),
    created_at_utc TEXT NOT NULL,
    responded_at_utc TEXT,
    user_response TEXT CHECK (user_response IN ('approved', 'denied') OR user_response IS NULL),
    response_notes TEXT,
    requires_admin_release INTEGER NOT NULL DEFAULT 0 CHECK (requires_admin_release IN (0, 1)),
    admin_decision TEXT CHECK (admin_decision IN ('approved', 'blocked') OR admin_decision IS NULL),
    admin_id TEXT,
    admin_notes TEXT,
    admin_decided_at_utc TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

_VERIFICATION_REQUESTS_COLUMNS = (
    "request_id, transaction_id, user_id, status, created_at_utc, responded_at_utc, user_response, "
    "response_notes, requires_admin_release, admin_decision, admin_id, admin_notes, admin_decided_at_utc"
)


def _migrate_verification_status_constraint(conn: sqlite3.Connection) -> None:
    """Rebuild `verification_requests` if it was created with the legacy status CHECK constraint.

    Databases created before the Admin-release workflow only allow
    ('pending', 'confirmed_legitimate', 'denied_suspicious'), so confirming a high-risk
    transfer (status 'awaiting_admin_release') fails with an IntegrityError. SQLite cannot
    alter CHECK constraints in place, so the table is rebuilt and all rows are preserved.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'verification_requests';"
    ).fetchone()
    if row is None or "awaiting_admin_release" in (row["sql"] or ""):
        return

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN;")
        conn.execute("DROP TABLE IF EXISTS verification_requests_migrated;")
        conn.execute(_VERIFICATION_REQUESTS_DDL.format(name="verification_requests_migrated"))
        conn.execute(
            f"INSERT INTO verification_requests_migrated ({_VERIFICATION_REQUESTS_COLUMNS}) "
            f"SELECT {_VERIFICATION_REQUESTS_COLUMNS} FROM verification_requests;"
        )
        conn.execute("DROP TABLE verification_requests;")
        conn.execute("ALTER TABLE verification_requests_migrated RENAME TO verification_requests;")
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")


def init_db(db_path: Optional[Path] = None) -> None:
    """Create all TRACE-Fin database tables and apply idempotent column migrations."""
    with get_connection(db_path) as conn:
        _apply_column_migrations(conn)
        conn.executescript(SCHEMA_SQL)
        _apply_column_migrations(conn)
        conn.commit()
        _migrate_verification_status_constraint(conn)
        conn.commit()
