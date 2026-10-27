"""
PAGE 1 — Overview Dashboard
Executive landing page displaying live SQLite KPIs, risk distribution, high-risk alert queue, and scenario archetypes.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_activity_chart_data,
    get_dashboard_metrics,
    get_scenario_summary,
    get_transactions,
)
from ui.components import (
    RISK_COLOR_MAP,
    build_activity_chart,
    build_risk_distribution_chart,
    expenditure_badge_html,
    fmt_currency,
    fmt_ts,
    inject_css,
    render_demo_banner,
    render_kpi_row,
    render_scenario_card,
    risk_badge_html,
    status_badge_html,
)

inject_css()
render_demo_banner()

# Load live data from FastAPI + SQLite
metrics = get_dashboard_metrics()
all_txs = get_transactions()
chart_data = get_activity_chart_data()
scenarios = get_scenario_summary()

# ── Page Header ───────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([3, 1.3])
with hdr_left:
    st.markdown(
        """
<div style="margin-bottom:4px">
  <h1 style="margin:0;font-size:1.75rem;font-weight:700;color:#F1F5F9">
    TRACE-Fin Executive SOC Overview
  </h1>
  <p style="margin:5px 0 0;color:#8A9CB0;font-size:0.86rem;max-width:820px;line-height:1.45">
    Evidence-aware financial transaction verification and incident response.
    Correlating transaction telemetry with OpEx/CapEx economic profiles, counterparty supply-chain affinity,
    authentication &amp; device forensics, and freshness-validated threat intelligence.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )
