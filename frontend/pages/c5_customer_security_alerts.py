"""
TRACE-Fin Customer Page 5: Security Alerts & Step-Up Verification.
Allows the signed-in customer to review pending verification requests ('I made this transaction'
or 'I did not make this transaction') and view recent sign-in activity.
"""

from __future__ import annotations

import streamlit as st

from services.data_provider import (
    get_user_profile,
    get_user_sessions,
    get_verification_requests_live,
    respond_verification_request_live,
)
from ui.components import fmt_currency, fmt_ts, render_demo_banner, status_badge_html

render_demo_banner()

auth_user = st.session_state.get("auth_user") or {}
uid = auth_user.get("user_id", "USR-001")

st.markdown("# 🚨 Security Alerts & Verification")
st.markdown(
    '<div style="color:#8A9CB0;font-size:0.85rem;margin-top:-10px;margin-bottom:18px">'
    'Confirm or deny unusual transfers on your account. Denying a transfer immediately blocks it and '
    'opens a protected security incident; high-risk holds are also reviewed by an administrator in the Risk Analysis Lab.</div>',
    unsafe_allow_html=True,
)

all_reqs = get_verification_requests_live(user_id=uid)
pending_reqs = [r for r in all_reqs if r.get("status") in ("pending", "awaiting_admin_release")]
resolved_reqs = [r for r in all_reqs if r.get("status") not in ("pending", "awaiting_admin_release")]

st.markdown(
    f'<div class="panel-header">Action Required · Pending Verification Requests ({len(pending_reqs)})</div>',
    unsafe_allow_html=True,
)

if not pending_reqs:
    st.success("You have no pending security verification alerts right now.")
else:
    for req in pending_reqs:
        req_id = req["request_id"]
        tx_id = req["transaction_id"]
        needs_admin = bool(req.get("requires_admin_release"))
        st.markdown(
            f"""
<div style="background:#281D0A;border:1px solid #F59E0B;border-left:4px solid #F59E0B;
border-radius:8px;padding:16px 20px;margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-size:0.75rem;color:#FDE68A;font-weight:700;text-transform:uppercase">
        Verification Request · {req_id} (Transfer {tx_id})
      </span>
      <div style="font-size:1.05rem;font-weight:700;color:#F8FAFC;margin-top:4px">
        {fmt_currency(float(req["amount"]))} to {req["beneficiary_name"]} (<code>{req["beneficiary_id"]}</code>)
      </div>
      <div style="font-size:0.76rem;color:#CBD5E1;margin-top:3px">
        Created: {fmt_ts(req["created_at_utc"])} &nbsp;·&nbsp;
        {"Requires Administrator Release in Risk Analysis Lab after your confirmation" if needs_admin else "Step-Up Customer Confirmation"}
      </div>
    </div>
    {status_badge_html(req["status"])}
  </div>
</div>""",
            unsafe_allow_html=True,
        )

        if req.get("status") == "awaiting_admin_release":
            st.info(
                f"You confirmed intent for `{tx_id}`. This high-risk transfer is now awaiting final administrator verification in the **Risk Analysis Lab** before your simulated balance is deducted."
            )
        else:
            note_val = st.text_input(
                f"Optional Note for {req_id}",
                value="Verified by account holder in Security Alerts.",
                key=f"cust_ver_note_{req_id}",
            )
            b1, b2 = st.columns(2)
            with b1:
                if st.button(
                    "✅ I made this transaction",
                    key=f"btn_approve_{req_id}",
                    use_container_width=True,
                ):
                    res = respond_verification_request_live(req_id, "approved", note_val)
                    if res["ok"]:
                        refreshed_u = get_user_profile(uid)
                        if refreshed_u:
                            st.session_state["auth_user"] = refreshed_u
                        st.success(f"Recorded confirmation for `{tx_id}`.")
                        st.rerun()
                    else:
                        st.error(res.get("error", "Could not submit response."))
            with b2:
                if st.button(
                    "🛑 I did not make this transaction",
                    key=f"btn_deny_{req_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    res = respond_verification_request_live(
                        req_id,
                        "denied",
                        note_val or "Customer reported unauthorized transfer in Security Alerts.",
                    )
                    if res["ok"]:
                        st.warning(
                            f"Transfer `{tx_id}` has been blocked and escalated to the security team."
                        )
                        st.rerun()
                    else:
                        st.error(res.get("error", "Could not submit response."))

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

col_hist, col_sess = st.columns([1.2, 1.0])

with col_hist:
    st.markdown(
        f'<div class="panel-header">Past Verification Responses ({len(resolved_reqs)})</div>',
        unsafe_allow_html=True,
    )
    if not resolved_reqs:
        st.caption("No past verification responses for your account.")
    else:
        for r in resolved_reqs[:10]:
            inc_tag = f" · Incident `{r['linked_incident_id']}`" if r.get("linked_incident_id") else ""
            st.markdown(
                f'<div style="background:#0E1720;border:1px solid #223342;border-radius:7px;padding:10px 14px;margin-bottom:8px;font-size:0.8rem">'
                f'<b>{r["request_id"]}</b> (Transfer <code>{r["transaction_id"]}</code>) · '
                f'{fmt_currency(float(r["amount"]))} to <b>{r["beneficiary_name"]}</b> · '
                f'Status: <code>{r["status"]}</code>{inc_tag}<br>'
                f'<span style="color:#8A9CB0;font-size:0.74rem">{r.get("response_notes") or "—"}</span></div>',
                unsafe_allow_html=True,
            )

with col_sess:
    st.markdown('<div class="panel-header">Recent Sign-In Activity</div>', unsafe_allow_html=True)
    sessions = get_user_sessions(user_id=uid, limit=8)
    if not sessions:
        st.caption("No recent sign-in sessions recorded.")
    else:
        for s in sessions:
            inf = s.get("inferred_context") or {}
            st.markdown(
                f'<div style="background:#0E1720;border:1px solid #223342;border-radius:7px;padding:10px 14px;margin-bottom:8px;font-size:0.78rem">'
                f'<b>{s["geo_location"]}</b> (<code>{s["ip_address"]}</code>) · {s["device_label"]}<br>'
                f'<span style="color:#8A9CB0;font-size:0.72rem">{fmt_ts(s["created_at_utc"])} · {inf.get("context_summary", "")}</span></div>',
                unsafe_allow_html=True,
            )
