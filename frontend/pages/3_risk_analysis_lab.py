"""
PAGE 3 — Risk Analysis Lab
Core research demonstration: side-by-side comparison of 3 scoring methods, rule matrix,
counterfactual analysis, and live What-If Alert Policy Simulator connected to FastAPI.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_alert_decision,
    get_risk_scores,
    get_scenario_summary,
    get_session_detail_live,
    get_transaction,
    get_transactions,
    get_user_sessions,
    get_verification_requests_live,
    submit_admin_transaction_decision_live,
    update_user_preferences_live,
)
from ui.components import (
    RISK_COLOR_MAP,
    build_score_comparison_chart,
    build_waterfall_chart,
    fmt_currency,
    fmt_ts,
    inject_css,
    render_demo_banner,
    render_financial_calibration_card,
    render_score_card,
    status_badge_html,
)

inject_css()
render_demo_banner()

st.markdown("<h1>Risk Analysis Lab (3-Method Comparison)</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Compare three deterministic heuristic scoring methods on the exact same transaction: '
    '<b>M1 (Transaction-Only Baseline)</b>, <b>M2 (Contextual Forensic Scoring)</b>, and '
    '<b>M3 (Contextual + Threat Intelligence)</b>. Inspect rule-level provenance, counterfactual explanations, '
    'and test the timezone-aware Alert Policy Simulator.</p>',
    unsafe_allow_html=True,
)

st.divider()

# ── Synchronized Scenario Preset & Transaction Selector ───────────────────
scenarios = get_scenario_summary()
all_txs = get_transactions()
all_tx_ids = [t["id"] for t in all_txs]

pending_or_held_txs = [
    t for t in all_txs
    if t.get("raw_status") in ("PENDING_VERIFICATION", "HELD_HIGH_RISK")
    or t.get("status") in ("Pending Review", "Flagged")
]

if pending_or_held_txs:
    with st.expander(
        f"🚨 Pending / Held Transfers Awaiting Admin Investigation & Release ({len(pending_or_held_txs)})",
        expanded=True,
    ):
        st.caption(
            "Select any pending or held transfer below to load its 3-method forensic breakdown, "
            "inspect the customer's login session & network context, and complete or block the transfer."
        )
        q_cols = st.columns([3.5, 1.5])
        with q_cols[0]:
            queue_tx_id = st.selectbox(
                "Pending / Held Transfer Queue",
                options=[t["id"] for t in pending_or_held_txs],
                format_func=lambda tid: (
                    f"{tid} · {get_transaction(tid)['sender_name']} → {get_transaction(tid)['beneficiary_name']} · "
                    f"{fmt_currency(get_transaction(tid)['amount'])} · "
                    f"[{get_transaction(tid).get('raw_status', get_transaction(tid)['status'])}] "
                    f"(M3={get_transaction(tid)['method3_score']}/100)"
                ),
                key="risk_lab_pending_queue_select",
            )
        with q_cols[1]:
            st.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
            if st.button("🔍 Load into Lab", use_container_width=True, key="btn_load_pending_into_lab"):
                st.session_state["selected_tx_id"] = queue_tx_id
                st.session_state["risk_custom_tx_selector"] = queue_tx_id
                st.rerun()

preset_map = {
    f"{s['id']} — {s['name']} ({s['type']}) [{s['tx_id']}]": s["tx_id"]
    for s in scenarios
}

scol1, scol2 = st.columns([2.2, 2.8], gap="large")

with scol1:
    preset_options = ["-- Custom / Current Selection --"] + list(preset_map.keys())

    def _on_preset_change() -> None:
        chosen_label = st.session_state.get("risk_preset_selector")
        if chosen_label and chosen_label in preset_map:
            st.session_state["selected_tx_id"] = preset_map[chosen_label]
            st.session_state["risk_custom_tx_selector"] = preset_map[chosen_label]

    st.selectbox(
        "1. Load a Representative Scenario Archetype",
        options=preset_options,
        index=0,
        key="risk_preset_selector",
        on_change=_on_preset_change,
    )

with scol2:
    current_tx_id = st.session_state.get("selected_tx_id", all_tx_ids[0] if all_tx_ids else "TX-0391")
    if current_tx_id not in all_tx_ids and all_tx_ids:
        current_tx_id = all_tx_ids[0]
    default_idx = all_tx_ids.index(current_tx_id) if current_tx_id in all_tx_ids else 0

    def _on_tx_change() -> None:
        st.session_state["selected_tx_id"] = st.session_state["risk_custom_tx_selector"]

    selected_tx_id = st.selectbox(
        "2. Or Select Any Transaction (⚡ Live-Created Shown First, Then Historical Ledger)",
        options=all_tx_ids,
        index=default_idx,
        format_func=lambda tid: (
            f"{'⚡ LIVE CREATED · ' if get_transaction(tid).get('is_live_created') else ''}"
            f"{tid} · {get_transaction(tid)['sender_name'][:20]} → "
            f"{get_transaction(tid)['beneficiary_name'][:18]} · "
            f"{fmt_currency(get_transaction(tid)['amount'])} "
            f"[M1={get_transaction(tid)['method1_score']} | M2={get_transaction(tid)['method2_score']} | M3={get_transaction(tid)['method3_score']}]"
        ),
        key="risk_custom_tx_selector",
        on_change=_on_tx_change,
    )

st.session_state["selected_tx_id"] = selected_tx_id

tx = get_transaction(selected_tx_id)
scores = get_risk_scores(selected_tx_id)

if not tx or not scores:
    st.error(f"Transaction '{selected_tx_id}' not found.")
    st.stop()

st.divider()

# ── Transaction Summary Banner & Financial Profile Calibration ─────────────
st.markdown(
    f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;
padding:14px 20px;margin-bottom:14px;display:flex;gap:24px;flex-wrap:wrap;align-items:center;justify-content:space-between">
  <div>
    <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.07em">Transaction ID</div>
    <div style="font-size:1.0rem;font-weight:700;color:#21D4C2;font-family:'JetBrains Mono',monospace">{tx["id"]}</div>
  </div>
  <div>
    <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Scenario Archetype</div>
    <div style="font-size:0.84rem;color:#E2E8F0;font-family:'JetBrains Mono',monospace">{tx.get("scenario_label","—")}</div>
  </div>
  <div>
    <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Amount</div>
    <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9;font-family:'JetBrains Mono',monospace">{fmt_currency(tx["amount"])}</div>
  </div>
  <div>
    <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Timestamp (UTC)</div>
    <div style="font-size:0.82rem;color:#CBD5E1;font-family:'JetBrains Mono',monospace">{fmt_ts(tx["timestamp"])}</div>
  </div>
  <div>
    <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Origin IP / Geo</div>
    <div style="font-size:0.82rem;color:#CBD5E1;font-family:'JetBrains Mono',monospace">{tx.get("ip_address","—")} ({tx.get("geo_location","—")})</div>
  </div>
  <div>
    <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Evaluation Ground Truth</div>
    <div style="font-size:0.88rem;font-weight:700;color:{'#EF4444' if tx.get('ground_truth')==1 else '#10B981'}">
      {'⚠ SUSPICIOUS / ATTACK' if tx.get('ground_truth')==1 else '✓ LEGITIMATE'}
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

render_financial_calibration_card(tx)

# ── Session & Network Intelligence Inspector + Admin Release Panel ────────
raw_tx_status = tx.get("raw_status") or tx.get("status", "COMPLETED")
tx_session_id = tx.get("session_id")
sess_detail = get_session_detail_live(tx_session_id) if tx_session_id else None
if not sess_detail:
    recent_user_sessions = get_user_sessions(user_id=tx["sender_id"], limit=1)
    if recent_user_sessions:
        sess_detail = recent_user_sessions[0]

ver_list_for_tx = [
    v for v in get_verification_requests_live(user_id=tx["sender_id"])
    if v.get("transaction_id") == selected_tx_id
]
ver_rec = ver_list_for_tx[0] if ver_list_for_tx else None

intel_col, release_col = st.columns([1.35, 1.15], gap="large")

with intel_col:
    st.markdown(
        '<div class="panel-header">SESSION &amp; NETWORK INTELLIGENCE (OBSERVED · CONTEXT · INFERRED)</div>',
        unsafe_allow_html=True,
    )
    if sess_detail:
        obs = sess_detail.get("observed_evidence") or {}
        sim = sess_detail.get("simulated_input") or {}
        inf = sess_detail.get("inferred_context") or {}
        st.markdown(
            f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:14px 18px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <span style="font-size:0.76rem;color:#21D4C2;font-weight:700;font-family:monospace">
      Session {sess_detail.get("session_id","—")} · User {sess_detail.get("user_id","—")}
    </span>
    <span style="font-size:0.71rem;color:#94A3B8">{fmt_ts(sess_detail.get("created_at_utc",""))}</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-size:0.76rem">
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 10px">
      <div style="color:#67E8F9;font-weight:700;font-size:0.65rem;text-transform:uppercase;margin-bottom:4px">1. Observed Telemetry</div>
      <div>Failed Logins (1h): <b>{obs.get("failed_logins_1h", sess_detail.get("failed_logins_1h", 0))}</b></div>
      <div>Active Session: <b>{"Yes" if obs.get("is_active", True) else "Revoked"}</b></div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 10px">
      <div style="color:#FDE68A;font-weight:700;font-size:0.65rem;text-transform:uppercase;margin-bottom:4px">2. Network Context</div>
      <div>IP: <code>{sim.get("ip_address", sess_detail.get("ip_address","—"))}</code></div>
      <div>Network: <code>{sim.get("network_type", sess_detail.get("network_type","—"))}</code></div>
      <div>Device: <code>{sim.get("device_id", sess_detail.get("device_id","—"))}</code></div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 10px">
      <div style="color:#A78BFA;font-weight:700;font-size:0.65rem;text-transform:uppercase;margin-bottom:4px">3. Inferred Context</div>
      <div>Geo: <b>{inf.get("geo_location", sess_detail.get("geo_location","—"))}</b> (Home: {inf.get("home_geo_location", tx.get("sender_home_geo","—"))})</div>
      <div>Known IP/Device: <b>{"Yes" if inf.get("is_known_ip") else "No"}</b> / <b>{"Yes" if inf.get("is_known_device") else "No"}</b></div>
      <div>Threat Intel Match: <b style="color:{'#EF4444' if inf.get('active_threat_intel_match') else '#10B981'}">{"ACTIVE MATCH" if inf.get("active_threat_intel_match") else "Clean"}</b></div>
    </div>
  </div>
  <div style="font-size:0.74rem;color:#CBD5E1;margin-top:8px;padding-top:6px;border-top:1px solid #1E2D3B">
    <b>Context Summary:</b> {inf.get("context_summary","Session telemetry correlated with baseline profile.")}
  </div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:14px 18px;font-size:0.78rem;color:#CBD5E1">
  <div><b>Transaction Network Telemetry:</b> Origin IP <code>{tx.get("ip_address","—")}</code> ({tx.get("geo_location","—")}) · Device <code>{tx.get("device_id","—")}</code></div>
  <div style="margin-top:4px;color:#8A9CB0">Customer Home Location Baseline: <b>{tx.get("sender_home_geo","—")}</b> · Policy Status: <code>{raw_tx_status}</code></div>
</div>""",
            unsafe_allow_html=True,
        )

