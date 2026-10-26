from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.database import get_connection, init_db
from scripts.seed_demo_data import seed_database


def test_schema_and_foreign_key_enforcement(tmp_path: Path) -> None:
    """Verify SQLite tables are created and foreign-key constraints are enforced."""
    db_file = tmp_path / "test_schema.db"
    init_db(db_file)

    with get_connection(db_file) as conn:
        fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_status == 1

        # Inserting a transaction for a non-existent user must fail with IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO transactions (
                    transaction_id, user_id, amount, currency, timestamp_utc,
                    beneficiary_id, beneficiary_name, beneficiary_category,
                    beneficiary_industry, device_id, ip_address, geo_location,
                    is_suspicious, scenario_label
                ) VALUES (
                    'TX-BAD', 'USR-DOES-NOT-EXIST', 100.0, 'USD', '2026-03-10T10:00:00Z',
                    'BEN-1', 'Test Ben', 'personal_peer', 'general_consumer',
                    'DEV-1', '10.0.0.1', 'IN-Mumbai', 0, 'normal_routine'
                )
                """
            )


def test_deterministic_seeding_and_idempotency(tmp_path: Path) -> None:
    """Verify seeding generates 500 transactions across all 8 archetypes and is idempotent."""
    db_file = tmp_path / "test_seed.db"

    summary_first = seed_database(db_path=db_file, total_transactions=500, seed=42)
    assert summary_first["users"] == 12
    assert summary_first["user_preferences"] == 12
    assert summary_first["transactions"] == 500
    assert summary_first["threat_intelligence"] == 5

    with get_connection(db_file) as conn:
        first_run_txs = [
            (r["transaction_id"], r["amount"], r["scenario_label"], r["is_suspicious"])
            for r in conn.execute("SELECT * FROM transactions ORDER BY transaction_id;").fetchall()
        ]

    # Re-run seeding on the same database: counts and exact values must match (no duplicates)
    summary_second = seed_database(db_path=db_file, total_transactions=500, seed=42)
    assert summary_second == summary_first

    with get_connection(db_file) as conn:
        second_run_txs = [
            (r["transaction_id"], r["amount"], r["scenario_label"], r["is_suspicious"])
            for r in conn.execute("SELECT * FROM transactions ORDER BY transaction_id;").fetchall()
        ]
    assert second_run_txs == first_run_txs


def test_user_profiles_and_scenario_archetypes_present(tmp_path: Path) -> None:
    """Verify OpEx/CapEx/Personal profiles and all 8 forensic scenario archetypes exist."""
    db_file = tmp_path / "test_archetypes.db"
    seed_database(db_path=db_file, total_transactions=500, seed=42)

    with get_connection(db_file) as conn:
        models = {
            r["expenditure_model"]
            for r in conn.execute("SELECT DISTINCT expenditure_model FROM users;").fetchall()
        }
        assert models == {"opex_heavy", "capex_heavy", "personal_consumption"}

        scenarios = {
            r["scenario_label"]
            for r in conn.execute("SELECT DISTINCT scenario_label FROM transactions;").fetchall()
        }
        expected_scenarios = {
            "normal_routine",
            "legitimate_capex_high_value",
            "legitimate_opex_payroll_cycle",
            "legitimate_travel_new_ip",
            "low_and_slow_ato",
            "b2b_vendor_bec_tamper",
            "structured_smurfing_drain",
            "threat_intel_active_or_stale_ip",
        }
        assert scenarios == expected_scenarios

        # Verify BEC scenario links to a preceding `beneficiary_bank_updated` event
        bec_tx = conn.execute(
            """
            SELECT user_id, beneficiary_id, timestamp_utc
            FROM transactions
            WHERE scenario_label = 'b2b_vendor_bec_tamper'
            LIMIT 1;
            """
        ).fetchone()
        assert bec_tx is not None

        bec_event = conn.execute(
            """
            SELECT event_type
            FROM beneficiary_events
            WHERE user_id = ?
              AND beneficiary_id = ?
              AND event_type = 'beneficiary_bank_updated'
              AND timestamp_utc <= ?;
            """,
            (bec_tx["user_id"], bec_tx["beneficiary_id"], bec_tx["timestamp_utc"]),
        ).fetchone()
        assert bec_event is not None
