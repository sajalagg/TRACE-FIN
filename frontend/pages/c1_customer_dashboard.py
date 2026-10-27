"""
TRACE-Fin Customer Page 1: Account Dashboard.
Displays simulated account balance, active session network context, recent transactions
(with 2-line explainers on medium/high risk transfers), and pending security alerts.
"""

from __future__ import annotations

import streamlit as st

from services.data_provider import (
    get_transactions,
    get_user_beneficiaries_list,
    get_user_profile,
    get_user_sessions,
    get_verification_requests_live,
)
from ui.components import (
    expenditure_badge_html,
    fmt_currency,
    fmt_ts,
    render_demo_banner,
    render_kpi_row,
    render_two_line_customer_explainer,
    risk_badge_html,
    status_badge_html,
)

render_demo_banner()

auth_user = st.session_state.get("auth_user") or {}
auth_session = st.session_state.get("auth_session") or {}
uid = auth_user.get("user_id", "USR-001")

# Refresh live profile for up-to-date simulated balance
fresh_profile = get_user_profile(uid) or auth_user
st.session_state["auth_user"] = fresh_profile

st.markdown(f"# 🏦 Welcome back, {fresh_profile.get('display_name', 'Valued Customer')}")
st.markdown(
    f'<div style="color:#8A9CB0;font-size:0.85rem;margin-top:-10px;margin-bottom:18px">'
    f'Account ID: <code>{uid}</code> · Username: <code>@{fresh_profile.get("username") or uid.lower()}</code> · '
    f'Home Location: <b>{fresh_profile.get("home_geo_location", "—")}</b> '
    f'{expenditure_badge_html(fresh_profile.get("expenditure_model", "personal_consumption"))}</div>',
    unsafe_allow_html=True,
)

user_txs = get_transactions({"search": uid})
user_txs = [t for t in user_txs if t.get("sender_id") == uid]
pending_alerts = get_verification_requests_live(user_id=uid, status="pending")
bens = get_user_beneficiaries_list(uid)

# Deduplicate beneficiaries by beneficiary_id
unique_bens = {b["beneficiary_id"]: b for b in bens}

render_kpi_row(
    [
        {
            "label": "Available Balance",
            "value": fmt_currency(float(fresh_profile.get("simulated_balance", 10000.0))),
            "color": "#10B981",
            "delta": "Active Account Balance",
            "delta_positive": True,
        },
        {
            "label": "Typical / Max Single Transfer",
            "value": f"{fmt_currency(float(fresh_profile.get('typical_tx_amount', 100)))} / {fmt_currency(float(fresh_profile.get('typical_max_tx_amount', 1000)))}",
            "color": "#21D4C2",
            "delta": f"Monthly Turnover: {fmt_currency(float(fresh_profile.get('declared_monthly_turnover', 5000)))}",
            "delta_positive": True,
        },
        {
            "label": "Saved Beneficiaries",
            "value": str(len(unique_bens)),
            "color": "#3B82F6",
            "delta": "Active Counterparties",
            "delta_positive": True,
        },
        {
            "label": "Pending Security Alerts",
            "value": str(len(pending_alerts)),
            "color": "#F59E0B" if pending_alerts else "#10B981",
            "delta": "Action Required in Security Alerts" if pending_alerts else "All Transfers Clear",
            "delta_positive": len(pending_alerts) == 0,
        },
    ]
)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

col_left, col_right = st.columns([1.45, 1.0])

with col_left:
    st.markdown('<div class="panel-header">Recent Account Transfers</div>', unsafe_allow_html=True)
    if not user_txs:
        st.info("No transactions recorded for your account yet. Use **Transfer Money** to send a payment.")
    else:
        for tx in user_txs[:6]:
            score = int(tx.get("method3_score") or tx.get("method2_score") or 0)
            level = tx.get("method3_level") or tx.get("method2_level") or "Low"
            raw_status = tx.get("raw_status") or tx.get("status", "Settled")
            st.markdown(
                f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:12px 16px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-weight:700;color:#F1F5F9;font-size:0.92rem">{tx.get("beneficiary_name","—")}</span>
      <span style="font-size:0.74rem;color:#8A9CB0;margin-left:8px;font-family:monospace">{tx["id"]} · {fmt_ts(tx["timestamp"])}</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="font-weight:700;font-size:0.98rem;color:#F8FAFC">{fmt_currency(float(tx["amount"]))}</span>
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

with col_right:
    st.markdown('<div class="panel-header">Current Sign-In &amp; Recent Sessions</div>', unsafe_allow_html=True)
    if auth_session:
        inf = auth_session.get("inferred_context") or {}
        sim = auth_session.get("simulated_input") or {}
        badge_col = "#10B981" if (auth_session.get("is_known_ip") and auth_session.get("is_known_device")) else "#F59E0B"
        st.markdown(
            f"""
<div style="background:#0E1720;border:1px solid {badge_col}66;border-left:4px solid {badge_col};
border-radius:8px;padding:14px 16px;margin-bottom:12px">
  <div style="font-size:0.7rem;color:#21D4C2;font-weight:700;text-transform:uppercase;letter-spacing:0.06em">
    Active Session · {auth_session.get("session_id","—")}
  </div>
  <div style="font-size:0.84rem;color:#F1F5F9;font-weight:600;margin-top:4px">
    📍 {auth_session.get("geo_location","—")} &nbsp;·&nbsp; IP: <code>{auth_session.get("ip_address","—")}</code>
  </div>
  <div style="font-size:0.76rem;color:#94A3B8;margin-top:4px">
    Device: <b>{sim.get("device_label", auth_session.get("device_label","—"))}</b> (<code>{auth_session.get("device_id","—")}</code>)<br>
    Network: <b>{str(auth_session.get("network_type","home_broadband")).replace("_"," ").title()}</b>
  </div>
  <div style="font-size:0.75rem;color:#CBD5E1;margin-top:8px;padding-top:8px;border-top:1px solid #1E2D3B">
    {inf.get("context_summary","Trusted baseline session.")}
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    sessions = get_user_sessions(user_id=uid, limit=5)
    if sessions:
        for s in sessions[:4]:
            st.markdown(
                f'<div style="font-size:0.75rem;color:#94A3B8;padding:6px 10px;border-bottom:1px solid #1E2D3B">'
                f'<code>{s["session_id"]}</code> · <b>{s["geo_location"]}</b> ({s["ip_address"]}) · '
                f'{s["network_type"].replace("_", " ")} · {fmt_ts(s["created_at_utc"])}</div>',
                unsafe_allow_html=True,
            )