with hdr_right:
    st.markdown(
        f'<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:10px 14px;text-align:right">'
        f'<div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.06em">Active Dataset Window</div>'
        f'<div style="font-size:0.82rem;font-weight:600;color:#21D4C2;font-family:monospace">{metrics["reporting_period"]}</div>'
        f'<div style="font-size:0.68rem;color:#94A3B8;margin-top:2px">Users Profiled: <b>{metrics.get("total_users", 12)}</b> · Engine: <b>{metrics["snapshot_time"]}</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── A: KPI Cards ──────────────────────────────────────────────────────────
render_kpi_row(
    [
        {
            "label": "Account Ledger Records",
            "value": f'{metrics["total_transactions"]:,}',
            "color": "#21D4C2",
            "delta": f'{metrics.get("live_created_count", 0)} created live · {metrics.get("historical_baseline_count", 500)} historical baseline',
        },
        {
            "label": "High / Critical Risk",
            "value": f'{metrics["high_risk_count"]:,}',
            "color": "#EF4444",
            "delta": f'{metrics["alert_rate_pct"]}% contextual alert rate',
            "delta_positive": False,
        },
        {
            "label": "Active Open Incidents",
            "value": str(metrics["open_incidents"]),
            "color": "#DC2626",
            "delta": "SHA-256 tamper-evident snapshots",
        },
        {
            "label": "Pending Triage / Review",
            "value": f'{metrics["needs_review_count"]:,}',
            "color": "#F59E0B",
            "delta": f'{metrics["critical_risk_count"]} critical priority (≥85)',
            "delta_positive": False,
        },
        {
            "label": "Avg M2 Contextual Score",
            "value": f'{metrics["avg_method2_score"]}',
            "color": "#8B5CF6",
            "delta": f'M1 Baseline: {metrics["avg_method1_score"]} · M3 +TI: {metrics["avg_method3_score"]}',
        },
    ]
)

st.markdown("<br>", unsafe_allow_html=True)

# ── B+D: Activity Chart + Risk Distribution ───────────────────────────────
col_act, col_dist = st.columns([2.1, 1.3], gap="large")

with col_act:
    st.markdown('<div class="panel-header">DAILY TRANSACTION TELEMETRY (LIVE SQLITE)</div>', unsafe_allow_html=True)
    fig_act = build_activity_chart(chart_data)
    st.plotly_chart(fig_act, use_container_width=True, config={"displayModeBar": False})

with col_dist:
    st.markdown('<div class="panel-header">RISK BAND DISTRIBUTION (M2 CONTEXTUAL)</div>', unsafe_allow_html=True)
    fig_dist = build_risk_distribution_chart(all_txs)
    st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── C: Priority High-Risk Alerts Queue ────────────────────────────────────
st.markdown('<div class="panel-header">PRIORITY HIGH-RISK ALERT QUEUE (TOP 12)</div>', unsafe_allow_html=True)

high_risk_txs = sorted(
    [t for t in all_txs if t.get("is_live_created") or t["method3_score"] >= 60 or t["method2_score"] >= 60],
    key=lambda t: (1 if t.get("is_live_created") else 0, t["method3_score"], t["method2_score"]),
    reverse=True,
)[:12]

if high_risk_txs:
    html_rows = ""
    for tx in high_risk_txs:
        level = tx["method3_level"]
        badge = risk_badge_html(level)
        status_b = status_badge_html(tx["status"])
        exp_b = expenditure_badge_html(tx.get("sender_expenditure_model", "personal_consumption"))
        m1_col = RISK_COLOR_MAP.get(tx["method1_level"], "#8A9CB0")
        m2_col = RISK_COLOR_MAP.get(tx["method2_level"], "#8A9CB0")
        m3_col = RISK_COLOR_MAP.get(tx["method3_level"], "#8A9CB0")
        reason_str = tx.get("alert_reasons", [""])[0]
        short_reason = reason_str[:72] + ("…" if len(reason_str) > 72 else "")

        html_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.77rem;color:#21D4C2;font-weight:600">{tx['id']}</td>
  <td style="padding:8px 10px;font-size:0.74rem;color:#8A9CB0;font-family:'JetBrains Mono',monospace">{fmt_ts(tx['timestamp'])}</td>
  <td style="padding:8px 10px;font-size:0.79rem;color:#E2E8F0">{tx.get('sender_name','')[:24]}</td>
  <td style="padding:8px 10px">{exp_b}</td>
  <td style="padding:8px 10px;font-size:0.79rem;color:#CBD5E1">{tx.get('beneficiary_name','')[:22]}</td>
  <td style="padding:8px 10px;font-size:0.81rem;color:#F1F5F9;font-weight:700;font-family:'JetBrains Mono',monospace">{fmt_currency(tx['amount'])}</td>
  <td style="padding:8px 10px;font-size:0.82rem;font-weight:600;color:{m1_col};text-align:center">{tx['method1_score']}</td>
  <td style="padding:8px 10px;font-size:0.86rem;font-weight:700;color:{m2_col};text-align:center">{tx['method2_score']}</td>
  <td style="padding:8px 10px;font-size:0.86rem;font-weight:700;color:{m3_col};text-align:center">{tx['method3_score']}</td>
  <td style="padding:8px 10px;text-align:center">{badge}</td>
  <td style="padding:8px 10px;text-align:center">{status_b}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#94A3B8;max-width:260px">{short_reason}</td>
</tr>"""

    st.markdown(
        f"""
<div style="max-height:370px;overflow-y:auto;border:1px solid #223342;border-radius:8px">
<table style="width:100%;border-collapse:collapse;background:#0E1720;font-family:'Inter',sans-serif">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342;position:sticky;top:0">
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">TX ID</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Timestamp</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Sender</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Model</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Counterparty</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Amount</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">M1</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">M2</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">M3</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Risk</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Status</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Primary Forensic Signal</th>
    </tr>
  </thead>
  <tbody>{html_rows}</tbody>
</table>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    qcol1, qcol2, qcol3, qcol4 = st.columns([2.2, 1.2, 1.2, 1.2])
    with qcol1:
        sel_tx = st.selectbox(
            "Quick-Jump: Select a transaction to inspect across workspaces",
            options=[
                f"{t['id']} · {t['sender_name'][:20]} · {fmt_currency(t['amount'])} (M2={t['method2_score']}, M3={t['method3_score']})"
                for t in high_risk_txs
            ],
            key="overview_tx_select",
        )
        chosen_tx_id = sel_tx.split(" · ")[0]
    with qcol2:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        if st.button("🔍 Explorer Detail →", use_container_width=True, key="ov_to_exp"):
            st.session_state["selected_tx_id"] = chosen_tx_id
            st.switch_page("pages/2_transaction_explorer.py")
    with qcol3:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        if st.button("⚗️ Risk Analysis Lab →", use_container_width=True, key="ov_to_risk"):
            st.session_state["selected_tx_id"] = chosen_tx_id
            st.switch_page("pages/3_risk_analysis_lab.py")
    with qcol4:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        if st.button("🔬 Forensic Timeline →", use_container_width=True, key="ov_to_for"):
            st.session_state["selected_tx_id"] = chosen_tx_id
            st.switch_page("pages/4_forensic_investigation.py")
else:
    st.info("No high-risk transactions found in the database.")

st.divider()

# ── F: Scenario Archetype Overview ────────────────────────────────────────
st.markdown('<div class="panel-header">8 SYNTHETIC FORENSIC SCENARIO ARCHETYPES</div>', unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.82rem;margin-bottom:14px">'
    'Eight deterministic scenarios covering legitimate corporate/personal false-positive traps '
    'and multi-stage attack lifecycles. Click any scenario button below to load its representative transaction into the Risk Lab.</p>',
    unsafe_allow_html=True,
)

legit_scenarios = [s for s in scenarios if s["type"] == "Legitimate"]
attack_scenarios = [s for s in scenarios if s["type"] == "Attack"]

col_leg, col_atk = st.columns(2, gap="large")

with col_leg:
    st.markdown(
        '<div style="font-size:0.72rem;color:#10B981;font-weight:700;letter-spacing:0.06em;'
        'text-transform:uppercase;margin-bottom:8px">✓ Legitimate False-Positive Suppression Scenarios</div>',
        unsafe_allow_html=True,
    )
    for s in legit_scenarios:
        render_scenario_card(s)
        if st.button(f"Inspect {s['tx_id']} ({s['name'][:30]}) in Risk Lab →", key=f"btn_{s['id']}"):
            st.session_state["selected_tx_id"] = s["tx_id"]
            st.switch_page("pages/3_risk_analysis_lab.py")

with col_atk:
    st.markdown(
        '<div style="font-size:0.72rem;color:#EF4444;font-weight:700;letter-spacing:0.06em;'
        'text-transform:uppercase;margin-bottom:8px">⚠ Multi-Stage Attack &amp; Evasion Scenarios</div>',
        unsafe_allow_html=True,
    )
    for s in attack_scenarios:
        render_scenario_card(s)
        if st.button(f"Investigate {s['tx_id']} ({s['name'][:30]}) in Risk Lab →", key=f"btn_{s['id']}"):
            st.session_state["selected_tx_id"] = s["tx_id"]
            st.switch_page("pages/3_risk_analysis_lab.py")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#64748B;font-size:0.7rem;padding:12px 0;border-top:1px solid #1E2D3B">'
    'TRACE-Fin v2.0 · Simulated Digital Banking &amp; Forensic Risk Protection</div>',
    unsafe_allow_html=True,
)
