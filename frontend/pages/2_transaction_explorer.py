"""
PAGE 2 — Transaction Explorer & Operational Ledger
Search, filter, and inspect enterprise banking transactions, economic baselines,
and live risk scores across the ledger.
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
    render_empty_state,
    render_financial_calibration_card,
    risk_badge_html,
    status_badge_html,
)

inject_css()

st.markdown("<h1>Transaction Explorer &amp; Operational Ledger</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Search and inspect all customer payment transactions across the core banking ledger. '
    'Review economic baseline profiles, authoritative live risk scores, and jump directly into detailed triage or forensic timelines.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Sidebar Filters ────────────────────────────────────────────────────────
st.sidebar.markdown(
    '<div style="font-size:0.68rem;color:#8A9CB0;font-weight:700;letter-spacing:0.08em;'
    'text-transform:uppercase;padding:4px 4px 6px">Ledger Filters</div>',
    unsafe_allow_html=True,
)

search_query = st.sidebar.text_input("Search (TX ID, Sender, Beneficiary, IP)", key="tx_search")

risk_filter = st.sidebar.multiselect(
    "Risk Level",
    options=["Critical", "High", "Medium", "Low"],
    default=["Critical", "High", "Medium", "Low"],
    key="tx_risk_filter",
)

exp_options = {
    "capex_heavy": "Capital Expenditure (CapEx)",
    "opex_heavy": "Operational Expense (OpEx)",
    "personal_consumption": "Personal / Retail",
}
exp_filter = st.sidebar.multiselect(
    "Expenditure Profile",
    options=list(exp_options.keys()),
    default=list(exp_options.keys()),
    format_func=lambda x: exp_options.get(x, x),
    key="tx_exp_filter",
)

status_filter = st.sidebar.multiselect(
    "Operational Status",
    options=["Flagged", "Pending Review", "Blocked", "Settled"],
    default=["Flagged", "Pending Review", "Blocked", "Settled"],
    key="tx_status_filter",
)

all_txs = get_transactions()
amounts = [float(t["amount"]) for t in all_txs] if all_txs else [0.0, 200000.0]
max_amt = float(max(amounts)) if amounts else 200000.0

max_slider_val = int(max(max_amt, 1000.0))

amount_range = st.sidebar.slider(
    "Amount Range (INR)",
    min_value=0,
    max_value=max_slider_val,
    value=(0, max_slider_val),
    step=500,
    format="₹%d",
    key="tx_amount_range",
)

st.sidebar.divider()
sort_col = st.sidebar.selectbox(
    "Sort By",
    options=["method3_score", "timestamp", "amount"],
    format_func=lambda x: {
        "method3_score": "Risk Score (High to Low)",
        "timestamp": "Timestamp (Newest First)",
        "amount": "Transaction Amount (Highest First)",
    }[x],
    index=0,
    key="tx_sort_col",
)
sort_asc = st.sidebar.checkbox("Reverse Sort Order", value=False, key="tx_sort_asc")
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

if filtered_txs:
    filtered_txs = sorted(
        filtered_txs,
        key=lambda t: t.get(sort_col, 0),
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

# ── Summary Stats Row (Actionable, No Ground-Truth Leak) ───────────────────
high_risk_count = sum(1 for t in filtered_txs if t.get("method3_score", t.get("risk_score", 0)) >= 60)
active_holds_count = sum(
    1 for t in filtered_txs
    if t.get("status") in ("Flagged", "Pending Review") or t.get("raw_status") in ("HELD_HIGH_RISK", "PENDING_VERIFICATION")
)
total_volume = sum(float(t["amount"]) for t in filtered_txs)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Matching Transactions", f"{len(filtered_txs):,}")
c2.metric("Active Holds (Open Action)", f"{active_holds_count:,}")
c3.metric("Elevated Risk History (≥60)", f"{high_risk_count:,}")
c4.metric("Total Filtered Volume", f"₹{total_volume:,.0f}")

st.markdown("<br>", unsafe_allow_html=True)

# ── Transaction Table (Clean, Authoritative, No 3-Way Internal Scores) ─────
if not page_txs:
    render_empty_state("No transactions match your current filter criteria.")
else:
    html_rows = ""
    for tx in page_txs:
        score = int(tx.get("method3_score", tx.get("risk_score", 0)))
        level = tx.get("method3_level", "Medium")
        score_color = RISK_COLOR_MAP.get(level, "#8A9CB0")
        exp_b = expenditure_badge_html(tx.get("sender_expenditure_model", "personal_consumption"))

        html_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#21D4C2;font-weight:600">{tx['id']}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#8A9CB0;font-family:'JetBrains Mono',monospace">{fmt_ts(tx['timestamp'])}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#E2E8F0;font-weight:500">{tx.get('sender_name','')[:22]}</td>
  <td style="padding:8px 10px">{exp_b}</td>
  <td style="padding:8px 10px;font-size:0.77rem;color:#CBD5E1">{tx.get('beneficiary_name','')[:22]}</td>
  <td style="padding:8px 10px;font-size:0.80rem;color:#F1F5F9;font-weight:700;font-family:'JetBrains Mono',monospace">{fmt_currency(tx['amount'])}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{score_color};font-family:'JetBrains Mono',monospace;font-size:0.85rem">{score}/100</td>
  <td style="padding:8px 10px;text-align:center">{risk_badge_html(level)}</td>
  <td style="padding:8px 10px;text-align:center">{status_badge_html(tx['status'])}</td>
</tr>"""

    st.markdown(
        f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720;font-family:'Inter',sans-serif">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">TX ID</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Timestamp (UTC)</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Account Holder</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Profile</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Beneficiary</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Amount</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Risk Score</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Risk Level</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;font-weight:600;text-transform:uppercase">Status</th>
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
            f'Page <b>{page_idx + 1}</b> of <b>{total_pages}</b> · {len(filtered_txs):,} matching transactions</div>',
            unsafe_allow_html=True,
        )
    with pc3:
        if st.button("Next Page ▶", key="tx_next", disabled=(page_idx >= total_pages - 1)):
            st.session_state.tx_page = min(total_pages - 1, page_idx + 1)
            st.rerun()

