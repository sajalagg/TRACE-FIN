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
    db_file = tmp_path / "test_alert_policy_stage6.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app), db_file


def test_get_and_update_user_preferences(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify reading and updating user alert preferences and validation errors."""
    client, _ = seeded_env

    # Read initial preferences for USR-001
    res = client.get("/preferences/USR-001")
    assert res.status_code == 200
    prefs = res.json()
    assert prefs["user_id"] == "USR-001"
    assert prefs["risk_threshold"] == 55
    assert prefs["timezone_iana"] == "Asia/Kolkata"
    assert prefs["quiet_hours_start"] == "22:00"
    assert prefs["quiet_hours_end"] == "07:00"

    # Update preferences
    update_res = client.put(
        "/preferences/USR-001",
        json={
            "risk_threshold": 70,
            "critical_bypass_threshold": 90,
            "timezone_iana": "Europe/London",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "06:30",
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["risk_threshold"] == 70
    assert updated["critical_bypass_threshold"] == 90
    assert updated["timezone_iana"] == "Europe/London"
    assert updated["quiet_hours_start"] == "23:00"

    # Invalid IANA timezone returns 422
    bad_tz = client.put(
        "/preferences/USR-001",
        json={
            "risk_threshold": 60,
            "critical_bypass_threshold": 85,
            "timezone_iana": "Invalid/Timezone_Name",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
    )
    assert bad_tz.status_code == 422

    # critical_bypass_threshold < risk_threshold returns 422
    bad_crit = client.put(
        "/preferences/USR-001",
        json={
            "risk_threshold": 80,
            "critical_bypass_threshold": 65,
            "timezone_iana": "UTC",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
    )
    assert bad_crit.status_code == 422

    # Unknown user returns 404
    missing = client.get("/preferences/USR-999")
    assert missing.status_code == 404


def test_timezone_conversion_overnight_quiet_hours_and_critical_bypass(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify UTC -> local timezone conversion, overnight quiet hours, and critical bypass."""
    client, _ = seeded_env

    # TX-0391 occurred at 2026-03-19T19:30:00Z on USR-001 (Asia/Kolkata = UTC+5:30 -> 01:00 IST next day!)
    # Contextual score is 100 (>= critical_bypass_threshold 85)
    res_ist = client.get("/transactions/TX-0391/alert-decision?method=contextual")
    assert res_ist.status_code == 200
    d_ist = res_ist.json()

    assert d_ist["risk_score"] == 100
    assert d_ist["within_quiet_hours"] is True
    assert "2026-03-20 01:00:00" in d_ist["transaction_local_time"]
    assert d_ist["alert_decision"] == "ALERT_NOW_CRITICAL_BYPASS"

    # What-If: Same transaction at 19:30:00Z viewed in America/New_York (15:30 EDT -> outside 22:00-07:00 quiet hours)
    res_ny = client.get(
        "/transactions/TX-0391/alert-decision?method=contextual&override_timezone=America/New_York"
    )
    assert res_ny.status_code == 200
    d_ny = res_ny.json()
    assert d_ny["is_what_if_simulation"] is True
    assert d_ny["within_quiet_hours"] is False
    assert "2026-03-19 15:30:00" in d_ny["transaction_local_time"]
    assert d_ny["alert_decision"] == "ALERT_NOW"
    # Underlying score is unchanged!
    assert d_ny["risk_score"] == d_ist["risk_score"] == 100


def test_queued_for_quiet_hours_and_threshold_score_invariance(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify non-critical alerts during quiet hours are queued, and threshold changes never alter risk_score."""
    client, db_file = seeded_env

    # Find an active threat-intel transaction where contextual score is 50 (medium)
    with get_connection(db_file) as conn:
        row = conn.execute(
            """
            SELECT transaction_id FROM transactions
            WHERE scenario_label = 'threat_intel_active_or_stale_ip' AND is_suspicious = 1
            ORDER BY transaction_id ASC LIMIT 1;
            """
        ).fetchone()
    tx_id = str(row["transaction_id"])

    # 1. With threshold=60 and method=contextual (score=50), decision is NO_ALERT_BELOW_THRESHOLD
    res_below = client.get(
        f"/transactions/{tx_id}/alert-decision?method=contextual&override_threshold=60"
    ).json()
    assert res_below["risk_score"] == 50
    assert res_below["alert_decision"] == "NO_ALERT_BELOW_THRESHOLD"

    # 2. Lower threshold to 40 and force a 00:00-23:59 quiet window with critical_bypass=85:
    # Score stays 50, but decision flips to QUEUED_FOR_QUIET_HOURS!
    res_queued = client.get(
        f"/transactions/{tx_id}/alert-decision?method=contextual"
        "&override_threshold=40&override_critical_bypass=85"
        "&override_quiet_hours_enabled=true&override_quiet_hours_start=00:00&override_quiet_hours_end=23:59"
    ).json()
    assert res_queued["risk_score"] == 50
    assert res_queued["within_quiet_hours"] is True
    assert res_queued["alert_decision"] == "QUEUED_FOR_QUIET_HOURS"

    # 3. Disable quiet hours with threshold=40: Score still stays 50, decision flips to ALERT_NOW!
    res_now = client.get(
        f"/transactions/{tx_id}/alert-decision?method=contextual"
        "&override_threshold=40&override_quiet_hours_enabled=false"
    ).json()
    assert res_now["risk_score"] == 50
    assert res_now["alert_decision"] == "ALERT_NOW"
