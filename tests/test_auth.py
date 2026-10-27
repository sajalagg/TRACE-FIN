from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.seed_demo_data import (
    DEMO_ADMIN_PASSWORD,
    DEMO_CUSTOMER_PASSWORD,
    seed_database,
    seed_initial_demo_incidents,
)


@pytest.fixture()
def seeded_auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    """Provide a TestClient and temporary database seeded with deterministic demo data."""
    db_file = tmp_path / "test_auth_stage3.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=120, seed=42)
    seed_initial_demo_incidents(db_path=db_file)
    return TestClient(app), db_file


def test_register_new_customer_with_home_ip_and_location(
    seeded_auth_env: tuple[TestClient, Path],
) -> None:
    """Verify registration captures home IP/location baseline, hashes password, and logs in."""
    client, _ = seeded_auth_env

    reg_resp = client.post(
        "/auth/register",
        json={
            "username": "priya.nair",
            "password": "StrongPassword#2026",
            "display_name": "Priya Nair (Product Designer)",
            "account_category": "individual",
            "profile_type": "salaried_individual",
            "industry_sector": "personal_finance",
            "expenditure_model": "personal_consumption",
            "home_geo_location": "IN-Kochi",
            "home_ip_address": "117.204.88.14",
            "primary_device_label": "Priya MacBook Air",
            "simulated_balance": 19500.0,
            "timezone_iana": "Asia/Kolkata",
        },
    )
    assert reg_resp.status_code == 201
    data = reg_resp.json()

    assert data["session_token"]
    assert data["user"]["user_id"] == "USR-013"
    assert data["user"]["username"] == "priya.nair"
    assert data["user"]["role"] == "customer"
    assert data["user"]["simulated_balance"] == 19500.0
    assert data["user"]["home_geo_location"] == "IN-Kochi"
    assert data["user"]["home_ip_prefix"] == "117.204.88."

    session = data["session"]
    assert session["ip_address"] == "117.204.88.14"
    assert session["geo_location"] == "IN-Kochi"
    assert session["is_known_ip"] is True
    assert session["is_known_device"] is True
    assert session["is_home_location"] is True
    assert session["observed_evidence"]["is_active"] is True
    assert session["simulated_input"]["network_type"] == "home_broadband"
    assert session["inferred_context"]["home_ip_prefix"] == "117.204.88."

    # Duplicate username must be rejected
    dup_resp = client.post(
        "/auth/register",
        json={
            "username": "priya.nair",
            "password": "AnotherPassword#1",
            "display_name": "Duplicate User",
        },
    )
    assert dup_resp.status_code == 400


def test_login_session_network_intelligence_and_failed_attempts(
    seeded_auth_env: tuple[TestClient, Path],
) -> None:
    """Verify failed login attempts are recorded and session provenance separates Observed/Simulated/Inferred."""
    client, _ = seeded_auth_env

    # 1. Check network presets tailored for USR-001 (Aarav Sharma, IN-Mumbai, 103.21.244.)
    presets_resp = client.get("/auth/network-presets", params={"username": "aarav.sharma"})
    assert presets_resp.status_code == 200
    presets = presets_resp.json()
    assert len(presets) == 4
    assert presets[0]["geo_location"] == "IN-Mumbai"
    assert presets[0]["ip_address"].startswith("103.21.244.")

    # 2. Submit a wrong password from a foreign IP/unseen device -> 401 and records login_failure
    bad_resp = client.post(
        "/auth/login",
        json={
            "username": "aarav.sharma",
            "password": "WrongPassword123",
            "ip_address": "198.51.100.201",
            "geo_location": "RO-Bucharest",
            "device_id": "DEV-UNSEEN-PROXY-01",
            "network_type": "anonymizer_proxy",
        },
    )
    assert bad_resp.status_code == 401

    # 3. Now sign in with valid password from that suspicious network context
    ok_resp = client.post(
        "/auth/login",
        json={
            "username": "aarav.sharma",
            "password": DEMO_CUSTOMER_PASSWORD,
            "ip_address": "198.51.100.201",
            "geo_location": "RO-Bucharest",
            "device_id": "DEV-UNSEEN-PROXY-01",
            "device_label": "Unrecognized Proxy Browser",
            "network_type": "anonymizer_proxy",
        },
    )
    assert ok_resp.status_code == 200
    login_data = ok_resp.json()
    ses = login_data["session"]

    assert ses["is_known_ip"] is False
    assert ses["is_known_device"] is False
    assert ses["is_home_location"] is False
    assert ses["failed_logins_1h"] >= 1
    assert ses["inferred_context"]["active_threat_intel_match"] is True
    assert ses["inferred_context"]["threat_intel_category"] == "anonymizer_proxy_node"


