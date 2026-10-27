"""
TRACE-Fin Live API Data Provider Service.
Connects exclusively to the FastAPI + SQLite backend over HTTP.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
import streamlit as st

from services.config import API_BASE_URL, API_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Internal HTTP helpers (FastAPI Client)
# ---------------------------------------------------------------------------

def _api_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return {"ok": True, "data": resp.json()}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {exc.response.status_code}: {detail}", "data": None}
    except Exception as exc:
        return {"ok": False, "error": f"Cannot reach FastAPI backend at {API_BASE_URL} ({exc})", "data": None}


def _api_post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return {"ok": True, "data": resp.json()}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {exc.response.status_code}: {detail}", "data": None}
    except Exception as exc:
        return {"ok": False, "error": f"Cannot reach FastAPI backend at {API_BASE_URL} ({exc})", "data": None}


def _api_patch(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
            resp = client.patch(url, json=payload)
            resp.raise_for_status()
            return {"ok": True, "data": resp.json()}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {exc.response.status_code}: {detail}", "data": None}
    except Exception as exc:
        return {"ok": False, "error": f"Cannot reach FastAPI backend at {API_BASE_URL} ({exc})", "data": None}


def _api_put(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
            resp = client.put(url, json=payload)
            resp.raise_for_status()
            return {"ok": True, "data": resp.json()}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {exc.response.status_code}: {detail}", "data": None}
    except Exception as exc:
        return {"ok": False, "error": f"Cannot reach FastAPI backend at {API_BASE_URL} ({exc})", "data": None}


def _score_to_level(score: int) -> str:
    if score >= 85:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Health & Full Dataset Cache
# ---------------------------------------------------------------------------

def check_backend_health() -> Dict[str, Any]:
    """Check if the FastAPI backend is reachable (`GET /health`)."""
    res = _api_get("/health")
    if res["ok"] and isinstance(res["data"], dict):
        return {"connected": True, "info": res["data"]}
    return {"connected": False, "error": res.get("error", "Backend unreachable")}


@st.cache_data(ttl=3, show_spinner=False)
def _fetch_analytics_dataset_cached() -> Dict[str, Any]:
    res = _api_get("/dashboard/dataset")
    if res["ok"] and isinstance(res["data"], dict):
        return res["data"]
    return {
        "metrics": {
            "total_transactions": 0,
            "total_users": 0,
            "high_risk_count": 0,
            "critical_risk_count": 0,
            "needs_review_count": 0,
            "open_incidents": 0,
            "alert_rate_pct": 0.0,
            "true_attack_count": 0,
            "avg_method1_score": 0.0,
            "avg_method2_score": 0.0,
            "avg_method3_score": 0.0,
            "snapshot_time": "Backend Offline",
            "reporting_period": "—",
        },
        "transactions": [],
        "activity_chart": [],
        "scenarios": [],
        "_error": res.get("error"),
    }


def invalidate_dataset_cache() -> None:
    """Clear the short-lived Streamlit dataset cache after creating a user, beneficiary, transaction, or incident."""
    _fetch_analytics_dataset_cached.clear()


# ---------------------------------------------------------------------------
# Dashboard & Transactions API
# ---------------------------------------------------------------------------

def get_dashboard_metrics() -> Dict[str, Any]:
    """Return high-level KPIs computed live by the FastAPI + SQLite backend."""
    dataset = _fetch_analytics_dataset_cached()
    return dataset["metrics"]


def get_transactions(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return enriched transaction list from the live FastAPI backend with client-side interactive filtering."""
    dataset = _fetch_analytics_dataset_cached()
    txs = list(dataset.get("transactions", []))

    if not filters:
        return txs

    search = str(filters.get("search") or "").lower().strip()
    if search:
        txs = [
            t for t in txs
            if search in t["id"].lower()
            or search in t.get("sender_name", "").lower()
            or search in t.get("sender_id", "").lower()
            or search in t.get("beneficiary_name", "").lower()
            or search in t.get("beneficiary_id", "").lower()
            or search in t.get("scenario_label", "").lower()
            or search in t.get("ip_address", "").lower()
        ]

    risk_levels = filters.get("risk_levels")
    if risk_levels:
        txs = [t for t in txs if t["method2_level"] in risk_levels or t["method3_level"] in risk_levels]

    statuses = filters.get("statuses")
    if statuses:
        txs = [t for t in txs if t["status"] in statuses]

    profiles = filters.get("profiles")
    if profiles:
        txs = [t for t in txs if t["sender_profile"] in profiles]

    exp_models = filters.get("expenditure_models")
    if exp_models:
        txs = [t for t in txs if t.get("sender_expenditure_model") in exp_models]

    min_amt = filters.get("min_amount")
    if min_amt is not None:
        txs = [t for t in txs if t["amount"] >= float(min_amt)]

    max_amt = filters.get("max_amount")
    if max_amt is not None:
        txs = [t for t in txs if t["amount"] <= float(max_amt)]

    scenario_id = filters.get("scenario_id")
    if scenario_id:
        txs = [
            t for t in txs
            if t.get("scenario_id") == scenario_id or t.get("scenario_label") == scenario_id
        ]

    return txs


