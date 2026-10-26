from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_connection
from app.main import app
from scripts.seed_demo_data import seed_database


@pytest.fixture()
def seeded_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    """Provide a TestClient and database path seeded with deterministic synthetic data."""
    db_file = tmp_path / "test_scoring_stage4.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app), db_file


def _find_tx_id_by_scenario(
    db_file: Path,
    scenario: str,
    is_suspicious: int | None = None,
    offset: int = 0,
) -> str:
    with get_connection(db_file) as conn:
        if is_suspicious is None:
            row = conn.execute(
                """
                SELECT transaction_id FROM transactions
                WHERE scenario_label = ?
                ORDER BY transaction_id ASC
                LIMIT 1 OFFSET ?;
                """,
                (scenario, offset),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT transaction_id FROM transactions
                WHERE scenario_label = ? AND is_suspicious = ?
                ORDER BY transaction_id ASC
                LIMIT 1 OFFSET ?;
                """,
                (scenario, is_suspicious, offset),
            ).fetchone()
    assert row is not None
    return str(row["transaction_id"])


def test_rule_catalog_endpoint(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify GET /risk/rules returns the documented rule catalog."""
    client, _ = seeded_env
    res = client.get("/risk/rules")
    assert res.status_code == 200
    rules = res.json()
    assert len(rules) >= 15
    rule_ids = {r["rule_id"] for r in rules}
    assert "PROFILE_VALUE_ANOMALY" in rule_ids
    assert "VENDOR_BEC_BANK_MODIFIED" in rule_ids
    assert "STRUCTURING_CUMULATIVE_DRAIN" in rule_ids
    assert "IMPOSSIBLE_TRAVEL_GEO_VELOCITY" in rule_ids
    assert "THREAT_INTEL_ACTIVE_MATCH" in rule_ids


def test_legitimate_capex_high_value_reduces_false_positives(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify contextual scoring avoids baseline false positives on legitimate CapEx purchases."""
    client, db_file = seeded_env
    capex_tx_id = _find_tx_id_by_scenario(db_file, "legitimate_capex_high_value")

    comp_res = client.get(f"/transactions/{capex_tx_id}/risk/compare")
    assert comp_res.status_code == 200
    comp = comp_res.json()

    # Baseline flags the huge raw dollar amount (>= 60), whereas Contextual sees CapEx profile + vendor match (0)
    assert comp["baseline"]["risk_score"] >= 60
    assert comp["contextual"]["risk_score"] == 0
    assert comp["delta_contextual_vs_baseline"] < 0
    assert comp["contextual"]["exceeds_user_threshold"] is False


def test_low_and_slow_ato_detected_by_contextual_and_capped_at_100(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify low-and-slow ATO evades baseline but is caught by contextual forensic rules."""
    client, db_file = seeded_env
    ato_tx_id = _find_tx_id_by_scenario(db_file, "low_and_slow_ato")

    base_res = client.get(f"/transactions/{ato_tx_id}/risk?method=baseline").json()
    ctx_res = client.get(f"/transactions/{ato_tx_id}/risk?method=contextual").json()

    # Baseline misses the modest transfer amount
    assert base_res["exceeds_user_threshold"] is False

    # Contextual triggers failed logins, unseen device, impossible travel, rapid new beneficiary
    assert ctx_res["risk_score"] >= 85
    assert ctx_res["risk_score"] <= 100
    assert ctx_res["raw_points_sum"] >= ctx_res["risk_score"]
    assert ctx_res["exceeds_user_threshold"] is True

    triggered_ids = {r["rule_id"] for r in ctx_res["triggered_rules"]}
    assert "REPEATED_FAILED_LOGINS" in triggered_ids
    assert "UNSEEN_DEVICE_USED" in triggered_ids
    assert "IMPOSSIBLE_TRAVEL_GEO_VELOCITY" in triggered_ids
    assert "RAPID_NEW_BENEFICIARY" in triggered_ids
    assert "Counterfactual:" in ctx_res["counterfactual_summary"]


def test_b2b_vendor_bec_bank_tamper_detection(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify VENDOR_BEC_BANK_MODIFIED catches existing vendors with recently altered bank details."""
    client, db_file = seeded_env
    bec_tx_id = _find_tx_id_by_scenario(db_file, "b2b_vendor_bec_tamper")

    ctx_res = client.get(f"/transactions/{bec_tx_id}/risk?method=contextual").json()
    triggered_ids = {r["rule_id"] for r in ctx_res["triggered_rules"]}

    assert "VENDOR_BEC_BANK_MODIFIED" in triggered_ids
    assert ctx_res["risk_score"] >= 65
    assert ctx_res["exceeds_user_threshold"] is True


def test_structuring_and_cross_user_mule_convergence(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify structuring bursts trigger STRUCTURING_CUMULATIVE_DRAIN and CROSS_USER_MULE_CONVERGENCE."""
    client, db_file = seeded_env
    # Pick the 3rd leg (offset=5 -> 2nd burst, 3rd leg) so both multi-tx structuring and cross-user mule apply
    smurf_tx_id = _find_tx_id_by_scenario(db_file, "structured_smurfing_drain", offset=5)

    ctx_res = client.get(f"/transactions/{smurf_tx_id}/risk?method=contextual").json()
    triggered_ids = {r["rule_id"] for r in ctx_res["triggered_rules"]}

    assert "STRUCTURING_CUMULATIVE_DRAIN" in triggered_ids
    assert "CROSS_USER_MULE_CONVERGENCE" in triggered_ids
    assert ctx_res["risk_score"] == 100


def test_threat_intel_active_vs_expired_indicators(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify active threat-intel indicators boost score while expired indicators add 0 points."""
    client, db_file = seeded_env

    active_ti_tx = _find_tx_id_by_scenario(
        db_file, "threat_intel_active_or_stale_ip", is_suspicious=1
    )
    stale_ti_tx = _find_tx_id_by_scenario(
        db_file, "threat_intel_active_or_stale_ip", is_suspicious=0
    )

    # 1. Active indicator pushes stealthy session from below threshold (Contextual) to above threshold (Contextual+TI)
    active_comp = client.get(f"/transactions/{active_ti_tx}/risk/compare").json()
    assert active_comp["contextual"]["risk_score"] == 50
    assert active_comp["contextual"]["exceeds_user_threshold"] is False
    assert active_comp["contextual_ti"]["risk_score"] >= 70
    assert active_comp["contextual_ti"]["exceeds_user_threshold"] is True
    assert active_comp["delta_ti_vs_contextual"] >= 20

    # 2. Expired indicator records informational rule with 0 points awarded
    stale_ti_res = client.get(f"/transactions/{stale_ti_tx}/risk?method=contextual_ti").json()
    ti_rules = [
        r
        for r in stale_ti_res["triggered_rules"]
        if r["rule_id"] == "THREAT_INTEL_EXPIRED_INDICATOR"
    ]
    assert len(ti_rules) == 1
    assert ti_rules[0]["points_awarded"] == 0
    assert stale_ti_res["risk_score"] == 0


def test_missing_authentication_telemetry_explicit_rule(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify missing authentication history triggers MISSING_AUTH_TELEMETRY rather than silent safety."""
    client, db_file = seeded_env
    tx_id = _find_tx_id_by_scenario(db_file, "normal_routine")

    with get_connection(db_file) as conn:
        user_id = conn.execute(
            "SELECT user_id FROM transactions WHERE transaction_id = ?;",
            (tx_id,),
        ).fetchone()["user_id"]
        conn.execute("DELETE FROM authentication_events WHERE user_id = ?;", (user_id,))
        conn.commit()

    ctx_res = client.get(f"/transactions/{tx_id}/risk?method=contextual").json()
    triggered_ids = {r["rule_id"] for r in ctx_res["triggered_rules"]}
    assert "MISSING_AUTH_TELEMETRY" in triggered_ids


def test_scoring_error_handling(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify 404 on unknown transaction_id and 422 on invalid scoring method."""
    client, _ = seeded_env

    res_404 = client.get("/transactions/TX-DOES-NOT-EXIST/risk?method=contextual")
    assert res_404.status_code == 404

    res_bad_method = client.get("/transactions/TX-0001/risk?method=magic_ml")
    assert res_bad_method.status_code == 422
