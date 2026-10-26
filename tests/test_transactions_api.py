from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.seed_demo_data import seed_database


@pytest.fixture()
def seeded_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Provide a TestClient backed by a freshly seeded temporary SQLite database."""
    db_file = tmp_path / "test_api_stage3.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app)


def test_list_and_get_user_profiles(seeded_client: TestClient) -> None:
    """Verify GET /users and GET /users/{user_id} return full financial/business profiles."""
    res = seeded_client.get("/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 12

    # Filter by capex_heavy expenditure model
    capex_res = seeded_client.get("/users?expenditure_model=capex_heavy")
    assert capex_res.status_code == 200
    capex_users = capex_res.json()
    assert len(capex_users) == 3
    assert all(u["expenditure_model"] == "capex_heavy" for u in capex_users)

    # Fetch single user profile
    u10_res = seeded_client.get("/users/USR-010")
    assert u10_res.status_code == 200
    u10 = u10_res.json()
    assert u10["user_id"] == "USR-010"
    assert u10["profile_type"] == "enterprise_capex_firm"
    assert u10["industry_sector"] == "manufacturing_heavy_machinery"
    assert u10["estimated_net_worth"] == 6800000.0
    assert u10["typical_max_tx_amount"] == 110000.0

    # Non-existent user returns 404
    missing_res = seeded_client.get("/users/USR-999")
    assert missing_res.status_code == 404
    assert "not found" in missing_res.json()["detail"].lower()


def test_list_transactions_pagination_and_filters(seeded_client: TestClient) -> None:
    """Verify GET /transactions supports limit/offset pagination and profile filters."""
    res = seeded_client.get("/transactions?limit=15&offset=0")
    assert res.status_code == 200
    payload = res.json()

    assert payload["total_matching"] == 500
    assert payload["limit"] == 15
    assert payload["offset"] == 0
    assert len(payload["items"]) == 15

    # Verify anti-leakage: ground-truth labels must NOT appear in operational API responses
    first_item = payload["items"][0]
    assert "is_suspicious" not in first_item
    assert "scenario_label" not in first_item
    assert "user_expenditure_model" in first_item

    # Filter by user_id
    user_res = seeded_client.get("/transactions?user_id=USR-001&limit=100")
    assert user_res.status_code == 200
    user_payload = user_res.json()
    assert user_payload["total_matching"] > 0
    assert all(tx["user_id"] == "USR-001" for tx in user_payload["items"])


def test_get_transaction_detail_and_context(seeded_client: TestClient) -> None:
    """Verify GET /transactions/{id} returns transaction, user profile, and surrounding events."""
    # TX-0391 is a known low-and-slow ATO transaction for USR-001 in seed=42
    res = seeded_client.get("/transactions/TX-0391")
    assert res.status_code == 200
    detail = res.json()

    assert detail["transaction"]["transaction_id"] == "TX-0391"
    assert detail["transaction"]["user_id"] == "USR-001"
    assert detail["user_profile"]["profile_type"] == "student"
    assert detail["user_profile"]["typical_max_tx_amount"] == 250.0

    # Verify linked context lists exist and contain the preceding failed logins and new beneficiary
    auth_events = detail["recent_authentication_events"]
    assert len(auth_events) >= 4
    assert any(a["event_type"] == "login_failure" for a in auth_events)

    device_events = detail["device_events"]
    assert any(d["known_status"] == "new" for d in device_events)

    ben_events = detail["beneficiary_events"]
    assert any(b["beneficiary_id"] == detail["transaction"]["beneficiary_id"] for b in ben_events)


def test_get_transaction_detail_not_found_and_validation(seeded_client: TestClient) -> None:
    """Verify 404 on missing transaction ID and 422 on invalid query parameters."""
    not_found = seeded_client.get("/transactions/TX-999999")
    assert not_found.status_code == 404
    assert not_found.json() == {"detail": "Transaction 'TX-999999' not found."}

    bad_limit = seeded_client.get("/transactions?limit=0")
    assert bad_limit.status_code == 422
