from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.schemas.api_schemas import (
    ConfusionMatrixSchema,
    DashboardSummarySchema,
    EvaluationReportResponseSchema,
    ExpenditureModelBreakdownSchema,
    MethodEvaluationMetricsSchema,
    ScenarioBreakdownItemSchema,
    ThresholdTradeoffPointSchema,
)
from app.services.scoring import (
     VALID_SCORING_METHODS,
    _evaluate_baseline_rules,
    _evaluate_contextual_rules,
    _evaluate_threat_intel_rules,
)
from app.services.transactions import list_transactions

EVALUATION_DISCLAIMER = (
    "Synthetic Evaluation Disclaimer: All metrics are computed on deterministic synthetic transactions "
    "with independent ground-truth labels. Results demonstrate the comparative behavior of transaction-only, "
    "contextual, and threat-intelligence-enriched rules in a classroom prototype and do NOT establish "
    "real-world banking fraud detection accuracy."
)

POSITIVE_PREDICTION_DEFINITION = (
    "A transaction is classified as a Positive (Flagged) prediction when its capped rule-based risk score "
    "(0-100) is greater than or equal to the active alert threshold (score >= threshold). "
    "TP = suspicious & flagged; FP = legitimate & flagged; TN = legitimate & unflagged; FN = suspicious & unflagged."
)

SWEEP_THRESHOLDS = (20, 30, 40, 50, 60, 70, 80, 90)


def _safe_div(num: float, den: float) -> float:
    return round(num / den, 4) if den > 0 else 0.0


def _compute_binary_metrics(
    records: List[Dict[str, Any]],
    score_key: str,
    use_user_threshold: bool,
    fixed_threshold: int,
) -> tuple[ConfusionMatrixSchema, float, float, float, float, int, float]:
    tp = fp = tn = fn = 0
    for r in records:
        score = int(r[score_key])
        thresh = int(r["user_threshold"]) if use_user_threshold else fixed_threshold
        pred_pos = score >= thresh
        actual_pos = bool(r["is_suspicious"])

        if actual_pos and pred_pos:
            tp += 1
        elif not actual_pos and pred_pos:
            fp += 1
        elif not actual_pos and not pred_pos:
            tn += 1
        else:
            fn += 1

    total = len(records)
    flagged = tp + fp
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    fpr = _safe_div(fp, fp + tn)
    flagged_pct = round((flagged / total) * 100.0, 2) if total > 0 else 0.0

    cm = ConfusionMatrixSchema(
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
    )
    return cm, precision, recall, f1, fpr, flagged, flagged_pct


