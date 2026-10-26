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
    db_file = tmp_path / "test_verification_stage7.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app), db_file


def test_create_verification_request_and_duplicate_prevention(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify creating a verification request and preventing duplicate requests for the same transaction."""
    client, _ = seeded_env

    # First creation
    res1 = client.post("/verification-requests", json={"transaction_id": "TX-0391"})
    assert res1.status_code == 200
    v1 = res1.json()
    assert v1["request_id"] == "VER-0001"
    assert v1["transaction_id"] == "TX-0391"
    assert v1["status"] == "pending"
    assert v1["created_new"] is True
    assert v1["linked_incident_id"] is None

    # Second creation for the exact same transaction returns the existing record
    res2 = client.post("/verification-requests", json={"transaction_id": "TX-0391"})
    assert res2.status_code == 200
    v2 = res2.json()
    assert v2["request_id"] == "VER-0001"
    assert v2["created_new"] is False

    # List pending requests
    list_res = client.get("/verification-requests?status=pending")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_verification_approval_preserves_risk_evidence(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify user approval records confirmed_legitimate without deleting underlying risk evidence."""
    client, _ = seeded_env

    score_before = client.get("/transactions/TX-0391/risk?method=contextual").json()

    create_res = client.post("/verification-requests", json={"transaction_id": "TX-0391"}).json()
    req_id = create_res["request_id"]

    resp_res = client.post(
        f"/verification-requests/{req_id}/respond",
        json={
            "user_response": "approved",
            "response_notes": "I authorized this transfer while traveling.",
        },
    )
    assert resp_res.status_code == 200
    body = resp_res.json()
    assert body["status"] == "confirmed_legitimate"
    assert body["user_response"] == "approved"
    assert body["responded_at_utc"] is not None
    assert body["linked_incident_id"] is None

    # Underlying forensic evidence and risk score must remain completely intact
    score_after = client.get("/transactions/TX-0391/risk?method=contextual").json()
    assert score_after["risk_score"] == score_before["risk_score"]
    assert len(score_after["triggered_rules"]) == len(score_before["triggered_rules"])


def test_verification_denial_creates_incident_and_handles_repeats(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify user denial creates an evidence-linked incident with SHA-256 hash and prevents duplicates."""
    client, db_file = seeded_env

    create_res = client.post("/verification-requests", json={"transaction_id": "TX-0391"}).json()
    req_id = create_res["request_id"]

    deny_res = client.post(
        f"/verification-requests/{req_id}/respond",
        json={
            "user_response": "denied",
            "response_notes": "I did not add this beneficiary or make this transfer.",
        },
    )
    assert deny_res.status_code == 200
    denied = deny_res.json()
    assert denied["status"] == "denied_suspicious"
    assert denied["user_response"] == "denied"
    assert denied["linked_incident_id"] == "INC-0001"

    # Repeating the exact same 'denied' response is idempotent and does NOT create a second incident
    repeat_res = client.post(
        f"/verification-requests/{req_id}/respond",
        json={"user_response": "denied", "response_notes": "Repeated click"},
    )
    assert repeat_res.status_code == 200
    assert repeat_res.json()["linked_incident_id"] == "INC-0001"

    with get_connection(db_file) as conn:
        inc_count = conn.execute("SELECT COUNT(*) AS cnt FROM incidents;").fetchone()["cnt"]
        assert inc_count == 1

        inc_row = conn.execute("SELECT * FROM incidents WHERE incident_id = 'INC-0001';").fetchone()
        assert inc_row["status"] == "open"
        assert inc_row["severity"] == "critical"
        assert len(inc_row["evidence_sha256"]) == 64

        ev_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM incident_evidence WHERE incident_id = 'INC-0001';"
        ).fetchone()["cnt"]
        assert ev_count >= 7

    # Submitting a conflicting 'approved' response after 'denied' returns 409 Conflict
    conflict_res = client.post(
        f"/verification-requests/{req_id}/respond",
        json={"user_response": "approved"},
    )
    assert conflict_res.status_code == 409


def test_verification_not_found_errors(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify 404 responses on missing transaction or verification request IDs."""
    client, _ = seeded_env

    bad_tx = client.post("/verification-requests", json={"transaction_id": "TX-999999"})
    assert bad_tx.status_code == 404

    bad_req = client.post(
        "/verification-requests/VER-9999/respond",
        json={"user_response": "approved"},
    )
    assert bad_req.status_code == 404
