"""
PAGE 1 — Overview Dashboard
Executive command center displaying live KPIs, activity trends, risk distribution,
and priority cases requiring administrator attention.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_activity_chart_data,
    get_dashboard_metrics,
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
    render_kpi_row,
    risk_badge_html,
    status_badge_html,
)

inject_css()

# Load live data from FastAPI + SQLite
metrics = get_dashboard_metrics()
all_txs = get_transactions()
chart_data = get_activity_chart_data()

# ── Page Header ───────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([3, 1.3])
with hdr_left:
    st.markdown(
        """
<div style="margin-bottom:4px">
  <h1 style="margin:0;font-size:1.75rem;font-weight:700;color:#F1F5F9">
    TRACE-Fin Security Command Center
  </h1>
  <p style="margin:5px 0 0;color:#8A9CB0;font-size:0.86rem;max-width:820px;line-height:1.45">
    Real-time transaction risk monitoring, customer step-up verification, and forensic investigation.
    Correlating login and device activity with account economic profiles, counterparty history,
    and freshness-validated threat intelligence.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )
with hdr_right:
    st.markdown(
        f'<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:10px 14px;text-align:right">'
        f'<div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.06em">Monitoring Period</div>'
        f'<div style="font-size:0.82rem;font-weight:600;color:#21D4C2;font-family:monospace">{metrics["reporting_period"]}</div>'
        f'<div style="font-size:0.68rem;color:#94A3B8;margin-top:2px">Accounts Monitored: <b>{metrics.get("total_users", 12)}</b> · Engine: <b>Live SQLite</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── 1. The 4 Distinct Actionable KPI Cards ─────────────────────────────────
total_tx_count = len(all_txs)
awaiting_customer_count = sum(
    1
    for t in all_txs
    if t.get("raw_status") == "PENDING_VERIFICATION" or t.get("status") in ("Pending Review", "Pending")
)
held_investigation_count = sum(
    1
    for t in all_txs
    if t.get("raw_status") == "HELD_HIGH_RISK" or t.get("status") in ("Flagged", "Held")
)
open_incidents_count = int(metrics.get("open_incidents", 0))

render_kpi_row(
    [
        {
            "label": "Total Transactions Processed",
            "value": f"{total_tx_count:,}",
            "color": "#21D4C2",
            "delta": f"{metrics.get('live_created_count', 0)} live created · {total_tx_count - metrics.get('live_created_count', 0)} baseline records",
            "delta_positive": True,
        },
        {
            "label": "Awaiting Customer Verification",
            "value": f"{awaiting_customer_count:,}",
            "color": "#F59E0B",
            "delta": "Transfers awaiting customer step-up confirmation",
            "delta_positive": awaiting_customer_count == 0,
        },
        {
            "label": "Held for Investigation",
            "value": f"{held_investigation_count:,}",
            "color": "#EF4444",
            "delta": "High-risk transfers frozen pending administrator decision",
            "delta_positive": held_investigation_count == 0,
        },
        {
            "label": "Open Security Incidents",
            "value": f"{open_incidents_count:,}",
            "color": "#DC2626",
            "delta": "Formal security incident cases under review",
            "delta_positive": open_incidents_count == 0,
        },
    ]
)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ── 2. Visual Charts (Activity + Risk & Status Distribution) ───────────────
col_act, col_dist = st.columns([2.1, 1.3], gap="large")

with col_act:
    st.markdown('<div class="panel-header">Daily Transaction Activity</div>', unsafe_allow_html=True)
    fig_act = build_activity_chart(chart_data)
    st.plotly_chart(fig_act, use_container_width=True, config={"displayModeBar": False})

with col_dist:
    st.markdown('<div class="panel-header">Risk &amp; Status Breakdown</div>', unsafe_allow_html=True)
    fig_dist = build_risk_distribution_chart(all_txs)
    st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── 3. Needs Your Attention (Actionable Alert Queue) ───────────────────────
st.markdown('<div class="panel-header">Needs Your Attention</div>', unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.84rem;margin-top:-4px;margin-bottom:12px">'
    'Transfers currently held for administrator review, awaiting verification, or flagged with elevated risk indicators. '
    'Select any record below to investigate the login/device activity and approve or block funds.</p>',
    unsafe_allow_html=True,
)

# Prioritize held transfers, then pending verification, then highest M3 risk score
attention_txs = sorted(
    [
        t
        for t in all_txs
        if t.get("raw_status") in ("HELD_HIGH_RISK", "PENDING_VERIFICATION")
        or t.get("status") in ("Flagged", "Pending Review")
        or t.get("method3_score", 0) >= 60
        or t.get("is_live_created")
    ],
    key=lambda t: (
        1 if t.get("raw_status") == "HELD_HIGH_RISK" or t.get("status") == "Flagged" else 0,
        1 if t.get("is_live_created") else 0,
        t.get("method3_score", 0),
        t.get("method2_score", 0),
    ),
    reverse=True,
)[:12]

if attention_txs:
    html_rows = ""
    for tx in attention_txs:
        level = tx["method3_level"]
        badge = risk_badge_html(level)
        status_b = status_badge_html(tx["status"])
        exp_b = expenditure_badge_html(tx.get("sender_expenditure_model", "personal_consumption"))
        m1_col = RISK_COLOR_MAP.get(tx["method1_level"], "#8A9CB0")
        m2_col = RISK_COLOR_MAP.get(tx["method2_level"], "#8A9CB0")
        m3_col = RISK_COLOR_MAP.get(tx["method3_level"], "#8A9CB0")
        reason_str = tx.get("alert_reasons", [""])[0]
        short_reason = reason_str[:76] + ("…" if len(reason_str) > 76 else "")

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
  <td style="padding:8px 10px;font-size:0.72rem;color:#94A3B8;max-width:280px">{short_reason}</td>
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
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Expense Type</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Counterparty</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Amount</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">M1</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">M2</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">M3</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Risk</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Status</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Risk Score &amp; Reasons</th>
    </tr>
  </thead>
  <tbody>{html_rows}</tbody>
</table>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    qcol1, qcol2, qcol3, qcol4 = st.columns([2.3, 1.2, 1.2, 1.2])
    with qcol1:
        sel_tx = st.selectbox(
            "Select a transaction from queue to take action:",
            options=[
                f"{t['id']} · {t['sender_name'][:18]} · {fmt_currency(t['amount'])} ({t.get('status','Flagged')})"
                for t in attention_txs
            ],
            key="overview_tx_select",
        )
        chosen_tx_id = sel_tx.split(" · ")[0]
    with qcol2:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("⚗️ Review in Risk Lab →", use_container_width=True, key="ov_to_risk"):
            st.session_state["selected_tx_id"] = chosen_tx_id
            st.switch_page("pages/3_risk_analysis_lab.py")
    with qcol3:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("🔬 Investigate Transaction →", use_container_width=True, key="ov_to_for"):
            st.session_state["selected_tx_id"] = chosen_tx_id
            st.switch_page("pages/4_forensic_investigation.py")
    with qcol4:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("🔍 View in Ledger →", use_container_width=True, key="ov_to_exp"):
            st.session_state["selected_tx_id"] = chosen_tx_id
            st.switch_page("pages/2_transaction_explorer.py")
else:
    st.info("No transfers currently require administrator attention. All accounts operating within normal baseline.")
