"""
PAGE 2 — Transaction Explorer
Interactive search, expenditure-model & risk-band filtering, and deep financial/forensic inspection.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import get_risk_scores, get_transaction, get_transactions
from ui.components import (
    RISK_COLOR_MAP,
    expenditure_badge_html,
    fmt_currency,
    fmt_ts,
    inject_css,
    render_demo_banner,
    render_empty_state,
    render_financial_calibration_card,
    risk_badge_html,
    status_badge_html,
)

inject_css()
render_demo_banner()

st.markdown("<h1>Historical Account Ledger &amp; Live Transactions</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Provides the historical account baseline ledger used by the scoring engine to compute 24-hour velocity, '
    'typical transaction envelopes, and established counterparty history—plus all live transactions created during your presentation.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Sidebar Filters ────────────────────────────────────────────────────────
st.sidebar.markdown(
    '<div style="font-size:0.68rem;color:#8A9CB0;font-weight:700;letter-spacing:0.08em;'
    'text-transform:uppercase;padding:4px 4px 6px">Ledger Filters</div>',
    unsafe_allow_html=True,
)

ledger_scope = st.sidebar.radio(
    "Ledger Scope",
    options=["all", "live_only", "historical_only"],
    format_func=lambda s: {
        "all": "All Records (Live First + History)",
        "live_only": "⚡ Live Created Transactions Only",
        "historical_only": "📂 Historical Baseline Ledger Only",
    }[s],
    index=0,
    key="tx_ledger_scope",
)

search_query = st.sidebar.text_input("Search (TX ID, Sender, Vendor, IP, Scenario)", key="tx_search")
risk_filter = st.sidebar.multiselect(
    "Risk Level (M2 / M3)",
    options=["Critical", "High", "Medium", "Low"],
    default=["Critical", "High", "Medium", "Low"],
    key="tx_risk_filter",
)
exp_filter = st.sidebar.multiselect(
    "Expense Type",
    options=["capex_heavy", "opex_heavy", "personal_consumption"],
    default=["capex_heavy", "opex_heavy", "personal_consumption"],
    key="tx_exp_filter",
)
status_filter = st.sidebar.multiselect(
    "Operational Status",
    options=["Blocked", "Flagged", "Pending Review", "Settled"],
    default=["Blocked", "Flagged", "Pending Review", "Settled"],
    key="tx_status_filter",
)

all_txs = get_transactions()
amounts = [t["amount"] for t in all_txs] if all_txs else [0.0, 200000.0]
max_amt = float(max(amounts)) if amounts else 200000.0

amount_range = st.sidebar.slider(
    "Amount Range (INR)",
    min_value=0.0,
    max_value=max(max_amt, 1000.0),
    value=(0.0, max(max_amt, 1000.0)),
    step=500.0,
    format="$%,.0f",
    key="tx_amount_range",
)

st.sidebar.divider()
sort_col = st.sidebar.selectbox(
    "Sort By",
    options=["method3_score", "method2_score", "method1_score", "amount", "timestamp"],
    format_func=lambda x: {
        "method3_score": "M3 Score (+Threat Intel)",
        "method2_score": "M2 Score (Contextual)",
        "method1_score": "M1 Score (Baseline)",
        "amount": "Transaction Amount (INR)",
        "timestamp": "Timestamp (UTC)",
    }[x],
    index=0,
    key="tx_sort_col",
)
sort_asc = st.sidebar.checkbox("Sort Ascending", value=False, key="tx_sort_asc")
page_size = st.sidebar.selectbox("Rows per page", options=[20, 50, 100], index=0, key="tx_page_size")

filters = {
    "search": search_query,
    "risk_levels": risk_filter if risk_filter else None,
    "expenditure_models": exp_filter if exp_filter else None,
    "statuses": status_filter if status_filter else None,
    "min_amount": amount_range[0],
    "max_amount": amount_range[1],
}
filtered_txs = get_transactions(filters)
if ledger_scope == "live_only":
    filtered_txs = [t for t in filtered_txs if t.get("is_live_created")]
elif ledger_scope == "historical_only":
    filtered_txs = [t for t in filtered_txs if not t.get("is_live_created")]

if filtered_txs:
    filtered_txs = sorted(
        filtered_txs,
        key=lambda t: (1 if (t.get("is_live_created") and not sort_asc) else 0, t.get(sort_col, 0)),
        reverse=not sort_asc,
    )

# Pagination
if "tx_page" not in st.session_state:
    st.session_state.tx_page = 0

total_pages = max(1, (len(filtered_txs) + page_size - 1) // page_size)
if st.session_state.tx_page >= total_pages:
    st.session_state.tx_page = 0
page_idx = st.session_state.tx_page
start, end = page_idx * page_size, (page_idx + 1) * page_size
page_txs = filtered_txs[start:end]

# ── Summary stats row ─────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Matching Transactions", f"{len(filtered_txs):,}")
c2.metric("High / Critical (≥60)", sum(1 for t in filtered_txs if t["method3_score"] >= 60))
c3.metric("Attack (Ground Truth)", sum(1 for t in filtered_txs if t["ground_truth"] == 1))
c4.metric("Total Volume (INR)", f'₹{sum(t["amount"] for t in filtered_txs):,.0f}')

st.markdown("<br>", unsafe_allow_html=True)

# ── Transaction Table ─────────────────────────────────────────────────────
if not page_txs:
    render_empty_state("No transactions match your current filter criteria.")
else:
    html_rows = ""
    for tx in page_txs:
        m1_color = RISK_COLOR_MAP.get(tx["method1_level"], "#8A9CB0")
        m2_color = RISK_COLOR_MAP.get(tx["method2_level"], "#8A9CB0")
        m3_color = RISK_COLOR_MAP.get(tx["method3_level"], "#8A9CB0")
        exp_b = expenditure_badge_html(tx.get("sender_expenditure_model", "personal_consumption"))
        gt_icon = "⚠ Attack" if tx["ground_truth"] == 1 else "✓ Legit"
        gt_color = "#EF4444" if tx["ground_truth"] == 1 else "#10B981"

        html_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:7px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#21D4C2;font-weight:600">{tx['id']}</td>
  <td style="padding:7px 10px;font-size:0.72rem;color:#8A9CB0;font-family:'JetBrains Mono',monospace">{fmt_ts(tx['timestamp'])}</td>
  <td style="padding:7px 10px;font-size:0.78rem;color:#E2E8F0">{tx.get('sender_name','')[:22]}</td>
  <td style="padding:7px 10px">{exp_b}</td>
  <td style="padding:7px 10px;font-size:0.77rem;color:#CBD5E1">{tx.get('beneficiary_name','')[:22]}</td>
  <td style="padding:7px 10px;font-size:0.79rem;color:#F1F5F9;font-weight:700;font-family:'JetBrains Mono',monospace">{fmt_currency(tx['amount'])}</td>
  <td style="padding:7px 10px;text-align:center;font-weight:600;color:{m1_color}">{tx['method1_score']}</td>
  <td style="padding:7px 10px;text-align:center;font-weight:700;color:{m2_color}">{tx['method2_score']}</td>
  <td style="padding:7px 10px;text-align:center;font-weight:700;color:{m3_color}">{tx['method3_score']}</td>
  <td style="padding:7px 10px;text-align:center">{risk_badge_html(tx['method3_level'])}</td>
  <td style="padding:7px 10px;text-align:center">{status_badge_html(tx['status'])}</td>
  <td style="padding:7px 10px;text-align:center;color:{gt_color};font-size:0.72rem;font-weight:600">{gt_icon}</td>
</tr>"""

    st.markdown(
        f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720;font-family:'Inter',sans-serif">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
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
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Eval Label</th>
    </tr>
  </thead>
  <tbody>{html_rows}</tbody>
</table>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("◀ Previous Page", key="tx_prev", disabled=(page_idx == 0)):
            st.session_state.tx_page = max(0, page_idx - 1)
            st.rerun()
    with pc2:
        st.markdown(
            f'<div style="text-align:center;color:#8A9CB0;font-size:0.8rem;padding-top:8px">'
            f'Page <b>{page_idx + 1}</b> of <b>{total_pages}</b> · {len(filtered_txs)} matching transactions</div>',
            unsafe_allow_html=True,
        )
    with pc3:
        if st.button("Next Page ▶", key="tx_next", disabled=(page_idx >= total_pages - 1)):
            st.session_state.tx_page = min(total_pages - 1, page_idx + 1)
            st.rerun()

st.divider()

# ── Transaction Detail & Financial Calibration Panel ──────────────────────
st.markdown(
    '<div class="panel-header">DEEP TRANSACTION &amp; ECONOMIC CALIBRATION INSPECTOR</div>',
    unsafe_allow_html=True,
)

tx_ids = [t["id"] for t in filtered_txs] if filtered_txs else [t["id"] for t in all_txs]
default_tx_id = st.session_state.get("selected_tx_id", tx_ids[0] if tx_ids else None)
default_idx = tx_ids.index(default_tx_id) if default_tx_id in tx_ids else 0

if tx_ids:
    selected_tx_id = st.selectbox(
        "Select Transaction to Inspect",
        options=tx_ids,
        index=default_idx,
        format_func=lambda tid: f"{tid} — {get_transaction(tid)['sender_name']} → {get_transaction(tid)['beneficiary_name']} ({fmt_currency(get_transaction(tid)['amount'])})",
        key="detail_tx_select",
    )
    st.session_state["selected_tx_id"] = selected_tx_id
    tx = get_transaction(selected_tx_id)
    scores = get_risk_scores(selected_tx_id)

    if tx and scores:
        # Render the sender's Economic & Business Calibration card
        render_financial_calibration_card(tx)

        d1, d2, d3 = st.columns(3, gap="large")

        with d1:
            st.markdown('<div class="panel-header">TELEMETRY &amp; ROUTING</div>', unsafe_allow_html=True)
            fields = {
                "Transaction ID": tx["id"],
                "Timestamp (UTC)": fmt_ts(tx["timestamp"]),
                "Amount": fmt_currency(tx["amount"], tx.get("currency", "INR")),
                "Scenario Archetype": tx.get("scenario_label", "—"),
                "Origin Device ID": tx.get("device_id", "—"),
                "Origin IP Address": tx.get("ip_address", "—"),
                "Origin Geo-Location": tx.get("geo_location", "—"),
                "Workflow Status": tx["status"],
            }
            for k, v in fields.items():
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:5px 0;border-bottom:1px solid #1E2D3B;font-size:0.79rem">'
                    f'<span style="color:#8A9CB0">{k}</span>'
                    f'<span style="color:#E2E8F0;font-weight:500;font-family:monospace">{v}</span></div>',
                    unsafe_allow_html=True,
                )

        with d2:
            st.markdown('<div class="panel-header">3-METHOD RISK SCORES</div>', unsafe_allow_html=True)
            for method_key, label in [
                ("method1", "M1: Transaction-Only Baseline"),
                ("method2", "M2: Contextual Forensic"),
                ("method3", "M3: Contextual + Threat Intel"),
            ]:
                m = scores[method_key]
                col = RISK_COLOR_MAP.get(m["level"], "#8A9CB0")
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:8px 0;border-bottom:1px solid #1E2D3B">'
                    f'<span style="font-size:0.79rem;color:#CBD5E1;font-weight:500">{label}</span>'
                    f'<div style="display:flex;align-items:center;gap:8px">'
                    f'<span style="font-size:1.15rem;font-weight:700;color:{col};font-family:monospace">{m["score"]}/100</span>'
                    f'{risk_badge_html(m["level"])}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="panel-header" style="margin-top:14px">TRIGGERED RULE IDs</div>', unsafe_allow_html=True)
            flags = scores.get("evidence_flags", [])
            if flags:
                for flag in flags:
                    st.markdown(
                        f'<div style="font-size:0.74rem;color:#21D4C2;padding:3px 0;font-family:monospace">▸ {flag}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="font-size:0.75rem;color:#10B981">✓ Zero anomaly rules triggered (0/100)</div>',
                    unsafe_allow_html=True,
                )

        with d3:
            st.markdown('<div class="panel-header">FORENSIC EXPLANATIONS &amp; NARRATIVE</div>', unsafe_allow_html=True)
            for reason in scores.get("alert_reasons", []):
                st.markdown(
                    f'<div style="font-size:0.76rem;color:#FDE68A;padding:5px 0;'
                    f'border-bottom:1px solid #1E2D3B;line-height:1.45">• {reason}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        nav1, nav2, nav3 = st.columns([1.4, 1.4, 2.5])
        with nav1:
            if st.button("⚗️ Open in Risk Analysis Lab →", use_container_width=True, key="nav_to_risk"):
                st.session_state["selected_tx_id"] = selected_tx_id
                st.switch_page("pages/3_risk_analysis_lab.py")
        with nav2:
            if st.button("🔬 Open Forensic Timeline →", use_container_width=True, key="nav_to_forensic"):
                st.session_state["selected_tx_id"] = selected_tx_id
                st.switch_page("pages/4_forensic_investigation.py")

    # CSV Export
    st.divider()
    if filtered_txs:
        df_export = pd.DataFrame(filtered_txs)
        csv_data = df_export.to_csv(index=False)
        st.download_button(
            label="⬇ Download Filtered Transactions (CSV)",
            data=csv_data,
            file_name="tracefin_transactions.csv",
            mime="text/csv",
            key="tx_csv_download",
        )
