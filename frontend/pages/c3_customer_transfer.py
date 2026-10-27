"""
TRACE-Fin Customer Page 3: Transfer Money.
Customer-facing transfer page that automatically inherits the active login session's
network context (IP, location, device) and displays a 2-line explainer when rated Medium or higher.
"""

from __future__ import annotations

import streamlit as st

from services.data_provider import (
    create_transaction_live,
    get_user_beneficiaries_list,
    get_user_profile,
)
from ui.components import (
    fmt_currency,
    render_demo_banner,
    render_two_line_customer_explainer,
    risk_badge_html,
    status_badge_html,
)

render_demo_banner()

auth_user = st.session_state.get("auth_user") or {}
auth_session = st.session_state.get("auth_session") or {}
uid = auth_user.get("user_id", "USR-001")

fresh_profile = get_user_profile(uid) or auth_user
st.session_state["auth_user"] = fresh_profile
avail_bal = float(fresh_profile.get("simulated_balance", 10000.0))

st.markdown("# 💸 Transfer Money")
st.markdown(
    '<div style="color:#8A9CB0;font-size:0.85rem;margin-top:-10px;margin-bottom:18px">'
    'Send a simulated payment to one of your saved beneficiaries. Your current sign-in session context '
    'is automatically evaluated alongside your account profile before funds are deducted.</div>',
    unsafe_allow_html=True,
)

col_form, col_ctx = st.columns([1.35, 1.0])

bens = get_user_beneficiaries_list(uid)
latest_bens = {}
for b in bens:
    latest_bens[b["beneficiary_id"]] = b

with col_form:
    st.markdown('<div class="panel-header">Payment Details</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="background:#0B1929;border:1px solid #21D4C244;border-radius:8px;padding:12px 16px;margin-bottom:14px;'
        f'display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-size:0.82rem;color:#94A3B8">Available Simulated Balance</span>'
        f'<span style="font-size:1.25rem;font-weight:700;color:#10B981">{fmt_currency(avail_bal)}</span></div>',
        unsafe_allow_html=True,
    )

    if not latest_bens:
        st.warning("You have no saved beneficiaries yet. Please add one on the **Beneficiaries** page first.")
    else:
        ben_options = [
            f"{bid} · {b['beneficiary_name']} ({b['beneficiary_category']})"
            for bid, b in latest_bens.items()
        ]
        selected_ben_str = st.selectbox("Select Recipient Beneficiary", options=ben_options, key="cust_tx_ben")
        sel_bid = selected_ben_str.split(" · ")[0]
        sel_b = latest_bens[sel_bid]

        default_amt = min(float(fresh_profile.get("typical_tx_amount", 150.0)), max(10.0, avail_bal))
        tx_amount = st.number_input(
            "Transfer Amount (USD)",
            min_value=1.0,
            max_value=max(1000000.0, avail_bal * 2.0),
            value=round(default_amt, 2),
            step=50.0,
            key="cust_tx_amount",
        )
        tx_note = st.text_input(
            "Payment Reference / Memo (Optional)",
            value="Invoice / Personal Transfer",
            key="cust_tx_memo",
        )

        if tx_amount > avail_bal:
            st.error(
                f"Transfer amount ({fmt_currency(tx_amount)}) exceeds your available simulated balance ({fmt_currency(avail_bal)})."
            )

        if st.button(
            "🚀 Submit Simulated Transfer",
            type="primary",
            disabled=(tx_amount > avail_bal),
            use_container_width=True,
            key="cust_submit_transfer_btn",
        ):
            ses_ip = auth_session.get("ip_address") or f"{fresh_profile.get('home_ip_prefix', '103.21.244.')}25"
            ses_geo = auth_session.get("geo_location") or fresh_profile.get("home_geo_location", "IN-Mumbai")
            ses_dev = auth_session.get("device_id") or f"DEV-{uid.split('-')[-1]}-PRIMARY"

            res = create_transaction_live(
                {
                    "user_id": uid,
                    "amount": float(tx_amount),
                    "beneficiary_id": sel_bid,
                    "beneficiary_name": sel_b["beneficiary_name"],
                    "beneficiary_category": sel_b["beneficiary_category"],
                    "beneficiary_industry": sel_b["beneficiary_industry"],
                    "device_id": ses_dev,
                    "ip_address": ses_ip,
                    "geo_location": ses_geo,
                }
            )
            if res["ok"] and isinstance(res["data"], dict):
                st.session_state["last_customer_transfer_result"] = res["data"]
                st.rerun()
            else:
                st.error(res.get("error", "Could not process transfer."))

with col_ctx:
    st.markdown('<div class="panel-header">Active Sign-In Session Context</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:14px 16px;font-size:0.8rem;color:#CBD5E1;line-height:1.65">
  <div><b>Session ID:</b> <code>{auth_session.get("session_id","SES-ACTIVE")}</code></div>
  <div><b>Origin IP Address:</b> <code>{auth_session.get("ip_address","—")}</code></div>
  <div><b>Approximate Location:</b> <b>{auth_session.get("geo_location", fresh_profile.get("home_geo_location","—"))}</b></div>
  <div><b>Device:</b> {auth_session.get("device_label","Registered Device")} (<code>{auth_session.get("device_id","—")}</code>)</div>
  <div><b>Network Type:</b> {str(auth_session.get("network_type","home_broadband")).replace("_"," ").title()}</div>
  <div style="margin-top:8px;padding-top:8px;border-top:1px solid #1E2D3B;color:#8A9CB0;font-size:0.74rem">
    To test how a transfer behaves from a different city, VPN, or unseen device, sign out in the sidebar and choose another network preset on the Sign-In page.
  </div>
</div>""",
        unsafe_allow_html=True,
    )

# ── Display Transfer Outcome & 2-Line Explainer ────────────────────────────
last_res = st.session_state.get("last_customer_transfer_result")
if last_res:
    tx_obj = last_res.get("transaction", {})
    risk_cmp = last_res.get("risk_comparison", {})
    ti_res = risk_cmp.get("contextual_ti") or risk_cmp.get("contextual") or {}
    score = int(ti_res.get("risk_score", 0))
    band = str(ti_res.get("risk_band", "low")).capitalize()
    tx_status = tx_obj.get("status", "COMPLETED")
    reasons = [r.get("explanation", "") for r in ti_res.get("triggered_rules", []) if r.get("explanation")]

    st.markdown("---")
    st.markdown(f"### Latest Transfer Receipt · `{tx_obj.get('transaction_id', '')}`")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
        f'<span style="font-size:1.1rem;font-weight:700;color:#F8FAFC">{fmt_currency(float(tx_obj.get("amount", 0)))} to {tx_obj.get("beneficiary_name", "")}</span>'
        f'{status_badge_html(tx_status)} {risk_badge_html(band)}</div>',
        unsafe_allow_html=True,
    )

    if score >= 40 or tx_status in ("PENDING_VERIFICATION", "HELD_HIGH_RISK", "BLOCKED"):
        render_two_line_customer_explainer(
            tx_status=tx_status,
            risk_score=score,
            reasons=reasons,
        )
    else:
        st.success(
            f"Transfer `{tx_obj.get('transaction_id')}` completed immediately (Risk Score: {score}/100 — Low Risk)."
        )
