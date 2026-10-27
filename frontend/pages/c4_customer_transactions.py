"""
TRACE-Fin Customer Page 4: My Transactions.
Displays the signed-in customer's transaction history with status badges and
a concise 2-line explainer whenever a transaction is rated Medium risk or higher.
"""

from __future__ import annotations

import streamlit as st

from services.data_provider import get_transactions
from ui.components import (
    fmt_currency,
    fmt_ts,
    render_empty_state,
    render_two_line_customer_explainer,
    risk_badge_html,
    status_badge_html,
)

auth_user = st.session_state.get("auth_user") or {}
uid = auth_user.get("user_id", "USR-001")

st.markdown("# 📜 My Transactions")
st.markdown(
    '<div style="color:#8A9CB0;font-size:0.85rem;margin-top:-10px;margin-bottom:18px">'
    'Complete history of your transfers, status updates, and security explanations.</div>',
    unsafe_allow_html=True,
)

all_txs = get_transactions()
my_txs = [t for t in all_txs if t.get("sender_id") == uid]

f1, f2 = st.columns([2, 1])
with f1:
    q = st.text_input("Search by Beneficiary or Transaction ID", placeholder="e.g., TX-0001 or vendor name", key="cust_tx_search")
with f2:
    band_filter = st.multiselect("Filter by Risk Level", options=["Low", "Medium", "High", "Critical"], default=[], key="cust_tx_band")

if q.strip():
    qs = q.strip().lower()
    my_txs = [
        t for t in my_txs
        if qs in t["id"].lower() or qs in t.get("beneficiary_name", "").lower()
    ]
if band_filter:
    my_txs = [t for t in my_txs if (t.get("method3_level") or t.get("method2_level")) in band_filter]

if not my_txs:
    render_empty_state("No transactions match your current filter.")
else:
    for tx in my_txs[:40]:
        score = int(tx.get("method3_score") or tx.get("method2_score") or 0)
        level = tx.get("method3_level") or tx.get("method2_level") or "Low"
        raw_status = tx.get("raw_status") or tx.get("status", "Settled")

        st.markdown(
            f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:14px 18px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
    <div>
      <span style="font-size:0.95rem;font-weight:700;color:#F1F5F9">{tx.get("beneficiary_name","—")}</span>
      <span style="font-size:0.74rem;color:#21D4C2;font-family:monospace;margin-left:8px">{tx["id"]}</span>
      <div style="font-size:0.74rem;color:#8A9CB0;margin-top:3px">
        {fmt_ts(tx["timestamp"])} &nbsp;·&nbsp; Location: {tx.get("geo_location","—")} ({tx.get("ip_address","—")}) &nbsp;·&nbsp; Device: <code>{tx.get("device_id","—")}</code>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="font-size:1.05rem;font-weight:700;color:#F8FAFC">{fmt_currency(float(tx["amount"]))}</span>
      {status_badge_html(tx["status"])}
      {risk_badge_html(level)}
    </div>
  </div>
</div>""",
            unsafe_allow_html=True,
        )
        if score >= 40 or raw_status in ("PENDING_VERIFICATION", "HELD_HIGH_RISK", "BLOCKED"):
            render_two_line_customer_explainer(
                tx_status=raw_status,
                risk_score=score,
                reasons=tx.get("alert_reasons") or [],
            )
