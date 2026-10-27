from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.run_evaluation import run_and_export_evaluation
from scripts.seed_demo_data import seed_database


@pytest.fixture()
def seeded_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    """Provide a TestClient and temporary database seeded with deterministic synthetic data."""
    db_file = tmp_path / "test_evaluation_stage10.db"
    monkeypatch.setenv("TRACE_FIN_DB_PATH", str(db_file))
    seed_database(db_path=db_file, total_transactions=500, seed=42)
    return TestClient(app), db_file


def test_dashboard_summary_endpoint(seeded_env: tuple[TestClient, Path]) -> None:
    """Verify GET /dashboard/summary returns KPI counts and recent transactions."""
    client, _ = seeded_env
    res = client.get("/dashboard/summary")
    assert res.status_code == 200
    data = res.json()

    assert data["total_users"] == 12
    assert data["total_transactions"] == 500
    assert data["users_by_expenditure_model"] == {
        "personal_consumption": 6,
        "opex_heavy": 3,
        "capex_heavy": 3,
    }
    assert len(data["recent_transactions"]) == 10


def test_evaluation_metrics_progression_across_three_methods(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify contextual and contextual_ti outperform baseline in Precision, Recall, F1, and FPR."""
    client, _ = seeded_env
    res = client.get("/evaluation/metrics?threshold=60")
    assert res.status_code == 200
    report = res.json()

    mc = report["methods_comparison"]
    base = mc["baseline"]
    ctx = mc["contextual"]
    ti = mc["contextual_ti"]

    # 1. Contextual must dramatically reduce False Positive Rate vs Baseline (especially on CapEx purchases)
    assert ctx["false_positive_rate"] < base["false_positive_rate"]
    assert ctx["capex_false_positive_rate"] == 0.0
    assert base["capex_false_positive_rate"] > 0.5

    # 2. Contextual must catch low-and-slow ATO, BEC tamper, and Structuring at a much higher rate than Baseline
    assert ctx["ato_scenario_detection_rate"] == 1.0
    assert base["ato_scenario_detection_rate"] < 0.5
    assert ctx["bec_scenario_detection_rate"] == 1.0
    assert base["bec_scenario_detection_rate"] < ctx["bec_scenario_detection_rate"]
    assert ctx["structuring_scenario_detection_rate"] == 1.0

    # 3. Contextual + Threat Intel must achieve higher Recall & F1 than Contextual alone (catching active TI cases)
    # while keeping False Positive Rate identical (ignoring expired TI indicators!)
    assert ti["recall"] > ctx["recall"]
    assert ti["f1_score"] > ctx["f1_score"] > base["f1_score"]
    assert ti["false_positive_rate"] == ctx["false_positive_rate"]

    # 4. Verify per-scenario, per-expenditure-model, and threshold curve structures
    assert len(report["per_scenario_breakdown"]) == 8
    assert len(report["per_expenditure_model_breakdown"]) == 3
    assert len(report["threshold_tradeoff_curve"]) == 8 * 3  # 8 thresholds * 3 methods


def test_cli_evaluation_exporter(
    seeded_env: tuple[TestClient, Path],
    tmp_path: Path,
) -> None:
    """Verify scripts/run_evaluation.py exports JSON and CSV files reproducibly."""
    _, _ = seeded_env
    out_dir = tmp_path / "exports"
    paths = run_and_export_evaluation(threshold=60, reseed=False, output_dir=out_dir)

    assert paths["json"].exists()
    assert paths["csv"].exists()
    csv_lines = paths["csv"].read_text(encoding="utf-8").strip().splitlines()
    assert len(csv_lines) == 4  # header + 3 scoring methods


def test_dashboard_dataset_and_threat_intel_endpoints(
    seeded_env: tuple[TestClient, Path],
) -> None:
    """Verify GET /dashboard/dataset and GET /threat-intel return live enriched SQLite data."""
    client, _ = seeded_env
    ds_res = client.get("/dashboard/dataset")
    assert ds_res.status_code == 200
    ds = ds_res.json()
    assert ds["metrics"]["total_transactions"] == 500
    assert len(ds["transactions"]) == 500
    assert len(ds["scenarios"]) == 8
    assert len(ds["activity_chart"]) > 0

    ti_res = client.get("/threat-intel")
    assert ti_res.status_code == 200
    ti_list = ti_res.json()
    assert len(ti_list) == 5
    assert any(i["status"] == "ACTIVE" and i["score_impact"] == 35 for i in ti_list)
    assert any(i["status"] == "EXPIRED" and i["score_impact"] == 0 for i in ti_list)