def get_transaction(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Return a single enriched transaction record by ID."""
    txs = get_transactions()
    for t in txs:
        if t["id"] == transaction_id:
            return t
    return None


def get_transaction_detail_full(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Fetch `GET /transactions/{transaction_id}` directly from FastAPI (includes auth, device, and beneficiary events)."""
    res = _api_get(f"/transactions/{transaction_id}")
    if res["ok"] and isinstance(res["data"], dict):
        return res["data"]
    return None


def get_risk_scores(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Fetch `GET /transactions/{transaction_id}/risk/compare` from FastAPI and format for UI components."""
    res = _api_get(f"/transactions/{transaction_id}/risk/compare")
    if not res["ok"] or not isinstance(res["data"], dict):
        return None

    cmp_data = res["data"]
    tx_enriched = get_transaction(transaction_id) or {}

    base = cmp_data["baseline"]
    ctx = cmp_data["contextual"]
    ti = cmp_data["contextual_ti"]

    m1_score = int(base["risk_score"])
    m2_score = int(ctx["risk_score"])
    m3_score = int(ti["risk_score"])

    # Build waterfall contribution dictionary
    contribs = tx_enriched.get("score_contributions") or {}
    if not contribs:
        base_map = {r["rule_id"]: int(r["points_awarded"]) for r in base.get("triggered_rules", [])}
        ctx_map = {r["rule_id"]: int(r["points_awarded"]) for r in ctx.get("triggered_rules", [])}
        for r in base.get("triggered_rules", []):
            contribs[f"M1: {r['rule_id']}"] = int(r["points_awarded"])
        for r_id, b_pts in base_map.items():
            c_pts = ctx_map.get(r_id, 0)
            if c_pts < b_pts:
                contribs[f"CTX_SUPPRESS: {r_id}"] = c_pts - b_pts
        for r in ctx.get("triggered_rules", []):
            if r["rule_id"] not in base_map:
                contribs[f"M2: {r['rule_id']}"] = int(r["points_awarded"])
            elif int(r["points_awarded"]) > base_map[r["rule_id"]]:
                contribs[f"M2_BOOST: {r['rule_id']}"] = int(r["points_awarded"]) - base_map[r["rule_id"]]
        for r in cmp_data.get("ti_added_rules", []):
            if int(r["points_awarded"]) > 0:
                contribs[f"M3_TI: {r['rule_id']}"] = int(r["points_awarded"])

    # Build counterfactual projection from top triggered contextual/TI rules
    ctx_rules = ctx.get("triggered_rules", [])
    ti_rules = cmp_data.get("ti_added_rules", [])
    top_ctx_pts = max((int(r["points_awarded"]) for r in ctx_rules), default=0)
    top_ti_pts = sum(int(r["points_awarded"]) for r in ti_rules)
    proj_m2 = max(0, m2_score - top_ctx_pts) if m2_score >= 30 else m2_score
    proj_m3 = max(0, m3_score - max(top_ctx_pts, top_ti_pts)) if m3_score >= 30 else m3_score

    all_rules = [*ctx_rules, *[r for r in ti_rules if int(r["points_awarded"]) > 0]]
    evidence_flags = [r["rule_id"] for r in all_rules]
    alert_reasons = [r["explanation"] for r in all_rules]
    if not alert_reasons:
        alert_reasons = [ctx.get("score_interpretation", "Low risk score within expected user baseline.")]

    return {
        "transaction_id": transaction_id,
        "user_id": cmp_data["user_id"],
        "user_alert_threshold": cmp_data["user_alert_threshold"],
        "comparison_narrative": cmp_data["comparison_narrative"],
        "delta_contextual_vs_baseline": cmp_data["delta_contextual_vs_baseline"],
        "delta_ti_vs_contextual": cmp_data["delta_ti_vs_contextual"],
        "method1": {
            "name": "Transaction-Only Baseline",
            "score": m1_score,
            "raw_points": base["raw_points_sum"],
            "level": _score_to_level(m1_score),
            "description": base["score_interpretation"],
            "triggered_rules": base.get("triggered_rules", []),
            "counterfactual_summary": base.get("counterfactual_summary", ""),
        },
        "method2": {
            "name": "Contextual Forensic Scoring",
            "score": m2_score,
            "raw_points": ctx["raw_points_sum"],
            "level": _score_to_level(m2_score),
            "description": ctx["score_interpretation"],
            "triggered_rules": ctx.get("triggered_rules", []),
            "counterfactual_summary": ctx.get("counterfactual_summary", ""),
        },
        "method3": {
            "name": "Contextual + Threat Intelligence",
            "score": m3_score,
            "raw_points": ti["raw_points_sum"],
            "level": _score_to_level(m3_score),
            "description": ti["score_interpretation"],
            "triggered_rules": ti.get("triggered_rules", []),
            "counterfactual_summary": ti.get("counterfactual_summary", ""),
        },
        "context_added_rules": cmp_data.get("context_added_rules", []),
        "ti_added_rules": cmp_data.get("ti_added_rules", []),
        "score_contributions": contribs,
        "counterfactual": {
            "hypothetical_change": ti.get("counterfactual_summary") or ctx.get("counterfactual_summary", ""),
            "projected_method2_score": proj_m2,
            "projected_method3_score": proj_m3,
            "explanation": cmp_data["comparison_narrative"],
        },
        "alert_reasons": alert_reasons,
        "evidence_flags": evidence_flags,
        "ground_truth": tx_enriched.get("ground_truth", 0),
    }


def get_alert_decision(
    transaction_id: str,
    method: str = "contextual_ti",
    override_threshold: Optional[int] = None,
    override_critical_bypass: Optional[int] = None,
    override_timezone: Optional[str] = None,
    override_quiet_hours_enabled: Optional[bool] = None,
    override_quiet_hours_start: Optional[str] = None,
    override_quiet_hours_end: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Call `GET /transactions/{transaction_id}/alert-decision` with optional What-If overrides."""
    params: Dict[str, Any] = {"method": method}
    if override_threshold is not None:
        params["override_threshold"] = override_threshold
    if override_critical_bypass is not None:
        params["override_critical_bypass"] = override_critical_bypass
    if override_timezone is not None:
        params["override_timezone"] = override_timezone
    if override_quiet_hours_enabled is not None:
        params["override_quiet_hours_enabled"] = override_quiet_hours_enabled
    if override_quiet_hours_start is not None:
        params["override_quiet_hours_start"] = override_quiet_hours_start
    if override_quiet_hours_end is not None:
        params["override_quiet_hours_end"] = override_quiet_hours_end

    res = _api_get(f"/transactions/{transaction_id}/alert-decision", params=params)
    if res["ok"] and isinstance(res["data"], dict):
        return res["data"]
    return None


def update_user_preferences_live(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist updated alert policy preferences for a user (`PUT /preferences/{user_id}`)."""
    res = _api_put(f"/preferences/{user_id}", payload)
    if res["ok"]:
        invalidate_dataset_cache()
    return res


def get_activity_chart_data() -> List[Dict[str, Any]]:
    """Return daily transaction activity series from SQLite."""
    dataset = _fetch_analytics_dataset_cached()
    return dataset.get("activity_chart", [])


def get_scenario_summary() -> List[Dict[str, Any]]:
    """Return the 8 scenario archetypes and their representative SQLite transaction IDs."""
    dataset = _fetch_analytics_dataset_cached()
    return dataset.get("scenarios", [])


# ---------------------------------------------------------------------------
# Forensic Evidence Timeline API
# ---------------------------------------------------------------------------

KILL_CHAIN_UI_LABELS = {
    "RECON_BRUTE_FORCE": ("Recon / Brute-Force", "Critical"),
    "INITIAL_ACCESS": ("Initial Access", "High"),
    "PREPARATION_PERSISTENCE": ("Preparation / Persistence", "High"),
    "EXFILTRATION_EXECUTION": ("Exfiltration Execution", "Critical"),
    "NORMAL_ACTIVITY": ("Normal Activity", "Low"),
}


def get_evidence_timeline(transaction_id: str) -> List[Dict[str, Any]]:
    """Call `GET /transactions/{transaction_id}/timeline` and format chronological forensic events."""
    res = _api_get(f"/transactions/{transaction_id}/timeline")
    if not res["ok"] or not isinstance(res["data"], dict):
        return []

    raw_data = res["data"]
    entries = raw_data.get("timeline", [])
    formatted: List[Dict[str, Any]] = []

    for ev in entries:
        kc_raw = ev.get("kill_chain_phase", "NORMAL_ACTIVITY")
        phase_label, default_sev = KILL_CHAIN_UI_LABELS.get(kc_raw, (kc_raw, "Medium"))
        # If normal activity on transaction execution, check if transaction had high risk
        if kc_raw == "NORMAL_ACTIVITY" and ev.get("event_category") == "transaction":
            severity = "Low"
        else:
            severity = default_sev

        entity_parts = []
        if ev.get("device_id"):
            entity_parts.append(f"Device: {ev['device_id']}")
        if ev.get("ip_address"):
            entity_parts.append(f"IP: {ev['ip_address']}")
        if ev.get("geo_location"):
            entity_parts.append(f"Geo: {ev['geo_location']}")
        entity_str = " · ".join(entity_parts) if entity_parts else raw_data.get("user_id", "—")

        formatted.append(
            {
                "sequence_no": ev.get("sequence_no"),
                "timestamp": ev.get("timestamp_utc", "").replace("T", " ").replace("Z", " UTC"),
                "event_category": ev.get("event_category", ""),
                "event_type": ev.get("event_type", "").upper(),
                "phase": phase_label,
                "kill_chain_raw": kc_raw,
                "severity": severity,
                "recorded_fact": ev.get("recorded_fact", ""),
                "system_interpretation": ev.get("system_interpretation", ""),
                "description": f"{ev.get('recorded_fact', '')} — {ev.get('system_interpretation', '')}",
                "entity": entity_str,
                "source": f"{ev.get('source_table', '')}:{ev.get('source_record_id', '')}",
            }
        )
    return formatted


def get_evidence_timeline_metadata(transaction_id: str) -> Dict[str, Any]:
    """Return full `TransactionTimelineResponseSchema` metadata (present/missing categories, kill chain phases)."""
    res = _api_get(f"/transactions/{transaction_id}/timeline")
    if res["ok"] and isinstance(res["data"], dict):
        return res["data"]
    return {}


# ---------------------------------------------------------------------------
# Threat Intelligence API
# ---------------------------------------------------------------------------

def get_threat_indicators(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Call `GET /threat-intel` from FastAPI and apply optional UI filters."""
    res = _api_get("/threat-intel")
    indicators: List[Dict[str, Any]] = res["data"] if (res["ok"] and isinstance(res["data"], list)) else []

    if not filters:
        return indicators

    confidence_levels = filters.get("confidence_levels")
    if confidence_levels:
        indicators = [i for i in indicators if i["confidence"] in confidence_levels]

    statuses = filters.get("statuses")
    if statuses:
        indicators = [i for i in indicators if i["status"] in statuses]

    indicator_types = filters.get("types")
    if indicator_types:
        indicators = [i for i in indicators if i["type"] in indicator_types]

    tx_id = filters.get("transaction_id")
    if tx_id:
        q = tx_id.strip().upper()
        indicators = [
            i for i in indicators
            if any(q in assoc_id.upper() for assoc_id in i.get("associated_tx_ids", []))
        ]

    return indicators


# ---------------------------------------------------------------------------
# Verification & Incident Register API
# ---------------------------------------------------------------------------

STATUS_UI_MAP = {
    "open": "Open",
    "investigating": "In Review",
    "closed": "Closed",
}


def get_incidents() -> List[Dict[str, Any]]:
    """Call `GET /incidents` from FastAPI and format for UI display."""
    res = _api_get("/incidents")
    if not res["ok"] or not isinstance(res["data"], list):
        return []

    out: List[Dict[str, Any]] = []
    for inc in res["data"]:
        out.append(
            {
                "incident_id": inc["incident_id"],
                "tx_id": inc["transaction_id"],
                "verification_request_id": inc.get("verification_request_id"),
                "user_id": inc["user_id"],
                "user_display_name": inc["user_display_name"],
                "user_profile_type": inc["user_profile_type"],
                "user_expenditure_model": inc["user_expenditure_model"],
                "amount": inc["amount"],
                "currency": inc["currency"],
                "beneficiary_name": inc["beneficiary_name"],
                "created_at": inc["created_at_utc"],
                "updated_at": inc["updated_at_utc"],
                "status": STATUS_UI_MAP.get(inc["status"], inc["status"].capitalize()),
                "raw_status": inc["status"],
                "severity": inc["severity"].capitalize(),
                "verification_outcome": "User Denied / Confirmed Fraud",
                "risk_score_at_creation": inc["risk_score_at_creation"],
                "scoring_method_used": inc["scoring_method_used"],
                "summary": inc["summary_reason"],
                "sha256_hash": inc["evidence_sha256"],
                "_simulated": False,
            }
        )
    return out


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """Call `GET /incidents/{incident_id}` for full detail, linked evidence, and SHA-256 verification."""
    res = _api_get(f"/incidents/{incident_id}")
    if not res["ok"] or not isinstance(res["data"], dict):
        return None

    detail = res["data"]
    inc = detail["incident"]
    integrity = detail["evidence_integrity"]
    linked_ev = detail.get("linked_evidence", [])

    canonical_snapshot = {
        "incident_id": inc["incident_id"],
        "transaction_id": inc["transaction_id"],
        "user_id": inc["user_id"],
        "user_display_name": inc["user_display_name"],
        "amount": inc["amount"],
        "currency": inc["currency"],
        "beneficiary_name": inc["beneficiary_name"],
        "risk_score_at_creation": inc["risk_score_at_creation"],
        "scoring_method_used": inc["scoring_method_used"],
        "evidence_records": [
            {
                "evidence_type": e["evidence_type"],
                "source_record_id": e["source_record_id"],
                "timestamp_utc": e["timestamp_utc"],
                "explanation": e["explanation"],
            }
            for e in linked_ev
        ],
    }

    return {
        "incident_id": inc["incident_id"],
        "tx_id": inc["transaction_id"],
        "verification_request_id": inc.get("verification_request_id"),
        "user_id": inc["user_id"],
        "user_display_name": inc["user_display_name"],
        "user_profile": detail.get("user_profile", {}),
        "created_at": inc["created_at_utc"],
        "updated_at": inc["updated_at_utc"],
        "status": STATUS_UI_MAP.get(inc["status"], inc["status"].capitalize()),
        "raw_status": inc["status"],
        "severity": inc["severity"].capitalize(),
        "verification_outcome": (
            "User Denied / Confirmed Fraud"
            if (detail.get("verification_request") or {}).get("user_response") == "denied"
            else "Escalated Forensic Incident"
        ),
        "risk_score_at_creation": inc["risk_score_at_creation"],
        "evidence_records_count": len(linked_ev),
        "linked_evidence": linked_ev,
        "recommended_actions": detail.get("recommended_actions", []),
        "summary": inc["summary_reason"],
        "canonical_snapshot": canonical_snapshot,
        "sha256_hash": inc["evidence_sha256"],
        "evidence_integrity": integrity,
        "_simulated": False,
    }


def update_incident_status_live(
    incident_id: str,
    new_status: str,
    investigator_note: str = "",
) -> Dict[str, Any]:
    """Call `PATCH /incidents/{incident_id}` to update status ('open', 'investigating', 'closed') in SQLite."""
    res = _api_patch(
        f"/incidents/{incident_id}",
        {"status": new_status, "investigator_note": investigator_note or None},
    )
    if res["ok"]:
        invalidate_dataset_cache()
    return res


def verify_transaction(transaction_id: str, outcome: str, analyst_note: str = "") -> Dict[str, Any]:
    """Execute real transaction verification workflow via FastAPI (`POST /verification-requests` + `/respond`).

    - 'confirmed_fraud' or 'escalated' -> submits user_response='denied', creating a SHA-256 incident in SQLite.
      If 'escalated', also transitions the incident status to 'investigating'.
    - 'cleared_legitimate' -> submits user_response='approved', marking the verification request 'confirmed_legitimate'.
    """
    create_res = _api_post("/verification-requests", {"transaction_id": transaction_id})
    if not create_res["ok"] or not isinstance(create_res["data"], dict):
        return {"success": False, "error": create_res.get("error", "Failed to create verification request.")}

    ver_req = create_res["data"]
    req_id = ver_req["request_id"]

    user_resp_val = "approved" if outcome == "cleared_legitimate" else "denied"
    default_note = (
        "Cleared as legitimate authorized activity after contextual review."
        if user_resp_val == "approved"
        else "Confirmed suspicious / unauthorized activity; escalated to Incident Register."
    )

    resp_res = _api_post(
        f"/verification-requests/{req_id}/respond",
        {
            "user_response": user_resp_val,
            "response_notes": analyst_note.strip() or default_note,
        },
    )
    if not resp_res["ok"] or not isinstance(resp_res["data"], dict):
        return {"success": False, "error": resp_res.get("error", "Failed to record verification response.")}

    ver_done = resp_res["data"]
    invalidate_dataset_cache()

    linked_inc_id = ver_done.get("linked_incident_id")
    if linked_inc_id:
        if outcome == "escalated":
            update_incident_status_live(
                incident_id=linked_inc_id,
                new_status="investigating",
                investigator_note=analyst_note.strip() or "Escalated for deep forensic investigation.",
            )
        inc_detail = get_incident(linked_inc_id)
        return {"success": True, "verification": ver_done, "incident": inc_detail}

    return {"success": True, "verification": ver_done, "incident": None}


# ---------------------------------------------------------------------------
# Stage 10 Evaluation Metrics API
# ---------------------------------------------------------------------------

def get_evaluation_metrics(
    threshold: int = 60,
    use_user_preferences_threshold: bool = False,
) -> Dict[str, Any]:
    """Call `GET /evaluation/metrics` from FastAPI and format for the Evaluation Dashboard."""
    res = _api_get(
        "/evaluation/metrics",
        params={
            "threshold": threshold,
            "use_user_preferences_threshold": use_user_preferences_threshold,
        },
    )
    if not res["ok"] or not isinstance(res["data"], dict):
        return {}

    raw = res["data"]
    mc = raw["methods_comparison"]

    def _fmt_method(m_key: str, label: str) -> Dict[str, Any]:
        m = mc[m_key]
        cm = m["confusion_matrix"]
        return {
            "method_name": label,
            "threshold": raw["threshold_evaluated"],
            "tp": cm["true_positives"],
            "fp": cm["false_positives"],
            "tn": cm["true_negatives"],
            "fn": cm["false_negatives"],
            "precision": m["precision"],
            "recall": m["recall"],
            "f1_score": m["f1_score"],
            "false_positive_rate": m["false_positive_rate"],
            "total_alerts": m["flagged_count"],
            "flagged_percentage": m["flagged_percentage"],
            "total_transactions": m["total_transactions"],
            "ato_detection_rate": m["ato_scenario_detection_rate"],
            "bec_detection_rate": m["bec_scenario_detection_rate"],
            "structuring_detection_rate": m["structuring_scenario_detection_rate"],
            "capex_fpr": m["capex_false_positive_rate"],
        }

    # Build scenario detection rates dict
    scenario_rates: Dict[str, Any] = {}
    for idx, item in enumerate(raw.get("per_scenario_breakdown", []), start=1):
        scen_label = item["scenario_label"]
        is_atk = item["ground_truth_class"] == "suspicious" or item["suspicious_cases"] > 0
        scenario_rates[f"SCEN-{idx:02d}"] = {
            "scenario_label": scen_label,
            "scenario_name": scen_label.replace("_", " ").title(),
            "type": "Attack" if is_atk else "Legitimate",
            "total": item["total_cases"],
            "baseline_rate": item["baseline_flagged_rate"],
            "detected_contextual": item["contextual_flagged_count"],
            "detection_rate": item["contextual_flagged_rate"],
            "ti_rate": item["contextual_ti_flagged_rate"],
        }

    # Build threshold sweep list across all 3 methods
    sweep_by_thr: Dict[int, Dict[str, Any]] = {}
    for pt in raw.get("threshold_tradeoff_curve", []):
        thr = pt["threshold"]
        entry = sweep_by_thr.setdefault(thr, {"threshold": thr})
        m = pt["method"]
        if m == "baseline":
            entry["alerts_method1"] = pt["flagged_count"]
            entry["recall_method1"] = pt["recall"]
            entry["f1_method1"] = pt["f1_score"]
        elif m == "contextual":
            entry["alerts"] = pt["flagged_count"]
            entry["recall_method2"] = pt["recall"]
            entry["f1_method2"] = pt["f1_score"]
        elif m == "contextual_ti":
            entry["alerts_method3"] = pt["flagged_count"]
            entry["recall_method3"] = pt["recall"]
            entry["f1_method3"] = pt["f1_score"]

    return {
        "method1": _fmt_method("baseline", "M1: Transaction-Only Baseline"),
        "method2": _fmt_method("contextual", "M2: Contextual Forensic Scoring"),
        "method3": _fmt_method("contextual_ti", "M3: Contextual + Threat Intelligence"),
        "scenario_detection_rates": scenario_rates,
        "per_expenditure_model_breakdown": raw.get("per_expenditure_model_breakdown", []),
        "threshold_sweep": [sweep_by_thr[k] for k in sorted(sweep_by_thr.keys())],
        "positive_class_definition": raw.get("positive_prediction_definition", ""),
        "note": raw.get("evaluation_disclaimer", ""),
    }


# ---------------------------------------------------------------------------
# Live Demo Studio API (Create User, Beneficiary, Transaction, Rules Catalog)
# ---------------------------------------------------------------------------

def get_users_list() -> List[Dict[str, Any]]:
    """Call `GET /users` to list all synthetic and custom user profiles."""
    res = _api_get("/users")
    if res["ok"] and isinstance(res["data"], list):
        return res["data"]
    return []


def create_user_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call `POST /users` to create a new custom user profile in SQLite."""
    res = _api_post("/users", payload)
    if res["ok"]:
        invalidate_dataset_cache()
    return res


def get_user_beneficiaries_list(user_id: str) -> List[Dict[str, Any]]:
    """Call `GET /users/{user_id}/beneficiaries` to list a user's beneficiaries."""
    res = _api_get(f"/users/{user_id}/beneficiaries")
    if res["ok"] and isinstance(res["data"], list):
        return res["data"]
    return []


def create_beneficiary_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call `POST /beneficiaries` to add or update a beneficiary (or simulate Vendor BEC bank change)."""
    res = _api_post("/beneficiaries", payload)
    if res["ok"]:
        invalidate_dataset_cache()
    return res


def create_transaction_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call `POST /transactions` to submit a live transaction and immediately evaluate 3-method risk."""
    res = _api_post("/transactions", payload)
    if res["ok"]:
        invalidate_dataset_cache()
    return res


def get_rules_catalog() -> List[Dict[str, Any]]:
    """Call `GET /risk/rules` to fetch the documented rule catalog."""
    res = _api_get("/risk/rules")
    if res["ok"] and isinstance(res["data"], list):
        return res["data"]
    return []
