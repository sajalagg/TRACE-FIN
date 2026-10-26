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
    db_file = tmp_path / "test_incidents_stage8.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app), db_file


def _create_denied_incident(client: TestClient, tx_id: str) -> str:
    ver = client.post("/verification-requests", json={"transaction_id": tx_id}).json()
    resp = client.post(
        f"/verification-requests/{ver['request_id']}/respond",
        json={
            "user_response": "denied",
            "response_notes": "Unauthorized transfer detected during audit.",
        },
    )
    assert resp.status_code == 200
    inc_id = resp.json()["linked_incident_id"]
    assert inc_id is not None
    return str(inc_id)


def test_incident_creation_listing_and_detail_retrieval(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify incident listing, filters, full detail payload, and SHA-256 integrity check."""
    client, db_file = seeded_env

    # Create an incident for ATO transaction TX-0391 and BEC transaction
    with get_connection(db_file) as conn:
        bec_tx_id = str(
            conn.execute(
                "SELECT transaction_id FROM transactions WHERE scenario_label = 'b2b_vendor_bec_tamper' LIMIT 1;"
            ).fetchone()["transaction_id"]
        )

    inc1_id = _create_denied_incident(client, "TX-0391")
    inc2_id = _create_denied_incident(client, bec_tx_id)

    list_res = client.get("/incidents")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 2

    # Filter by status=open
    open_res = client.get("/incidents?status=open")
    assert open_res.status_code == 200
    assert len(open_res.json()) == 2

    # Inspect full detail of BEC corporate incident
    detail_res = client.get(f"/incidents/{inc2_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert detail["incident"]["incident_id"] == inc2_id
    assert detail["incident"]["transaction_id"] == bec_tx_id
    assert detail["user_profile"]["account_category"] == "business"
    assert detail["verification_request"]["user_response"] == "denied"

    # Verify SHA-256 integrity check passes
    integrity = detail["evidence_integrity"]
    assert integrity["integrity_verified"] is True
    assert integrity["stored_sha256"] == integrity["recomputed_sha256"]

    # Verify BEC-specific advisory playbook is included in recommended_actions
    recs_joined = " ".join(detail["recommended_actions"])
    assert "B2B BEC Playbook" in recs_joined
    assert "Corporate" in recs_joined

    # Verify linked evidence preserves source_table:source_record_id provenance
    linked = detail["linked_evidence"]
    assert len(linked) >= 3
    assert any(
        e["source_record_id"].startswith("beneficiary_events:BEN-EVT-") for e in linked
    )


def test_incident_status_lifecycle_and_tamper_detection(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify status updates (open -> investigating -> closed) and SHA-256 tamper detection."""
    client, db_file = seeded_env
    inc_id = _create_denied_incident(client, "TX-0391")

    # 1. Transition open -> investigating
    patch_inv = client.patch(
        f"/incidents/{inc_id}",
        json={
            "status": "investigating",
            "investigator_note": "Contacted student account holder; reviewing NL-Amsterdam login.",
        },
    )
    assert patch_inv.status_code == 200
    inv_data = patch_inv.json()
    assert inv_data["incident"]["status"] == "investigating"
    assert "Contacted student account holder" in inv_data["incident"]["summary_reason"]
    evidence_count_before = len(inv_data["linked_evidence"])
    assert evidence_count_before >= 7

    # 2. Transition investigating -> closed
    patch_closed = client.patch(
        f"/incidents/{inc_id}",
        json={
            "status": "closed",
            "investigator_note": "Confirmed unauthorized ATO in classroom simulation.",
        },
    )
    assert patch_closed.status_code == 200
    closed_data = patch_closed.json()
    assert closed_data["incident"]["status"] == "closed"
    # Closing an incident must preserve all linked evidence records!
    assert len(closed_data["linked_evidence"]) == evidence_count_before
    assert closed_data["evidence_integrity"]["integrity_verified"] is True

    # 3. Simulate tampering with the stored JSON snapshot in SQLite and verify detection
    with get_connection(db_file) as conn:
        conn.execute(
            """
            UPDATE incidents
            SET evidence_snapshot_json = '{"tampered":true}'
            WHERE incident_id = ?;
            """,
            (inc_id,),
        )
        conn.commit()

    tampered_res = client.get(f"/incidents/{inc_id}").json()
    assert tampered_res["evidence_integrity"]["integrity_verified"] is False
    assert (
        tampered_res["evidence_integrity"]["stored_sha256"]
        != tampered_res["evidence_integrity"]["recomputed_sha256"]
    )


def test_incident_errors(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify 404 on unknown incident ID and 422 on invalid status."""
    client, _ = seeded_env

    res_404 = client.get("/incidents/INC-9999")
    assert res_404.status_code == 404

    patch_404 = client.patch("/incidents/INC-9999", json={"status": "closed"})
    assert patch_404.status_code == 404

    inc_id = _create_denied_incident(client, "TX-0391")
    bad_status = client.patch(f"/incidents/{inc_id}", json={"status": "deleted"})
    assert bad_status.status_code == 422