with release_col:
    st.markdown(
        '<div class="panel-header">ADMIN INVESTIGATION &amp; TRANSFER RELEASE</div>',
        unsafe_allow_html=True,
    )
    bal_deducted_flag = bool(tx.get("balance_deducted", True))
    ver_status_str = ver_rec.get("status", "none") if ver_rec else "none"
    user_resp_str = ver_rec.get("user_response") or "Not yet responded" if ver_rec else "No verification request"

    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:12px 16px;margin-bottom:8px;font-size:0.78rem">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span>Transfer Lifecycle Status: {status_badge_html(raw_tx_status)}</span>
    <span style="color:#94A3B8">Balance Deducted: <b>{"Yes" if bal_deducted_flag else "No (On Hold)"}</b></span>
  </div>
  <div style="color:#CBD5E1">Customer Verification Status: <code>{ver_status_str}</code> (Customer Response: <b>{user_resp_str}</b>)</div>
  <div style="color:#8A9CB0;font-size:0.73rem;margin-top:4px">{tx.get("decision_reason","")}</div>
</div>""",
        unsafe_allow_html=True,
    )

    admin_note_input = st.text_input(
        "Admin Investigation & Owner Confirmation Note",
        value="Investigated 3-method risk & session context in Lab; confirmed transfer intent with account owner.",
        key=f"admin_lab_note_{selected_tx_id}",
    )
    ac1, ac2 = st.columns(2)
    with ac1:
        if st.button(
            "✅ Complete Transfer",
            key=f"btn_admin_approve_{selected_tx_id}",
            use_container_width=True,
            disabled=(raw_tx_status == "BLOCKED"),
        ):
            res = submit_admin_transaction_decision_live(selected_tx_id, "approve", admin_note_input)
            if res["ok"]:
                st.success(
                    f"Transfer `{selected_tx_id}` released and marked COMPLETED. Balance updated."
                )
                st.rerun()
            else:
                st.error(res.get("error", "Could not approve transaction."))
    with ac2:
        if st.button(
            "🛑 Block & Escalate",
            key=f"btn_admin_block_{selected_tx_id}",
            type="primary",
            use_container_width=True,
        ):
            res = submit_admin_transaction_decision_live(selected_tx_id, "block", admin_note_input)
            if res["ok"]:
                inc_id = (res.get("data") or {}).get("linked_incident_id")
                st.warning(
                    f"Transfer `{selected_tx_id}` BLOCKED (balance untouched). "
                    f"Forensic Incident `{inc_id}` created."
                )
                st.rerun()
            else:
                st.error(res.get("error", "Could not block transaction."))

st.divider()

# ── Score Cards (side-by-side) ────────────────────────────────────────────
st.markdown(
    '<div class="panel-header">SIDE-BY-SIDE MODEL SCORE COMPARISON (0–100 HEURISTIC SCALE)</div>',
    unsafe_allow_html=True,
)

sc1, sc2, sc3 = st.columns(3, gap="medium")
with sc1:
    render_score_card(
        "Method 1 · Transaction-Only Baseline",
        scores["method1"]["score"],
        scores["method1"]["level"],
        scores["method1"]["description"],
    )
with sc2:
    render_score_card(
        "Method 2 · Contextual Forensic Scoring",
        scores["method2"]["score"],
        scores["method2"]["level"],
        scores["method2"]["description"],
    )
with sc3:
    render_score_card(
        "Method 3 · Contextual + Threat Intel",
        scores["method3"]["score"],
        scores["method3"]["level"],
        scores["method3"]["description"],
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Comparative Narrative Box ─────────────────────────────────────────────
m1s = scores["method1"]["score"]
m2s = scores["method2"]["score"]
m3s = scores["method3"]["score"]
delta_ctx = scores.get("delta_contextual_vs_baseline", m2s - m1s)
delta_ti = scores.get("delta_ti_vs_contextual", m3s - m2s)

st.markdown(
    f"""
