from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from scripts.seed_demo_data import (
    DEMO_ADMIN_PASSWORD,
    DEMO_CUSTOMER_PASSWORD,
    seed_database,
)


def _build_seeded_client(tmp_path: Path, monkeypatch) -> TestClient:
    db_file = tmp_path / "test_transfers_admin.db"
    seed_database(db_path=db_file)
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    return TestClient(app)


def test_insufficient_simulated_balance_rejected(tmp_path: Path, monkeypatch) -> None:
    """Submitting a transfer exceeding the customer's simulated_balance must return 422."""
    client = _build_seeded_client(tmp_path, monkeypatch)

    user_before = client.get("/users/USR-001").json()
    bal_before = float(user_before["simulated_balance"])

    resp = client.post(
        "/transactions",
        json={
            "user_id": "USR-001",
            "amount": bal_before + 5000.0,
            "beneficiary_id": "BEN-IND-UTIL",
            "beneficiary_name": "City Power & Broadband Utility",
            "beneficiary_category": "utility_tax",
            "beneficiary_industry": "general_consumer",
            "ip_address": "103.21.244.12",
            "geo_location": "IN-Bengaluru",
        },
    )
    assert resp.status_code == 422
    assert "Insufficient simulated balance" in resp.json()["detail"]

    user_after = client.get("/users/USR-001").json()
    assert float(user_after["simulated_balance"]) == bal_before


def test_legitimate_travel_unfamiliar_ip_alone_completes_and_deducts_balance(
    tmp_path: Path, monkeypatch
) -> None:
    """An unfamiliar IP/location (VPN/travel) alone on a normal transfer must NOT block it."""
    client = _build_seeded_client(tmp_path, monkeypatch)

    # Sign in from Singapore VPN using known device (omitting device_id uses user's primary registered device) and 0 failed logins
    login_resp = client.post(
        "/auth/login",
        json={
            "username": "aarav.sharma",
            "password": "DemoUser@123",
            "ip_address": "165.225.112.40",
            "geo_location": "SG-Singapore",
            "network_type": "commercial_vpn",
            "simulate_failed_attempts": 0,
        },
    )
    assert login_resp.status_code == 200
    auth_data = login_resp.json()
    token = auth_data["session_token"]
    session_id = auth_data["session"]["session_id"]
    known_dev_id = auth_data["session"]["device_id"]
    bal_before = float(auth_data["user"]["simulated_balance"])

    # Establish a verified beneficiary well before the transfer so counterparty is trusted
    client.post(
        "/beneficiaries",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": "USR-001",
            "beneficiary_id": "BEN-TRAVEL-HOTEL",
            "beneficiary_name": "Marina Bay Hospitality SG",
            "beneficiary_category": "utility_tax",
            "beneficiary_industry": "general_consumer",
            "event_type": "beneficiary_verified",
            "timestamp_utc": "2026-02-01T10:00:00Z",
        },
    )

    tx_resp = client.post(
        "/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": "USR-001",
            "amount": 45.0,
            "beneficiary_id": "BEN-TRAVEL-HOTEL",
            "beneficiary_name": "Marina Bay Hospitality SG",
            "beneficiary_category": "utility_tax",
            "beneficiary_industry": "general_consumer",
            "device_id": known_dev_id,
            "ip_address": "165.225.112.40",
            "geo_location": "SG-Singapore",
            "timestamp_utc": "2026-03-20T09:00:00Z",
        },
    )
    assert tx_resp.status_code == 200
    body = tx_resp.json()
    tx = body["transaction"]
    m3_score = body["risk_comparison"]["contextual_ti"]["risk_score"]

    assert m3_score < 40
    assert tx["status"] == "COMPLETED"
    assert tx["balance_deducted"] is True
    assert tx["session_id"] == session_id

    user_after = client.get("/users/USR-001").json()
    assert round(float(user_after["simulated_balance"]), 2) == round(bal_before - 45.0, 2)


