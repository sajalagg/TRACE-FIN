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
        total_users = int(
            conn.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE role = 'customer';"
            ).fetchone()["cnt"]
        )
        exp_rows = conn.execute(
            "SELECT expenditure_model, COUNT(*) AS cnt FROM users WHERE role = 'customer' GROUP BY expenditure_model;"
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


PROFILE_DISPLAY_LABELS: Dict[str, str] = {
    "student": "Student",
    "salaried_individual": "Salaried Individual",
    "freelancer": "Freelancer / Consultant",
    "sme_opex_merchant": "Small Business",
    "enterprise_capex_firm": "Enterprise",
    "high_net_worth": "HNI Individuals",
    "small business": "Small Business",
    "enterprise": "Enterprise",
    "HNI indiviuals": "HNI Individuals",
    "HNI individuals": "HNI Individuals",
}

SCENARIO_METADATA: Dict[str, Dict[str, str]] = {
    "legitimate_capex_high_value": {
        "code": "SCEN-01",
        "name": "Enterprise CapEx Equipment Purchase",
        "type": "Legitimate",
        "headline": "High-value industrial machinery wire (₹35k–₹115k) to an established B2B supplier during business hours.",
        "key_lesson": "Transaction-only rules flag the large rupee amount (False Positive), while Contextual Scoring verifies CapEx profile + supply-chain vendor affinity.",
    },
    "legitimate_opex_payroll_cycle": {
        "code": "SCEN-02",
        "name": "Month-End OpEx & Payroll Settlement",
        "type": "Legitimate",
        "headline": "Scheduled month-end (25th–5th) batch payroll or wholesale inventory settlement by an OpEx SME.",
        "key_lesson": "Cash-flow calendar awareness suppresses false positives on recurring month-end operational spikes.",
    },
    "legitimate_travel_new_ip": {
        "code": "SCEN-03",
        "name": "Authorized Travel with Known Device",
        "type": "Legitimate",
        "headline": "Routine transfer from a new roaming IP address, but authenticated cleanly on the user's primary registered device.",
        "key_lesson": "Correlating device continuity prevents flagging legitimate traveling users who change IP subnets.",
    },
    "low_and_slow_ato": {
        "code": "SCEN-04",
        "name": "Low-and-Slow Account Takeover (ATO)",
        "type": "Attack",
        "headline": "Sub-threshold transfer preceded by credential-stuffing failures, an unseen device, impossible travel, and a newly added beneficiary.",
        "key_lesson": "Evades static rupee thresholds, but Contextual Scoring correlates the full kill-chain (Recon -> Initial Access -> Preparation -> Exfiltration).",
    },
    "b2b_vendor_bec_tamper": {
        "code": "SCEN-05",
        "name": "B2B Vendor BEC Bank Account Tamper",
        "type": "Attack",
        "headline": "Corporate invoice payment to a trusted vendor whose bank account/IBAN was modified minutes before the wire.",
        "key_lesson": "Detects Business Email Compromise (BEC) by correlating beneficiary bank-modification events with subsequent high-value wires.",
    },
    "structured_smurfing_drain": {
        "code": "SCEN-06",
        "name": "Structured Smurfing / 24h Cumulative Drain",
        "type": "Attack",
        "headline": "Rapid burst of split transfers individually below the user's single-transaction max, but cumulatively draining turnover.",
        "key_lesson": "Rolling 24-hour velocity and cumulative turnover ratio catch split-transfer structuring missed by single-tx checks.",
    },
    "threat_intel_active_or_stale_ip": {
        "code": "SCEN-07",
        "name": "Threat Intelligence Indicator Match (Fresh vs Expired)",
        "type": "Attack",
        "headline": "Transactions originating from known Tor/Botnet C2 IPs or flagged mule accounts vs expired historical indicators.",
        "key_lesson": "Demonstrates freshness-aware TI gating: active indicators boost Method 3 scores while expired indicators contribute 0 points.",
    },
    "normal_routine": {
        "code": "SCEN-08",
        "name": "Routine Baseline Activity",
        "type": "Legitimate",
        "headline": "Everyday personal and business transfers within expected amount bands, operating hours, and established counterparties.",
        "key_lesson": "Establishes low-noise normal behavior across Individual, OpEx, and CapEx accounts.",
    },
}


def _score_to_ui_level(score: int) -> str:
    if score >= 85:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def get_full_analytics_dataset(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return all SQLite transactions enriched with 3-method scores, KPIs, scenarios, and activity series."""
    with get_connection(db_path) as conn:
        user_rows = conn.execute("SELECT * FROM users;").fetchall()
        users_by_id = {u["user_id"]: u for u in user_rows}
        customer_users_cnt = sum(1 for u in user_rows if (u["role"] if "role" in u.keys() else "customer") == "customer")

        pref_rows = conn.execute("SELECT user_id, risk_threshold FROM user_preferences;").fetchall()
        prefs_by_id = {p["user_id"]: int(p["risk_threshold"]) for p in pref_rows}

        ver_rows = conn.execute("SELECT transaction_id, status FROM verification_requests;").fetchall()
        ver_by_tx = {r["transaction_id"]: r["status"] for r in ver_rows}

        inc_rows = conn.execute("SELECT incident_id, transaction_id, status FROM incidents;").fetchall()
        inc_by_tx = {r["transaction_id"]: r["status"] for r in inc_rows}
        open_incidents_count = sum(1 for r in inc_rows if r["status"] in ("open", "investigating"))

        tx_rows = conn.execute(
            """
            SELECT * FROM transactions
            ORDER BY CASE WHEN scenario_label = 'live_custom_demo' THEN 0 ELSE 1 END ASC,
                     timestamp_utc DESC,
                     transaction_id DESC;
            """
        ).fetchall()

        enriched_txs: List[Dict[str, Any]] = []
        representative_by_scenario: Dict[str, str] = {}
        scenario_counts: Dict[str, int] = {}

        for tx in tx_rows:
            tx_id = tx["transaction_id"]
            uid = tx["user_id"]
            u_row = users_by_id[uid]
            u_thresh = prefs_by_id.get(uid, 60)
            scen_label = tx["scenario_label"]

            scenario_counts[scen_label] = scenario_counts.get(scen_label, 0) + 1

            base_rules = _evaluate_baseline_rules(conn, tx)
            ctx_rules = _evaluate_contextual_rules(conn, tx, u_row)
            ti_rules = _evaluate_threat_intel_rules(conn, tx)

            m1_score = min(100, sum(r.points_awarded for r in base_rules))
            m2_score = min(100, sum(r.points_awarded for r in ctx_rules))
            m3_score = min(100, m2_score + sum(r.points_awarded for r in ti_rules))

            m1_level = _score_to_ui_level(m1_score)
            m2_level = _score_to_ui_level(m2_score)
            m3_level = _score_to_ui_level(m3_score)

            # Pick the clearest representative transaction for each scenario
            if scen_label not in representative_by_scenario:
                representative_by_scenario[scen_label] = tx_id
            elif scen_label == "legitimate_capex_high_value" and m1_score >= 60 and m2_score < 30:
                representative_by_scenario[scen_label] = tx_id
            elif scen_label == "threat_intel_active_or_stale_ip" and m3_score > m2_score:
                representative_by_scenario[scen_label] = tx_id

            tx_keys = tx.keys()
            raw_status = str(tx["status"]) if "status" in tx_keys and tx["status"] else "COMPLETED"
            decision_reason = (
                str(tx["decision_reason"])
                if "decision_reason" in tx_keys and tx["decision_reason"]
                else "Approved under baseline simulation policy."
            )
            balance_deducted = (
                bool(tx["balance_deducted"]) if "balance_deducted" in tx_keys else True
            )
            session_id = str(tx["session_id"]) if "session_id" in tx_keys and tx["session_id"] else None

            # Determine operational workflow status from verification/incident tables, persisted status, or score band
            if tx_id in inc_by_tx:
                inc_st = inc_by_tx[tx_id]
                status_str = "Blocked" if inc_st in ("open", "investigating") else "Settled"
            elif tx_id in ver_by_tx:
                ver_st = ver_by_tx[tx_id]
                if ver_st == "denied_suspicious":
                    status_str = "Blocked"
                elif ver_st == "confirmed_legitimate":
                    status_str = "Settled"
                elif raw_status == "HELD_HIGH_RISK":
                    status_str = "Flagged"
                else:
                    status_str = "Pending Review"
            elif raw_status == "BLOCKED":
                status_str = "Blocked"
            elif raw_status == "HELD_HIGH_RISK":
                status_str = "Flagged"
            elif raw_status == "PENDING_VERIFICATION":
                status_str = "Pending Review"
            elif scen_label == "live_custom_demo" and raw_status == "COMPLETED":
                status_str = "Settled"
            else:
                if m3_score >= 85:
                    status_str = "Flagged"
                elif m2_score >= u_thresh or m3_score >= u_thresh:
                    status_str = "Pending Review"
                else:
                    status_str = "Settled"

            all_active_rules = [*ctx_rules, *ti_rules]
            evidence_flags = [r.rule_id for r in all_active_rules]
            alert_reasons = [r.explanation for r in all_active_rules]

            # Build waterfall contribution dictionary showing Baseline rules + Contextual deltas + TI deltas
            contribs: Dict[str, int] = {}
            base_map = {r.rule_id: r.points_awarded for r in base_rules}
            ctx_map = {r.rule_id: r.points_awarded for r in ctx_rules}
            for r in base_rules:
                contribs[f"M1: {r.rule_id}"] = r.points_awarded
            # Contextual suppressions (baseline rules suppressed by context)
            for r_id, b_pts in base_map.items():
                c_pts = ctx_map.get(r_id, 0)
                if c_pts < b_pts:
                    contribs[f"CTX_SUPPRESS: {r_id}"] = c_pts - b_pts
            # Contextual additions
            for r in ctx_rules:
                if r.rule_id not in base_map:
                    contribs[f"M2: {r.rule_id}"] = r.points_awarded
                elif r.points_awarded > base_map[r.rule_id]:
                    contribs[f"M2_BOOST: {r.rule_id}"] = r.points_awarded - base_map[r.rule_id]
            # TI additions
            for r in ti_rules:
                if r.points_awarded > 0:
                    contribs[f"M3_TI: {r.rule_id}"] = r.points_awarded

            if not alert_reasons:
                alert_reasons = [
                    f"Transaction aligns with {u_row['display_name']}'s {u_row['expenditure_model']} profile and established vendor history."
                ]

            enriched_txs.append(
                {
                    "id": tx_id,
                    "transaction_id": tx_id,
                    "timestamp": tx["timestamp_utc"],
                    "timestamp_utc": tx["timestamp_utc"],
                    "sender_id": uid,
                    "sender_name": u_row["display_name"],
                    "sender_profile": PROFILE_DISPLAY_LABELS.get(u_row["profile_type"], u_row["profile_type"]),
                    "sender_profile_raw": u_row["profile_type"],
                    "sender_account_category": u_row["account_category"],
                    "sender_expenditure_model": u_row["expenditure_model"],
                    "sender_industry": u_row["industry_sector"],
                    "sender_net_worth_band": u_row["net_worth_band"],
                    "sender_net_worth": float(u_row["estimated_net_worth"]),
                    "sender_monthly_turnover": float(u_row["declared_monthly_turnover"]),
                    "sender_typical_tx": float(u_row["typical_tx_amount"]),
                    "sender_max_tx": float(u_row["typical_max_tx_amount"]),
                    "sender_operating_hours": u_row["operating_hours_utc"],
                    "sender_home_geo": u_row["home_geo_location"],
                    "user_alert_threshold": u_thresh,
                    "beneficiary_id": tx["beneficiary_id"],
                    "beneficiary_name": tx["beneficiary_name"],
                    "beneficiary_category": tx["beneficiary_category"],
                    "beneficiary_industry": tx["beneficiary_industry"],
                    "beneficiary_country": tx["geo_location"],
                    "device_id": tx["device_id"],
                    "ip_address": tx["ip_address"],
                    "geo_location": tx["geo_location"],
                    "amount": float(tx["amount"]),
                    "currency": tx["currency"],
                    "status": status_str,
                    "raw_status": raw_status,
                    "decision_reason": decision_reason,
                    "balance_deducted": balance_deducted,
                    "session_id": session_id,
                    "method1_score": m1_score,
                    "method1_level": m1_level,
                    "method2_score": m2_score,
                    "method2_level": m2_level,
                    "method3_score": m3_score,
                    "method3_level": m3_level,
                    "ground_truth": int(tx["is_suspicious"]),
                    "scenario_label": scen_label,
                    "scenario_id": SCENARIO_METADATA.get(scen_label, {}).get("code", "LIVE-TX" if scen_label == "live_custom_demo" else scen_label),
                    "is_live_created": scen_label == "live_custom_demo",
                    "evidence_flags": evidence_flags,
                    "alert_reasons": alert_reasons,
                    "score_contributions": contribs,
                }
            )

    total = len(enriched_txs)
    live_created_cnt = sum(1 for t in enriched_txs if t.get("is_live_created"))
    high_risk = sum(1 for t in enriched_txs if t["method2_score"] >= 60 or t["method3_score"] >= 60)
    critical_risk = sum(1 for t in enriched_txs if t["method3_score"] >= 85)
    needs_review = sum(1 for t in enriched_txs if t["status"] in ("Pending Review", "Flagged"))
    alert_rate = round((high_risk / total) * 100, 1) if total else 0.0
    true_attacks = sum(1 for t in enriched_txs if t["ground_truth"] == 1)

    avg_m1 = round(sum(t["method1_score"] for t in enriched_txs) / total, 1) if total else 0.0
    avg_m2 = round(sum(t["method2_score"] for t in enriched_txs) / total, 1) if total else 0.0
    avg_m3 = round(sum(t["method3_score"] for t in enriched_txs) / total, 1) if total else 0.0

    # Activity chart grouped by date from actual SQLite timestamps
    by_day: Dict[str, List[int]] = {}
    for t in enriched_txs:
        day_str = t["timestamp"][:10]
        by_day.setdefault(day_str, []).append(t["method2_score"])

    activity_series = [
        {
            "datetime": f"{day_key} 12:00",
            "count": len(scores_list),
            "avg_risk": round(sum(scores_list) / len(scores_list), 1),
        }
        for day_key, scores_list in sorted(by_day.items())
    ]

    scenarios_out: List[Dict[str, Any]] = []
    for scen_key, meta in SCENARIO_METADATA.items():
        if scen_key in scenario_counts:
            scenarios_out.append(
                {
                    "id": meta["code"],
                    "scenario_label": scen_key,
                    "name": meta["name"],
                    "type": meta["type"],
                    "tx_id": representative_by_scenario.get(scen_key, "TX-0001"),
                    "count": scenario_counts[scen_key],
                    "headline": meta["headline"],
                    "key_lesson": meta["key_lesson"],
                }
            )

    min_date = min((t["timestamp"][:10] for t in enriched_txs), default="2026-03-01")
    max_date = max((t["timestamp"][:10] for t in enriched_txs), default="2026-03-30")

    return {
        "metrics": {
            "total_transactions": total,
            "live_created_count": live_created_cnt,
            "historical_baseline_count": total - live_created_cnt,
            "total_users": customer_users_cnt,
            "high_risk_count": high_risk,
            "critical_risk_count": critical_risk,
            "needs_review_count": needs_review,
            "open_incidents": open_incidents_count,
            "alert_rate_pct": alert_rate,
            "true_attack_count": true_attacks,
            "avg_method1_score": avg_m1,
            "avg_method2_score": avg_m2,
            "avg_method3_score": avg_m3,
            "snapshot_time": "Live SQLite Engine",
            "reporting_period": f"{min_date} to {max_date}",
        },
        "transactions": enriched_txs,
        "activity_chart": activity_series,
        "scenarios": scenarios_out,
    }


def get_threat_intelligence_registry(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return all synthetic threat-intelligence indicators from SQLite with freshness and linked TX IDs."""
    with get_connection(db_path) as conn:
        ti_rows = conn.execute(
            "SELECT * FROM threat_intelligence ORDER BY indicator ASC;"
        ).fetchall()
        tx_rows = conn.execute(
            "SELECT transaction_id, ip_address, beneficiary_id FROM transactions ORDER BY transaction_id ASC;"
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for idx, row in enumerate(ti_rows, start=1):
        ind_val = row["indicator"]
        ind_type_raw = row["indicator_type"]
        ui_type = "IP_ADDRESS" if ind_type_raw == "ip_address" else "BENEFICIARY_IBAN"
        conf_raw = row["confidence_level"].lower()
        conf_label = conf_raw.capitalize()
        conf_score = 0.95 if conf_raw == "high" else (0.78 if conf_raw == "medium" else 0.45)

        expires_str = row["expires_at_utc"]
        is_expired = expires_str < "2026-03-01T00:00:00Z"
        status_str = "EXPIRED" if is_expired else "ACTIVE"

        if is_expired:
            score_impact = 0
        elif conf_raw == "high":
            score_impact = 35
        elif conf_raw == "medium":
            score_impact = 20
        else:
            score_impact = 10

        linked_txs = [
            t["transaction_id"]
            for t in tx_rows
            if (ind_type_raw == "ip_address" and t["ip_address"] == ind_val)
            or (ind_type_raw == "beneficiary_account" and t["beneficiary_id"] == ind_val)
        ]

        results.append(
            {
                "indicator_id": f"TI-IND-900{idx}",
                "indicator": ind_val,
                "masked_value": ind_val,
                "type": ui_type,
                "indicator_type": ind_type_raw,
                "source_name": row["source_label"],
                "confidence": conf_label,
                "confidence_score": conf_score,
                "first_seen": row["first_seen_utc"],
                "last_seen": row["last_seen_utc"],
                "expires_at": expires_str,
                "status": status_str,
                "score_impact": score_impact,
                "threat_actor_or_campaign": row["threat_category"],
                "notes": row["description"],
                "associated_tx_ids": linked_txs,
            }
        )
    return results


