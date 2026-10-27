from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.database import get_connection, init_db
from app.core.policy import (
    TX_STATUS_COMPLETED,
    TX_STATUS_HELD_HIGH_RISK,
    TX_STATUS_PENDING_VERIFICATION,
    evaluate_transfer_policy,
)
from app.core.security import hash_password, verify_password
from scripts.seed_demo_data import (
    DEMO_ADMIN_PASSWORD,
    DEMO_CUSTOMER_PASSWORD,
    seed_database,
    seed_initial_demo_incidents,
)


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


def test_stage2_policy_password_hashing_and_seeded_entities(tmp_path: Path) -> None:
    """Verify Stage 2 central transfer policy, password hashing, balances, beneficiaries, and admin account."""
    # 1. Password hashing & verification (PBKDF2-HMAC-SHA256)
    digest = hash_password("MySecretPass#2026")
    assert "MySecretPass#2026" not in digest
    assert digest.startswith("pbkdf2_sha256$")
    assert verify_password("MySecretPass#2026", digest) is True
    assert verify_password("WrongPassword", digest) is False

    # 2. Central transfer policy bands
    low_decision = evaluate_transfer_policy(risk_score=18, user_alert_threshold=55)
    assert low_decision.resulting_status == TX_STATUS_COMPLETED
    assert low_decision.deduct_balance_immediately is True
    assert low_decision.requires_user_verification is False
    assert low_decision.requires_admin_release is False

    med_decision = evaluate_transfer_policy(risk_score=58, user_alert_threshold=55, high_risk_hold_threshold=75)
    assert med_decision.resulting_status == TX_STATUS_PENDING_VERIFICATION
    assert med_decision.deduct_balance_immediately is False
    assert med_decision.requires_user_verification is True
    assert med_decision.requires_admin_release is False

    high_decision = evaluate_transfer_policy(risk_score=84, user_alert_threshold=55, high_risk_hold_threshold=75)
    assert high_decision.resulting_status == TX_STATUS_HELD_HIGH_RISK
    assert high_decision.deduct_balance_immediately is False
    assert high_decision.requires_user_verification is True
    assert high_decision.requires_admin_release is True

    # 3. Seeded customer balances, admin account, beneficiaries, and transaction statuses
    db_file = tmp_path / "test_stage2.db"
    summary = seed_database(db_path=db_file, total_transactions=500, seed=42)
    seed_initial_demo_incidents(db_path=db_file)
    assert summary["beneficiaries"] == 36

    with get_connection(db_file) as conn:
        admin_row = conn.execute(
            "SELECT user_id, username, password_hash, role FROM users WHERE user_id = 'ADMIN-001';"
        ).fetchone()
        assert admin_row is not None
        assert admin_row["username"] == "admin"
        assert admin_row["role"] == "admin"
        assert verify_password(DEMO_ADMIN_PASSWORD, admin_row["password_hash"]) is True

        cust_row = conn.execute(
            "SELECT user_id, username, password_hash, role, simulated_balance FROM users WHERE user_id = 'USR-001';"
        ).fetchone()
        assert cust_row is not None
        assert cust_row["username"] == "aarav.sharma"
        assert cust_row["role"] == "customer"
        assert float(cust_row["simulated_balance"]) == 3250.00
        assert verify_password(DEMO_CUSTOMER_PASSWORD, cust_row["password_hash"]) is True

        blocked_cnt = conn.execute(
            "SELECT COUNT(*) AS cnt FROM transactions WHERE status = 'BLOCKED' AND balance_deducted = 0;"
        ).fetchone()["cnt"]
        pending_cnt = conn.execute(
            "SELECT COUNT(*) AS cnt FROM transactions WHERE status = 'PENDING_VERIFICATION' AND balance_deducted = 0;"
        ).fetchone()["cnt"]
        assert blocked_cnt == 3
        assert pending_cnt == 1