def test_medium_risk_transfer_pending_then_completed_on_customer_approval(
    tmp_path: Path, monkeypatch
) -> None:
    """Medium-risk transfer (40-74) is placed in PENDING_VERIFICATION without deducting balance until customer approves."""
    client = _build_seeded_client(tmp_path, monkeypatch)

    user_before = client.get("/users/USR-002").json()
    bal_before = float(user_before["simulated_balance"])

    # Trigger a Medium-risk score (40-74): unseen device (20) + rapid new beneficiary (25) = 45 from home location
    tx_resp = client.post(
        "/transactions",
        json={
            "user_id": "USR-002",
            "amount": 90.0,
            "beneficiary_id": "BEN-MED-PEER",
            "beneficiary_name": "New Peer Transfer",
            "beneficiary_category": "personal_peer",
            "beneficiary_industry": "general_consumer",
            "ip_address": "103.21.244.25",
            "geo_location": "IN-Mumbai",
            "timestamp_utc": "2026-03-21T10:00:00Z",
            "simulate_unseen_device": True,
            "simulate_rapid_new_beneficiary": True,
        },
    )
    assert tx_resp.status_code == 200
    body = tx_resp.json()
    tx = body["transaction"]
    tx_id = tx["transaction_id"]
    m3_score = body["risk_comparison"]["contextual_ti"]["risk_score"]

    assert 40 <= m3_score <= 74
    assert tx["status"] == "PENDING_VERIFICATION"
    assert tx["balance_deducted"] is False

    # Balance must NOT be deducted while pending verification
    user_mid = client.get("/users/USR-002").json()
    assert round(float(user_mid["simulated_balance"]), 2) == round(bal_before, 2)

    # Verification request should exist and not require admin release
    ver_list = client.get("/verification-requests", params={"user_id": "USR-002"}).json()
    matching_ver = [v for v in ver_list if v["transaction_id"] == tx_id]
    assert len(matching_ver) == 1
    req_id = matching_ver[0]["request_id"]
    assert matching_ver[0]["requires_admin_release"] is False

    # Customer approves the verification request
    approve_resp = client.post(
        f"/verification-requests/{req_id}/respond",
        json={"user_response": "approved", "response_notes": "Confirmed by customer."},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "confirmed_legitimate"

    # Transaction is now COMPLETED and balance is deducted once
    tx_after = client.get(f"/transactions/{tx_id}").json()["transaction"]
    assert tx_after["status"] == "COMPLETED"
    assert tx_after["balance_deducted"] is True

    user_after = client.get("/users/USR-002").json()
    assert round(float(user_after["simulated_balance"]), 2) == round(bal_before - 90.0, 2)


def test_high_risk_transfer_held_and_completed_or_blocked_by_admin_in_lab(
    tmp_path: Path, monkeypatch
) -> None:
    """High-risk transfers (>=75) are HELD_HIGH_RISK and require Admin release in the Risk Analysis Lab."""
    client = _build_seeded_client(tmp_path, monkeypatch)

    # Log in as customer USR-002 and Admin ADMIN-001
    cust_login = client.post(
        "/auth/login",
        json={"username": "USR-002", "password": DEMO_CUSTOMER_PASSWORD},
    ).json()
    cust_token = cust_login["session_token"]

    admin_login = client.post(
        "/auth/login",
        json={"username": "admin", "password": DEMO_ADMIN_PASSWORD},
    ).json()
    admin_token = admin_login["session_token"]

    bal_start = float(client.get("/users/USR-002").json()["simulated_balance"])

    # 1. Create a High-Risk transfer (score >= 75)
    tx1_resp = client.post(
        "/transactions",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={
            "user_id": "USR-002",
            "amount": 1200.0,
            "beneficiary_id": "BEN-HIGH-01",
            "beneficiary_name": "Offshore Digital Exchange",
            "beneficiary_category": "financial_brokerage",
            "beneficiary_industry": "digital_assets_brokerage",
            "ip_address": "198.51.100.201",
            "geo_location": "NL-Amsterdam",
            "timestamp_utc": "2026-03-22T02:15:00Z",
            "simulate_failed_logins": 4,
            "simulate_unseen_device": True,
            "simulate_rapid_new_beneficiary": True,
        },
    )
    assert tx1_resp.status_code == 200
    tx1 = tx1_resp.json()["transaction"]
    tx1_id = tx1["transaction_id"]
    assert tx1_resp.json()["risk_comparison"]["contextual_ti"]["risk_score"] >= 75
    assert tx1["status"] == "HELD_HIGH_RISK"
    assert tx1["balance_deducted"] is False

    # Balance untouched while held
    assert round(float(client.get("/users/USR-002").json()["simulated_balance"]), 2) == round(bal_start, 2)

    # Customer confirms intent -> status becomes 'awaiting_admin_release', still HELD_HIGH_RISK
    ver_list = client.get("/verification-requests", params={"user_id": "USR-002"}).json()
    ver1 = [v for v in ver_list if v["transaction_id"] == tx1_id][0]
    assert ver1["requires_admin_release"] is True

    cust_approve = client.post(
        f"/verification-requests/{ver1['request_id']}/respond",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"user_response": "approved", "response_notes": "I authorized this wire."},
    )
    assert cust_approve.status_code == 200
    assert cust_approve.json()["status"] == "awaiting_admin_release"

    # Balance is STILL untouched until Admin releases it
    assert round(float(client.get("/users/USR-002").json()["simulated_balance"]), 2) == round(bal_start, 2)

    # Customer cannot call /admin-decision (403 Forbidden)
    forbid_resp = client.post(
        f"/transactions/{tx1_id}/admin-decision",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"admin_decision": "approve", "admin_notes": "Trying self-release"},
    )
    assert forbid_resp.status_code == 403

    # Admin investigates in Risk Analysis Lab and approves/releases tx1
    admin_rel = client.post(
        f"/transactions/{tx1_id}/admin-decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "admin_decision": "approve",
            "admin_notes": "Confirmed directly with Priya Nair; releasing high-risk hold.",
        },
    )
    assert admin_rel.status_code == 200
    rel_data = admin_rel.json()
    assert rel_data["transaction"]["status"] == "COMPLETED"
    assert rel_data["transaction"]["balance_deducted"] is True
    assert rel_data["verification_request"]["status"] == "confirmed_legitimate"
    assert rel_data["verification_request"]["admin_decision"] == "approved"
    assert round(float(rel_data["user_profile"]["simulated_balance"]), 2) == round(bal_start - 1200.0, 2)

    # 2. Create a second High-Risk transfer and have Admin BLOCK it
    bal_after_tx1 = float(rel_data["user_profile"]["simulated_balance"])
    tx2_resp = client.post(
        "/transactions",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={
            "user_id": "USR-002",
            "amount": 900.0,
            "beneficiary_id": "BEN-HIGH-02",
            "beneficiary_name": "Suspicious Mule Account",
            "beneficiary_category": "personal_peer",
            "beneficiary_industry": "digital_assets_brokerage",
            "ip_address": "198.51.100.201",
            "geo_location": "RO-Bucharest",
            "timestamp_utc": "2026-03-22T03:00:00Z",
            "simulate_failed_logins": 4,
            "simulate_unseen_device": True,
            "simulate_rapid_new_beneficiary": True,
        },
    )
    assert tx2_resp.status_code == 200
    tx2_id = tx2_resp.json()["transaction"]["transaction_id"]

    admin_blk = client.post(
        f"/transactions/{tx2_id}/admin-decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "admin_decision": "block",
            "admin_notes": "Customer confirmed compromise during callback; blocking transfer.",
        },
    )
    assert admin_blk.status_code == 200
    blk_data = admin_blk.json()
    assert blk_data["transaction"]["status"] == "BLOCKED"
    assert blk_data["transaction"]["balance_deducted"] is False
    assert blk_data["verification_request"]["status"] == "denied_suspicious"
    assert blk_data["verification_request"]["admin_decision"] == "blocked"
    assert blk_data["linked_incident_id"] is not None
    assert blk_data["linked_incident_id"].startswith("INC-")
    assert round(float(blk_data["user_profile"]["simulated_balance"]), 2) == round(bal_after_tx1, 2)