def compute_evaluation_report(
    threshold: int = 60,
    use_user_preferences_threshold: bool = False,
    db_path: Optional[Path] = None,
) -> EvaluationReportResponseSchema:
    """Evaluate all three scoring approaches across the synthetic dataset without data leakage."""
    with get_connection(db_path) as conn:
        user_rows = conn.execute("SELECT * FROM users;").fetchall()
        users_by_id = {u["user_id"]: u for u in user_rows}

        pref_rows = conn.execute("SELECT user_id, risk_threshold FROM user_preferences;").fetchall()
        prefs_by_id = {p["user_id"]: int(p["risk_threshold"]) for p in pref_rows}

        tx_rows = conn.execute(
            "SELECT * FROM transactions ORDER BY transaction_id ASC;"
        ).fetchall()

        scored_records: List[Dict[str, Any]] = []
        for tx in tx_rows:
            uid = tx["user_id"]
            u_row = users_by_id[uid]
            u_thresh = prefs_by_id.get(uid, 60)

            base_rules = _evaluate_baseline_rules(conn, tx)
            ctx_rules = _evaluate_contextual_rules(conn, tx, u_row)
            ti_rules = _evaluate_threat_intel_rules(conn, tx)

            base_score = min(100, sum(r.points_awarded for r in base_rules))
            ctx_score = min(100, sum(r.points_awarded for r in ctx_rules))
            ti_score = min(100, sum(r.points_awarded for r in ctx_rules) + sum(r.points_awarded for r in ti_rules))

            scored_records.append(
                {
                    "transaction_id": tx["transaction_id"],
                    "user_id": uid,
                    "expenditure_model": u_row["expenditure_model"],
                    "is_suspicious": int(tx["is_suspicious"]),
                    "scenario_label": tx["scenario_label"],
                    "user_threshold": u_thresh,
                    "baseline": base_score,
                    "contextual": ctx_score,
                    "contextual_ti": ti_score,
                }
            )

    total_tx = len(scored_records)
    total_susp = sum(1 for r in scored_records if r["is_suspicious"] == 1)
    total_legit = total_tx - total_susp

    def _scenario_flag_rate(method_key: str, scenario_name: str) -> float:
        subset = [r for r in scored_records if r["scenario_label"] == scenario_name]
        if not subset:
            return 0.0
        flagged_cnt = sum(
            1
            for r in subset
            if r[method_key] >= (r["user_threshold"] if use_user_preferences_threshold else threshold)
        )
        return _safe_div(flagged_cnt, len(subset))

    methods_comparison: Dict[str, MethodEvaluationMetricsSchema] = {}
    for m in VALID_SCORING_METHODS:
        cm, prec, rec, f1, fpr, flagged_cnt, flagged_pct = _compute_binary_metrics(
            records=scored_records,
            score_key=m,
            use_user_threshold=use_user_preferences_threshold,
            fixed_threshold=threshold,
        )
        methods_comparison[m] = MethodEvaluationMetricsSchema(
            method=m,
            threshold_mode="per_user_preference" if use_user_preferences_threshold else "fixed",
            fixed_threshold=None if use_user_preferences_threshold else threshold,
            total_transactions=total_tx,
            total_suspicious_ground_truth=total_susp,
            total_legitimate_ground_truth=total_legit,
            confusion_matrix=cm,
            precision=prec,
            recall=rec,
            f1_score=f1,
            false_positive_rate=fpr,
            flagged_count=flagged_cnt,
            flagged_percentage=flagged_pct,
            ato_scenario_detection_rate=_scenario_flag_rate(m, "low_and_slow_ato"),
            bec_scenario_detection_rate=_scenario_flag_rate(m, "b2b_vendor_bec_tamper"),
            structuring_scenario_detection_rate=_scenario_flag_rate(m, "structured_smurfing_drain"),
            capex_false_positive_rate=_scenario_flag_rate(m, "legitimate_capex_high_value"),
        )

    # 2. Per-Scenario Breakdown
    scenario_names = sorted({r["scenario_label"] for r in scored_records})
    per_scenario: List[ScenarioBreakdownItemSchema] = []
    for s_name in scenario_names:
        sub = [r for r in scored_records if r["scenario_label"] == s_name]
        s_susp = sum(1 for r in sub if r["is_suspicious"] == 1)
        s_legit = len(sub) - s_susp
        if s_susp == len(sub):
            gt_class = "suspicious"
        elif s_legit == len(sub):
            gt_class = "legitimate"
        else:
            gt_class = "mixed"

        def _cnt_flagged(m_key: str) -> int:
            return sum(
                1
                for r in sub
                if r[m_key] >= (r["user_threshold"] if use_user_preferences_threshold else threshold)
            )

        b_cnt = _cnt_flagged("baseline")
        c_cnt = _cnt_flagged("contextual")
        t_cnt = _cnt_flagged("contextual_ti")

        per_scenario.append(
            ScenarioBreakdownItemSchema(
                scenario_label=s_name,
                ground_truth_class=gt_class,
                total_cases=len(sub),
                suspicious_cases=s_susp,
                legitimate_cases=s_legit,
                baseline_flagged_count=b_cnt,
                baseline_flagged_rate=_safe_div(b_cnt, len(sub)),
                contextual_flagged_count=c_cnt,
                contextual_flagged_rate=_safe_div(c_cnt, len(sub)),
                contextual_ti_flagged_count=t_cnt,
                contextual_ti_flagged_rate=_safe_div(t_cnt, len(sub)),
            )
        )

    # 3. Per-Expenditure-Model Breakdown (opex_heavy, capex_heavy, personal_consumption)
    exp_models = ["capex_heavy", "opex_heavy", "personal_consumption"]
    per_exp_model: List[ExpenditureModelBreakdownSchema] = []
    for em in exp_models:
        sub = [r for r in scored_records if r["expenditure_model"] == em]
        if not sub:
            continue
        _, b_p, b_r, b_f1, b_fpr, _, _ = _compute_binary_metrics(
            sub, "baseline", use_user_preferences_threshold, threshold
        )
        _, c_p, c_r, c_f1, c_fpr, _, _ = _compute_binary_metrics(
            sub, "contextual", use_user_preferences_threshold, threshold
        )
        _, t_p, t_r, t_f1, t_fpr, _, _ = _compute_binary_metrics(
            sub, "contextual_ti", use_user_preferences_threshold, threshold
        )
        per_exp_model.append(
            ExpenditureModelBreakdownSchema(
                expenditure_model=em,
                total_transactions=len(sub),
                baseline_precision=b_p,
                baseline_recall=b_r,
                baseline_f1=b_f1,
                baseline_fpr=b_fpr,
                contextual_precision=c_p,
                contextual_recall=c_r,
                contextual_f1=c_f1,
                contextual_fpr=c_fpr,
                contextual_ti_precision=t_p,
                contextual_ti_recall=t_r,
                contextual_ti_f1=t_f1,
                contextual_ti_fpr=t_fpr,
            )
        )

    # 4. Threshold Trade-off Curve (20..90)
    tradeoff_curve: List[ThresholdTradeoffPointSchema] = []
    for t_val in SWEEP_THRESHOLDS:
        for m in VALID_SCORING_METHODS:
            _, prec, rec, f1, fpr, f_cnt, f_pct = _compute_binary_metrics(
                records=scored_records,
                score_key=m,
                use_user_threshold=False,
                fixed_threshold=t_val,
            )
            tradeoff_curve.append(
                ThresholdTradeoffPointSchema(
                    threshold=t_val,
                    method=m,
                    flagged_count=f_cnt,
                    flagged_percentage=f_pct,
                    precision=prec,
                    recall=rec,
                    f1_score=f1,
                    false_positive_rate=fpr,
                )
            )

    return EvaluationReportResponseSchema(
        evaluation_disclaimer=EVALUATION_DISCLAIMER,
        positive_prediction_definition=POSITIVE_PREDICTION_DEFINITION,
        threshold_evaluated=threshold,
        use_user_preferences_threshold=use_user_preferences_threshold,
        methods_comparison=methods_comparison,
        per_scenario_breakdown=per_scenario,
        per_expenditure_model_breakdown=per_exp_model,
        threshold_tradeoff_curve=tradeoff_curve,
    )