<div style="background:#0B1929;border:1px solid #1E3A5F;border-left:4px solid #21D4C2;
border-radius:8px;padding:12px 18px;margin-bottom:16px;font-size:0.83rem;color:#E2E8F0;line-height:1.5">
  <b>Comparative Engine Narrative:</b> {scores.get("comparison_narrative","")}
  <span style="margin-left:12px;font-family:monospace;color:#67E8F9">
    [Δ Contextual vs Baseline: {delta_ctx:+d} pts &nbsp;|&nbsp; Δ Threat Intel vs Contextual: {delta_ti:+d} pts]
  </span>
</div>
""",
    unsafe_allow_html=True,
)

# ── Side-by-side comparison chart + waterfall ─────────────────────────────
chart_col, waterfall_col = st.columns([1.4, 2.0], gap="large")

with chart_col:
    fig_cmp = build_score_comparison_chart(scores, threshold=tx.get("user_alert_threshold", 60))
    st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

with waterfall_col:
    contribs = scores.get("score_contributions", {})
    if contribs:
        fig_wf = build_waterfall_chart(contribs)
        st.plotly_chart(fig_wf, use_container_width=True, config={"displayModeBar": False})
    else:
        st.success("Zero anomaly points triggered across all 3 methods (0/100).")

st.divider()

# ── Rule-by-Rule Trigger Matrix (M1 vs M2 vs M3) ──────────────────────────
st.markdown(
    '<div class="panel-header">EXPLAINABLE RULE TRIGGER MATRIX &amp; EVIDENCE PROVENANCE</div>',
    unsafe_allow_html=True,
)

rtab1, rtab2, rtab3 = st.tabs(
    [
        f"M3: Contextual + TI ({len(scores['method3']['triggered_rules'])} rules)",
        f"M2: Contextual Forensic ({len(scores['method2']['triggered_rules'])} rules)",
        f"M1: Transaction-Only Baseline ({len(scores['method1']['triggered_rules'])} rules)",
    ]
)

for tab_obj, method_key in [(rtab1, "method3"), (rtab2, "method2"), (rtab3, "method1")]:
    with tab_obj:
        rules_list = scores[method_key].get("triggered_rules", [])
        if not rules_list:
            st.markdown(
                '<div style="padding:14px;background:#07291B;border:1px solid #10B98155;border-radius:7px;'
                'color:#6EE7B7;font-size:0.82rem">✓ No anomaly rules fired in this scoring tier (Score = 0/100).</div>',
                unsafe_allow_html=True,
            )
        else:
            r_rows = ""
            for r in rules_list:
                pts = r["points_awarded"]
                max_pts = r["max_points"]
                pt_col = "#EF4444" if pts >= 25 else ("#F59E0B" if pts > 0 else "#94A3B8")
                refs = ", ".join(r.get("evidence_refs", [])) or "transactions"
                r_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#21D4C2;font-weight:600">{r['rule_id']}</td>
  <td style="padding:8px 10px;font-size:0.79rem;color:#F1F5F9;font-weight:600">{r['rule_name']}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#94A3B8;font-family:monospace">{r['category']}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{pt_col};font-family:monospace">+{pts} / {max_pts}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#CBD5E1;line-height:1.4">{r['explanation']}</td>
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.71rem;color:#67E8F9">{refs}</td>
</tr>"""
            st.markdown(
                f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Rule ID</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Rule Name</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Category</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Points</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Forensic Explanation</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Evidence Provenance Refs</th>
    </tr>
  </thead>
  <tbody>{r_rows}</tbody>
</table>
</div>
""",
                unsafe_allow_html=True,
            )

st.divider()

# ── Counterfactual Explanation ─────────────────────────────────────────────
cf = scores.get("counterfactual", {})
if cf:
    st.markdown(
        '<div class="panel-header">COUNTERFACTUAL EXPLANATION ("WHAT WOULD LOWER THIS SCORE?")</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div style="background:#0D1522;border:1px solid #223342;border-left:4px solid #8B5CF6;
border-radius:8px;padding:16px 20px">
  <div style="font-size:0.72rem;color:#A78BFA;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:8px">
    Actionable Counterfactual Analysis
  </div>
  <div style="font-size:0.86rem;color:#F1F5F9;margin-bottom:12px;line-height:1.5">{cf.get("hypothetical_change","")}</div>
  <div style="display:flex;gap:18px;flex-wrap:wrap">
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:10px 16px;text-align:center">
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;margin-bottom:4px">Actual M2 Score</div>
      <div style="font-size:1.35rem;font-weight:700;color:{'#EF4444' if m2s>=60 else '#10B981'}">{m2s}/100</div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:10px 16px;text-align:center">
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;margin-bottom:4px">Projected Counterfactual M2</div>
      <div style="font-size:1.35rem;font-weight:700;color:#A78BFA">{cf.get("projected_method2_score","—")}/100</div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:10px 16px;text-align:center">
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;margin-bottom:4px">Projected Counterfactual M3</div>
      <div style="font-size:1.35rem;font-weight:700;color:#A78BFA">{cf.get("projected_method3_score","—")}/100</div>
    </div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

st.divider()

# ── Live Alert Policy Simulator (`GET /transactions/{id}/alert-decision`) ─
st.markdown(
    '<div class="panel-header">ALERT POLICY &amp; QUIET-HOURS SIMULATOR</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.8rem;margin-bottom:14px">'
    'Evaluates <code>GET /transactions/{id}/alert-decision</code> using IANA timezone conversion and overnight quiet-hour windows. '
    'Notice that changing alert delivery preferences <b>never alters the underlying forensic risk score</b>.</p>',
    unsafe_allow_html=True,
)

stored_decision = get_alert_decision(selected_tx_id, method="contextual_ti")
stored_prefs = (stored_decision or {}).get("applied_preferences", {})

apc1, apc2, apc3 = st.columns(3, gap="large")
with apc1:
    sim_method = st.selectbox(
        "Scoring Method to Gate",
        options=["contextual_ti", "contextual", "baseline"],
        format_func=lambda m: {
            "contextual_ti": "M3: Contextual + Threat Intel",
            "contextual": "M2: Contextual Forensic",
            "baseline": "M1: Transaction-Only Baseline",
        }[m],
        index=0,
        key="ap_method",
    )
    sim_threshold = st.slider(
        "User Alert Threshold (10–95)",
        min_value=10,
        max_value=95,
        value=int(stored_prefs.get("risk_threshold", 60)),
        step=5,
        key="ap_threshold",
    )
    sim_bypass = st.slider(
        "Critical Bypass Threshold (50–100)",
        min_value=50,
        max_value=100,
        value=int(stored_prefs.get("critical_bypass_threshold", 85)),
        step=5,
        key="ap_bypass",
    )

with apc2:
    hours_list = [f"{h:02d}:00" for h in range(24)] + [f"{h:02d}:30" for h in range(24)]
    hours_list = sorted(hours_list)
    default_q_start = stored_prefs.get("quiet_hours_start", "22:00")
    default_q_end = stored_prefs.get("quiet_hours_end", "07:00")

    sim_quiet_enabled = st.checkbox(
        "Enable Quiet Hours Window",
        value=bool(stored_prefs.get("quiet_hours_enabled", True)),
        key="ap_q_enabled",
    )
    sim_quiet_start = st.selectbox(
        "Quiet Hours Start (Local Time)",
        options=hours_list,
        index=hours_list.index(default_q_start) if default_q_start in hours_list else 44,
        key="ap_quiet_start",
    )
    sim_quiet_end = st.selectbox(
        "Quiet Hours End (Local Time)",
        options=hours_list,
        index=hours_list.index(default_q_end) if default_q_end in hours_list else 14,
        key="ap_quiet_end",
    )

with apc3:
    tz_options = [
        "Asia/Kolkata",
        "Asia/Singapore",
        "Asia/Dubai",
        "Europe/London",
        "America/New_York",
        "America/Los_Angeles",
        "UTC",
    ]
    default_tz = stored_prefs.get("timezone_iana", "Asia/Kolkata")
    if default_tz not in tz_options:
        tz_options.insert(0, default_tz)

    sim_tz = st.selectbox(
        "User IANA Timezone",
        options=tz_options,
        index=tz_options.index(default_tz),
        key="ap_tz",
    )
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("💾 Save Alert Policy Preferences", use_container_width=True, key="save_prefs_btn"):
        save_res = update_user_preferences_live(
            tx["sender_id"],
            {
                "risk_threshold": sim_threshold,
                "critical_bypass_threshold": sim_bypass,
                "timezone_iana": sim_tz,
                "quiet_hours_enabled": sim_quiet_enabled,
                "quiet_hours_start": sim_quiet_start,
                "quiet_hours_end": sim_quiet_end,
            },
        )
        if save_res["ok"]:
            st.success(f"Saved updated alert preferences for {tx['sender_id']}!")
        else:
            st.error(save_res.get("error", "Failed to save preferences."))

live_decision = get_alert_decision(
    transaction_id=selected_tx_id,
    method=sim_method,
    override_threshold=sim_threshold,
    override_critical_bypass=sim_bypass,
    override_timezone=sim_tz,
    override_quiet_hours_enabled=sim_quiet_enabled,
    override_quiet_hours_start=sim_quiet_start,
    override_quiet_hours_end=sim_quiet_end,
)

if live_decision:
    dec_code = live_decision["alert_decision"]
    dec_colors = {
        "NO_ALERT_BELOW_THRESHOLD": ("#10B981", "✅ NO ALERT (BELOW THRESHOLD)"),
        "QUEUED_FOR_QUIET_HOURS": ("#F59E0B", "🌙 QUEUED FOR QUIET HOURS DIGEST"),
        "ALERT_NOW": ("#EF4444", "🚨 ALERT NOW (IMMEDIATE DISPATCH)"),
        "ALERT_NOW_CRITICAL_BYPASS": ("#DC2626", "🔥 CRITICAL BYPASS — IMMEDIATE ALERT DURING QUIET HOURS"),
    }
    d_col, d_title = dec_colors.get(dec_code, ("#21D4C2", dec_code))

    st.markdown(
        f"""
<div style="padding:14px 20px;background:{d_col}14;border:1px solid {d_col}55;border-left:4px solid {d_col};
border-radius:8px;margin-top:10px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px">
    <span style="font-size:0.9rem;font-weight:700;color:{d_col}">{d_title}</span>
    <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#CBD5E1">
      Local Tx Time: <b>{live_decision["transaction_local_time"]}</b> &nbsp;|&nbsp;
      Quiet Hours Active: <b>{"Yes" if live_decision["within_quiet_hours"] else "No"}</b> &nbsp;|&nbsp;
      Forensic Score: <b>{live_decision["risk_score"]}/100 (Invariant)</b>
    </span>
  </div>
  <div style="font-size:0.82rem;color:#E2E8F0;line-height:1.45">{live_decision["decision_explanation"]}</div>
  <div style="font-size:0.71rem;color:#94A3B8;margin-top:6px;font-style:italic">{live_decision["policy_disclaimer"]}</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
nav_col1, nav_col2 = st.columns([1.6, 4])
with nav_col1:
    if st.button("🔬 Open Forensic Investigation Timeline →", use_container_width=True, key="risk_to_forensic"):
        st.switch_page("pages/4_forensic_investigation.py")