def test_ownership_enforcement_prevents_idor_and_admin_access(
    seeded_auth_env: tuple[TestClient, Path],
) -> None:
    """Verify Customer A cannot access Customer B's resources, while Admin can inspect all."""
    client, _ = seeded_auth_env

    # Sign in as USR-001 (aarav.sharma)
    u1_login = client.post(
        "/auth/login",
        json={"username": "aarav.sharma", "password": DEMO_CUSTOMER_PASSWORD},
    )
    assert u1_login.status_code == 200
    u1_token = u1_login.json()["session_token"]
    u1_headers = {"Authorization": f"Bearer {u1_token}"}

    # USR-001 can read their own profile and preferences
    own_prof = client.get("/users/USR-001", headers=u1_headers)
    assert own_prof.status_code == 200
    own_prefs = client.get("/preferences/USR-001", headers=u1_headers)
    assert own_prefs.status_code == 200

    # USR-001 CANNOT read or mutate USR-002's profile, preferences, beneficiaries, or sessions (403 Forbidden)
    assert client.get("/users/USR-002", headers=u1_headers).status_code == 403
    assert client.get("/preferences/USR-002", headers=u1_headers).status_code == 403
    assert (
        client.put(
            "/preferences/USR-002",
            headers=u1_headers,
            json={
                "risk_threshold": 80,
                "critical_bypass_threshold": 90,
                "timezone_iana": "Asia/Singapore",
                "quiet_hours_enabled": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00",
            },
        ).status_code
        == 403
    )
    assert client.get("/users/USR-002/beneficiaries", headers=u1_headers).status_code == 403
    assert client.get("/auth/sessions", params={"user_id": "USR-002"}, headers=u1_headers).status_code == 403

    # USR-001 CANNOT modify forensic incident statuses (Admin-only)
    incidents = client.get("/incidents").json()
    assert len(incidents) >= 1
    inc_id = incidents[0]["incident_id"]
    patch_inc = client.patch(
        f"/incidents/{inc_id}",
        headers=u1_headers,
        json={"status": "closed", "investigator_note": "Customer trying to close incident"},
    )
    assert patch_inc.status_code == 403

    # Sign in as Admin (ADMIN-001)
    admin_login = client.post(
        "/auth/login",
        json={"username": "admin", "password": DEMO_ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["session_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    assert admin_login.json()["user"]["role"] == "admin"

    # Admin CAN inspect USR-002's profile, sessions, and update incidents
    assert client.get("/users/USR-002", headers=admin_headers).status_code == 200
    assert client.get("/auth/sessions", params={"user_id": "USR-001"}, headers=admin_headers).status_code == 200
    admin_patch = client.patch(
        f"/incidents/{inc_id}",
        headers=admin_headers,
        json={"status": "investigating", "investigator_note": "SOC Admin reviewing session telemetry."},
    )
    assert admin_patch.status_code == 200

    # Logout USR-001 -> subsequent /auth/me fails with 401
    logout_resp = client.post("/auth/logout", headers=u1_headers)
    assert logout_resp.status_code == 200
    assert client.get("/auth/me", headers=u1_headers).status_code == 401