st.divider()

# ── Deep Transaction & Economic Calibration Inspector ──────────────────────
st.markdown(
    '<div class="panel-header">DEEP TRANSACTION &amp; ECONOMIC PROFILE INSPECTOR</div>',
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
        format_func=lambda tid: (
            f"{tid} — {get_transaction(tid)['sender_name']} → {get_transaction(tid)['beneficiary_name']} "
            f"({fmt_currency(get_transaction(tid)['amount'])}) · Risk: {get_transaction(tid).get('method3_score', get_transaction(tid).get('risk_score', 0))}/100"
        ),
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
            st.markdown('<div class="panel-header">TRANSACTION &amp; NETWORK METADATA</div>', unsafe_allow_html=True)
            fields = {
                "Transaction ID": tx["id"],
                "Timestamp (UTC)": fmt_ts(tx["timestamp"]),
                "Amount": fmt_currency(tx["amount"], tx.get("currency", "INR")),
                "Origin Device ID": tx.get("device_id", "—"),
                "Origin IP Address": tx.get("ip_address", "—"),
                "Origin Geo-Location": tx.get("geo_location", "—"),
                "Workflow Status": tx["status"],
            }
            for k, v in fields.items():
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.79rem">'
                    f'<span style="color:#8A9CB0">{k}</span>'
                    f'<span style="color:#E2E8F0;font-weight:500;font-family:monospace">{v}</span></div>',
                    unsafe_allow_html=True,
                )

        with d2:
            st.markdown('<div class="panel-header">AUTHORITATIVE RISK ASSESSMENT</div>', unsafe_allow_html=True)
            m3_score = scores.get("method3", {}).get("score", tx.get("method3_score", 0))
            m3_level = scores.get("method3", {}).get("level", tx.get("method3_level", "Medium"))
            score_color = RISK_COLOR_MAP.get(m3_level, "#8A9CB0")

            st.markdown(
                f"""
<div style="background:#09121B;border:1px solid #223342;border-radius:8px;padding:12px 16px;margin-bottom:14px">
  <div style="font-size:0.68rem;color:#8A9CB0;text-transform:uppercase">Composite Risk Score</div>
  <div style="display:flex;align-items:center;gap:12px;margin-top:4px">
    <span style="font-size:2.0rem;font-weight:700;color:{score_color};font-family:monospace">{m3_score}/100</span>
    <div>{risk_badge_html(m3_level)}</div>
  </div>
  <div style="font-size:0.72rem;color:#8A9CB0;margin-top:6px">
    Alert Policy Threshold: <b style="color:#F1F5F9">{tx.get('user_alert_threshold', 60)}/100</b>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div style="font-size:0.68rem;color:#8A9CB0;font-weight:700;letter-spacing:0.07em;'
                'text-transform:uppercase;margin:10px 0 6px">ACTIVE SECURITY RULE FLAGS</div>',
                unsafe_allow_html=True,
            )
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
            st.markdown('<div class="panel-header">SECURITY FINDINGS &amp; DIRECT ACTIONS</div>', unsafe_allow_html=True)
            reasons = scores.get("alert_reasons", [])
            if reasons:
                for reason in reasons:
                    st.markdown(
                        f'<div style="font-size:0.76rem;color:#FCA5A5;padding:5px 8px;'
                        f'background:#2A0E12;border-left:3px solid #EF4444;border-radius:0 4px 4px 0;'
                        f'margin-bottom:6px;line-height:1.4">▸ {reason}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="font-size:0.75rem;color:#6EE7B7;padding:6px 8px;background:#072318;border-radius:4px">'
                    '✓ Transaction parameters match established baseline.</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            st.markdown(
                '<div style="font-size:0.68rem;color:#8A9CB0;font-weight:700;letter-spacing:0.07em;'
                'text-transform:uppercase;margin-bottom:8px">WORKFLOW SHORTCUTS</div>',
                unsafe_allow_html=True,
            )
            if st.button("⚗️ Open in Risk Analysis Lab →", use_container_width=True, key="nav_to_risk"):
                st.session_state["selected_tx_id"] = selected_tx_id
                st.switch_page("pages/3_risk_analysis_lab.py")

            if st.button("🔬 Open Forensic Timeline →", use_container_width=True, key="nav_to_forensic"):
                st.session_state["selected_tx_id"] = selected_tx_id
                st.switch_page("pages/4_forensic_investigation.py")

    # CSV Export
    st.divider()
    if filtered_txs:
        # Prepare clean export columns (no ground truth or internal scenario tags)
        export_records = []
        for t in filtered_txs:
            export_records.append(
                {
                    "Transaction ID": t.get("id"),
                    "Timestamp UTC": t.get("timestamp"),
                    "Account Holder": t.get("sender_name"),
                    "Account Profile": t.get("sender_profile"),
                    "Beneficiary": t.get("beneficiary_name"),
                    "Amount INR": t.get("amount"),
                    "Risk Score": t.get("method3_score", t.get("risk_score", 0)),
                    "Risk Level": t.get("method3_level", "Medium"),
                    "Operational Status": t.get("status"),
                    "Origin IP": t.get("ip_address"),
                    "Origin Geo": t.get("geo_location"),
                }
            )
        df_export = pd.DataFrame(export_records)
        csv_data = df_export.to_csv(index=False)
        st.download_button(
            label="⬇ Download Filtered Transactions (CSV)",
            data=csv_data,
            file_name="tracefin_transactions.csv",
            mime="text/csv",
            key="tx_csv_download",
        )
