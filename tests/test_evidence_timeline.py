from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_connection
from app.main import app
from scripts.seed_demo_data import seed_database


@pytest.fixture()
def seeded_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    """Provide a TestClient and temporary database seeded with deterministic synthetic data."""
    db_file = tmp_path / "test_timeline_stage5.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app), db_file


def test_timeline_chronological_ordering_and_kill_chain_on_ato(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify unified timeline is strictly ordered, links source records, and tags Kill-Chain phases."""
    client, _ = seeded_env
    res = client.get("/transactions/TX-0391/timeline")
    assert res.status_code == 200
    data = res.json()

    assert data["transaction_id"] == "TX-0391"
    assert data["user_id"] == "USR-001"
    assert data["missing_categories"] == []
    assert set(data["present_categories"]) >= {
        "authentication",
        "device",
        "beneficiary",
        "transaction",
    }

    timeline = data["timeline"]
    assert len(timeline) >= 7

    # 1. Verify strict chronological ordering and sequence numbers
    timestamps = [entry["timestamp_utc"] for entry in timeline]
    assert timestamps == sorted(timestamps)
    assert [entry["sequence_no"] for entry in timeline] == list(range(1, len(timeline) + 1))

    # 2. Final entry must be the target transaction itself
    last_entry = timeline[-1]
    assert last_entry["source_table"] == "transactions"
    assert last_entry["source_record_id"] == "TX-0391"
    assert last_entry["kill_chain_phase"] == "EXFILTRATION_EXECUTION"

    # 3. Verify all 4 attack kill-chain phases are observed on this ATO chain
    phases = set(data["kill_chain_phases_observed"])
    assert "RECON_BRUTE_FORCE" in phases
    assert "INITIAL_ACCESS" in phases
    assert "PREPARATION_PERSISTENCE" in phases
    assert "EXFILTRATION_EXECUTION" in phases

    # 4. Verify recorded_fact vs system_interpretation separation on every entry
    for entry in timeline:
        assert entry["source_table"] in {
            "authentication_events",
            "device_events",
            "beneficiary_events",
            "threat_intelligence",
            "transactions",
        }
        assert entry["source_record_id"] != ""
        assert len(entry["recorded_fact"]) > 10
        assert len(entry["system_interpretation"]) > 10
        assert entry["recorded_fact"] != entry["system_interpretation"]


def test_timeline_bec_vendor_modification_provenance(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify BEC scenario timeline includes the beneficiary_bank_updated preparation event."""
    client, db_file = seeded_env
    with get_connection(db_file) as conn:
        bec_tx_id = conn.execute(
            "SELECT transaction_id FROM transactions WHERE scenario_label = 'b2b_vendor_bec_tamper' LIMIT 1;"
        ).fetchone()["transaction_id"]

    res = client.get(f"/transactions/{bec_tx_id}/timeline")
    assert res.status_code == 200
    timeline = res.json()["timeline"]

    bec_entries = [
        e for e in timeline if e["event_type"] == "beneficiary_bank_updated"
    ]
    assert len(bec_entries) >= 1
    assert bec_entries[-1]["source_table"] == "beneficiary_events"
    assert bec_entries[-1]["kill_chain_phase"] == "PREPARATION_PERSISTENCE"


def test_timeline_missing_categories_and_minimal_history(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify timeline handles missing event categories explicitly without failing."""
    client, db_file = seeded_env
    with get_connection(db_file) as conn:
        tx_row = conn.execute(
            "SELECT transaction_id, user_id FROM transactions WHERE scenario_label = 'normal_routine' LIMIT 1;"
        ).fetchone()
        tx_id = tx_row["transaction_id"]
        uid = tx_row["user_id"]

        # Delete all supporting events for this user
        conn.execute("DELETE FROM authentication_events WHERE user_id = ?;", (uid,))
        conn.execute("DELETE FROM device_events WHERE user_id = ?;", (uid,))
        conn.execute("DELETE FROM beneficiary_events WHERE user_id = ?;", (uid,))
        conn.execute(
            "DELETE FROM transactions WHERE user_id = ? AND transaction_id != ?;",
            (uid, tx_id),
        )
        conn.commit()

    res = client.get(f"/transactions/{tx_id}/timeline")
    assert res.status_code == 200
    data = res.json()

    assert data["total_events"] == 1
    assert data["present_categories"] == ["transaction"]
    assert set(data["missing_categories"]) == {"authentication", "device", "beneficiary"}
    assert data["timeline"][0]["source_record_id"] == tx_id


def test_timeline_not_found(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify 404 when requesting timeline for a non-existent transaction."""
    client, _ = seeded_env
    res = client.get("/transactions/TX-999999/timeline")
    assert res.status_code == 404