def test_customer_denial_immediately_blocks_without_going_to_admin(
    tmp_path: Path, monkeypatch
) -> None:
    """When a customer denies an alert (Medium or High risk), it blocks immediately and clears requires_admin_release."""
    client = _build_seeded_client(tmp_path, monkeypatch)

    cust_login = client.post(
        "/auth/login",
        json={"username": "USR-002", "password": DEMO_CUSTOMER_PASSWORD},
    ).json()
    cust_token = cust_login["session_token"]
    bal_before = float(client.get("/users/USR-002").json()["simulated_balance"])

    tx_resp = client.post(
        "/transactions",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={
            "user_id": "USR-002",
            "amount": 750.0,
            "beneficiary_id": "BEN-DENY-01",
            "beneficiary_name": "Unauthorized Recipient",
            "beneficiary_category": "personal_peer",
            "beneficiary_industry": "digital_assets_brokerage",
            "ip_address": "198.51.100.201",
            "geo_location": "NL-Amsterdam",
            "timestamp_utc": "2026-03-23T04:00:00Z",
            "simulate_failed_logins": 3,
            "simulate_unseen_device": True,
            "simulate_rapid_new_beneficiary": True,
        },
    )
    assert tx_resp.status_code == 200
    tx_id = tx_resp.json()["transaction"]["transaction_id"]

    ver_list = client.get("/verification-requests", params={"user_id": "USR-002"}).json()
    ver_item = [v for v in ver_list if v["transaction_id"] == tx_id][0]
    assert ver_item["requires_admin_release"] is True

    # Customer clicks "I did not make this transaction" ('denied')
    deny_resp = client.post(
        f"/verification-requests/{ver_item['request_id']}/respond",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"user_response": "denied", "response_notes": "I did not authorize this transfer."},
    )
    assert deny_resp.status_code == 200
    deny_data = deny_resp.json()
    assert deny_data["status"] == "denied_suspicious"
    assert deny_data["requires_admin_release"] is False

    # Transaction is immediately BLOCKED with 'Thank you for your response — the transaction is blocked'
    tx_detail = client.get(f"/transactions/{tx_id}").json()["transaction"]
    assert tx_detail["status"] == "BLOCKED"
    assert tx_detail["balance_deducted"] is False
    assert "Thank you for your response — the transaction is blocked" in tx_detail["decision_reason"]

    # Customer's balance is untouched
    bal_after = float(client.get("/users/USR-002").json()["simulated_balance"])
    assert round(bal_after, 2) == round(bal_before, 2)