def get_dashboard_summary(db_path: Optional[Path] = None) -> DashboardSummarySchema:
    """Return top-level KPI counts and recent transactions for the UI dashboard."""
    with get_connection(db_path) as conn:
        total_users = int(conn.execute("SELECT COUNT(*) AS cnt FROM users;").fetchone()["cnt"])
        exp_rows = conn.execute(
            "SELECT expenditure_model, COUNT(*) AS cnt FROM users GROUP BY expenditure_model;"
        ).fetchall()
        users_by_exp = {r["expenditure_model"]: int(r["cnt"]) for r in exp_rows}

        total_tx = int(conn.execute("SELECT COUNT(*) AS cnt FROM transactions;").fetchone()["cnt"])

        ver_rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM verification_requests GROUP BY status;"
        ).fetchall()
        ver_map = {r["status"]: int(r["cnt"]) for r in ver_rows}

        inc_rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM incidents GROUP BY status;"
        ).fetchall()
        inc_map = {r["status"]: int(r["cnt"]) for r in inc_rows}

    recent = list_transactions(limit=10, offset=0, db_path=db_path)

    return DashboardSummarySchema(
        disclaimer=EVALUATION_DISCLAIMER,
        total_users=total_users,
        users_by_expenditure_model=users_by_exp,
        total_transactions=total_tx,
        pending_verifications_count=ver_map.get("pending", 0),
        confirmed_verifications_count=ver_map.get("confirmed_legitimate", 0),
        denied_verifications_count=ver_map.get("denied_suspicious", 0),
        open_incidents_count=inc_map.get("open", 0),
        investigating_incidents_count=inc_map.get("investigating", 0),
        closed_incidents_count=inc_map.get("closed", 0),
        recent_transactions=recent.items,
    )
