"""
PAGE 2 (Risk Analysis Lab) — Transaction Risk Analysis & Authorization
Operational triage, rule-level explainability, counterfactual analysis,
and out-of-band customer verification for transfer release or blocking.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_risk_scores,
    get_session_detail_live,
    get_transaction,
    get_transactions,
    get_user_sessions,
    get_verification_requests_live,
    submit_admin_transaction_decision_live,
)
from ui.components import (
    RISK_COLOR_MAP,
    fmt_currency,
    fmt_ts,
    inject_css,
    status_badge_html,
)

inject_css()

st.markdown("<h1>Risk Analysis &amp; Transfer Authorization</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Investigate transaction risk indicators, review triggered security rules and counterfactual explanations, '
    'record customer verification, and authorize or block held transfers.</p>',
    unsafe_allow_html=True,
)

st.divider()

# ── Urgent Held Transfers Queue & Transaction Selector ──────────────────────
all_txs = get_transactions()
all_tx_ids = [t["id"] for t in all_txs]

pending_or_held_txs = [
    t for t in all_txs
    if t.get("raw_status") == "HELD_HIGH_RISK"
    or (t.get("status") == "Flagged" and t.get("raw_status") not in ("PENDING_VERIFICATION", "BLOCKED", "COMPLETED"))
]

if pending_or_held_txs:
    with st.expander(
        f"🚨 Urgent Transfers Awaiting Verification & Release ({len(pending_or_held_txs)})",
        expanded=True,
    ):
        st.caption(
            "Transfers held under high-risk security policies require out-of-band customer verification "
            "and administrator authorization before funds can be released."
        )
        q_cols = st.columns([3.5, 1.5])
        with q_cols[0]:
            queue_tx_id = st.selectbox(
                "Held Transfer Queue",
                options=[t["id"] for t in pending_or_held_txs],
                format_func=lambda tid: (
                    f"{tid} · {get_transaction(tid)['sender_name']} → {get_transaction(tid)['beneficiary_name']} · "
                    f"{fmt_currency(get_transaction(tid)['amount'])} · "
                    f"Risk Score: {get_transaction(tid).get('method3_score', get_transaction(tid).get('risk_score', 0))}/100 · "
                    f"[{get_transaction(tid).get('raw_status', get_transaction(tid)['status'])}]"
                ),
                key="risk_lab_pending_queue_select",
            )
        with q_cols[1]:
            st.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
            if st.button("🔍 Load into Investigation", use_container_width=True, key="btn_load_pending_into_lab"):
                st.session_state["selected_tx_id"] = queue_tx_id
                st.session_state["risk_custom_tx_selector"] = queue_tx_id
                st.rerun()

current_tx_id = st.session_state.get("selected_tx_id", all_tx_ids[0] if all_tx_ids else "TX-0391")
if current_tx_id not in all_tx_ids and all_tx_ids:
    current_tx_id = all_tx_ids[0]
default_idx = all_tx_ids.index(current_tx_id) if current_tx_id in all_tx_ids else 0

def _on_tx_change() -> None:
    st.session_state["selected_tx_id"] = st.session_state["risk_custom_tx_selector"]

selected_tx_id = st.selectbox(
    "Select Transaction to Inspect",
    options=all_tx_ids,
    index=default_idx,
    format_func=lambda tid: (
        f"{'⚡ LIVE · ' if get_transaction(tid).get('is_live_created') else ''}"
        f"{tid} · {get_transaction(tid)['sender_name'][:22]} → "
        f"{get_transaction(tid)['beneficiary_name'][:20]} · "
        f"{fmt_currency(get_transaction(tid)['amount'])} · "
        f"Risk Score: {get_transaction(tid).get('method3_score', get_transaction(tid).get('risk_score', 0))}/100 · "
        f"[{get_transaction(tid).get('raw_status', get_transaction(tid).get('status', ''))}]"
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

raw_tx_status = tx.get("raw_status") or tx.get("status", "COMPLETED")
bal_deducted_flag = bool(tx.get("balance_deducted", True))

# ── Session & Verification Records ─────────────────────────────────────────
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

st.divider()

# ── Transaction & Customer Snapshot ────────────────────────────────────────
st.markdown('<div class="panel-header">TRANSACTION &amp; CUSTOMER SNAPSHOT</div>', unsafe_allow_html=True)

snap_col1, snap_col2 = st.columns([1.4, 1.0], gap="large")

with snap_col1:
    ip_val = tx.get("ip_address") or "—"
    geo_val = tx.get("geo_location") or "—"
    device_val = tx.get("device_id") or "—"
    network_val = tx.get("network_type") or "Standard"
    home_geo = tx.get("sender_home_geo") or "—"
    typical_max = tx.get("sender_typical_max") or tx.get("user_max_transfer") or 0
    expense_type = tx.get("expense_type") or tx.get("expenditure_model") or "Personal Account"
    if expense_type == "personal_consumption":
        expense_type = "Personal Account"
    elif expense_type == "opex_heavy":
        expense_type = "Small Business / OpEx"
    elif expense_type == "capex_heavy":
        expense_type = "Enterprise / CapEx"

    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:16px 20px;font-size:0.83rem">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-size:0.68rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.05em">Transaction ID:</span>
      <span style="font-weight:700;color:#21D4C2;font-family:monospace;font-size:0.95rem;margin-left:6px">{tx['id']}</span>
    </div>
    <div>
      <span style="font-size:0.68rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.05em">Initiated (UTC):</span>
      <span style="color:#CBD5E1;font-family:monospace;margin-left:6px">{fmt_ts(tx.get('timestamp',''))}</span>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:10px 14px">
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;margin-bottom:3px">Sender (Account Owner)</div>
      <div style="font-weight:600;color:#F1F5F9;font-size:0.88rem">{tx.get('sender_name','—')}</div>
      <div style="color:#67E8F9;font-family:monospace;font-size:0.75rem">{tx.get('sender_id','—')}</div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:10px 14px">
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase;margin-bottom:3px">Beneficiary (Recipient)</div>
      <div style="font-weight:600;color:#F1F5F9;font-size:0.88rem">{tx.get('beneficiary_name','—')}</div>
      <div style="color:#94A3B8;font-family:monospace;font-size:0.75rem">{tx.get('beneficiary_id','—')}</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:10px;font-size:0.76rem">
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 10px">
      <div style="color:#8A9CB0;font-size:0.65rem;text-transform:uppercase">Session IP &amp; Geo</div>
      <div style="color:#CBD5E1;font-family:monospace;font-weight:600;margin-top:2px">{ip_val}</div>
      <div style="color:#94A3B8">{geo_val}</div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 10px">
      <div style="color:#8A9CB0;font-size:0.65rem;text-transform:uppercase">Device &amp; Network</div>
      <div style="color:#CBD5E1;font-family:monospace;margin-top:2px">{device_val[:16]}</div>
      <div style="color:#94A3B8">{network_val}</div>
    </div>
    <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 10px">
      <div style="color:#8A9CB0;font-size:0.65rem;text-transform:uppercase">Customer Baseline</div>
      <div style="color:#CBD5E1;margin-top:2px">Home: <b>{home_geo}</b></div>
      <div style="color:#94A3B8">Type: <b>{expense_type}</b></div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

with snap_col2:
    bal_color = "#10B981" if bal_deducted_flag else "#F59E0B"
    bal_label = "Debited from Account" if bal_deducted_flag else "Funds Held (Not Debited)"

    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:16px 20px;height:100%;display:flex;flex-direction:column;justify-content:space-between">
  <div>
    <div style="font-size:0.68rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.05em">Transfer Amount</div>
    <div style="font-size:1.6rem;font-weight:700;color:#F1F5F9;font-family:monospace;margin-top:2px">{fmt_currency(tx['amount'])}</div>
    <div style="color:#8A9CB0;font-size:0.75rem;margin-top:4px">Typical Max Baseline: <b style="color:#CBD5E1">{fmt_currency(typical_max) if typical_max else '—'}</b></div>
  </div>
  <div style="margin-top:14px;padding-top:12px;border-top:1px solid #1E2D3B">
    <div style="font-size:0.68rem;color:#8A9CB0;text-transform:uppercase;margin-bottom:4px">Lifecycle Status</div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      {status_badge_html(raw_tx_status)}
      <span style="font-size:0.75rem;font-weight:600;color:{bal_color}">• {bal_label}</span>
    </div>
  </div>
  <div style="margin-top:14px">
    <a href="pages/4_forensic_investigation.py" style="text-decoration:none">
      <div style="background:#13202B;border:1px solid #223342;border-radius:6px;padding:8px 12px;text-align:center;font-size:0.76rem;color:#21D4C2;font-weight:600">
        🔬 View Full Chronological Evidence Timeline in Page 3 →
      </div>
    </a>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.divider()

# ── Risk Explanation & Primary Operational Score ───────────────────────────
st.markdown('<div class="panel-header">RISK EXPLANATION &amp; TRIGGERED SECURITY RULES</div>', unsafe_allow_html=True)

# We present the primary operational engine (Method 3: Contextual + Threat Intelligence)
op_score_info = scores.get("method3", scores.get("method2", {}))
risk_score = op_score_info.get("score", tx.get("risk_score", 0))
risk_level = op_score_info.get("level", "Low")
score_color = RISK_COLOR_MAP.get(risk_level, "#8A9CB0")
triggered_rules = op_score_info.get("triggered_rules", [])

r_col1, r_col2 = st.columns([1.1, 1.9], gap="large")

with r_col1:
    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:18px 20px;text-align:center">
  <div style="font-size:0.68rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.06em">Live Risk Score</div>
  <div style="font-size:3.0rem;font-weight:800;color:{score_color};font-family:monospace;line-height:1.1;margin:6px 0">
    {risk_score}<span style="font-size:1.2rem;color:#8A9CB0">/100</span>
  </div>
  <div style="display:inline-block;padding:4px 14px;border-radius:12px;background:{score_color}22;border:1px solid {score_color}66;font-size:0.8rem;font-weight:700;color:{score_color};text-transform:uppercase;letter-spacing:0.05em">
    {risk_level} Severity
  </div>
  <div style="color:#CBD5E1;font-size:0.78rem;margin-top:12px;line-height:1.45;text-align:left;border-top:1px solid #1E2D3B;padding-top:10px">
    <b>Reasoning:</b> {scores.get('comparison_narrative', op_score_info.get('description', 'Evaluated against contextual behavioral baseline.'))}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Counterfactual Analysis ("What would lower this score?")
    cf = scores.get("counterfactual", {})
    if cf and cf.get("hypothetical_change"):
        st.markdown(
            f"""
<div style="background:#0D1522;border:1px solid #223342;border-left:4px solid #8B5CF6;border-radius:8px;padding:14px 16px;margin-top:12px">
  <div style="font-size:0.68rem;color:#A78BFA;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">
    💡 What Would Lower This Score?
  </div>
  <div style="font-size:0.8rem;color:#F1F5F9;line-height:1.45;margin-bottom:8px">
    {cf.get('hypothetical_change')}
  </div>
  <div style="font-size:0.74rem;color:#CBD5E1">
    Projected Score: <b style="color:#A78BFA;font-family:monospace;font-size:0.88rem">{cf.get('projected_method3_score', '—')}/100</b>
    (from {risk_score}/100)
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

with r_col2:
    st.markdown(
        f'<div style="font-size:0.78rem;color:#8A9CB0;font-weight:600;margin-bottom:8px;text-transform:uppercase">'
        f'Triggered Rules ({len(triggered_rules)})'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not triggered_rules:
        st.markdown(
            """
<div style="padding:16px;background:#07291B;border:1px solid #10B98155;border-radius:8px;color:#6EE7B7;font-size:0.84rem">
  ✓ <b>Zero Anomalies Detected:</b> All contextual baseline and security checks passed cleanly.
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        table_rows = ""
        for r in triggered_rules:
            pts = r.get("points_awarded", 0)
            max_pts = r.get("max_points", pts)
            pt_col = "#EF4444" if pts >= 25 else ("#F59E0B" if pts > 0 else "#94A3B8")
            r_name = r.get("rule_name", r.get("rule_id", "Rule"))
            explanation = r.get("explanation", "—")
            table_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:10px 12px;font-size:0.82rem;font-weight:600;color:#F1F5F9">{r_name}</td>
  <td style="padding:10px 12px;text-align:center;font-weight:700;color:{pt_col};font-family:monospace;font-size:0.82rem">+{pts} / {max_pts}</td>
  <td style="padding:10px 12px;font-size:0.79rem;color:#CBD5E1;line-height:1.4">{explanation}</td>
</tr>"""

        st.markdown(
            f"""
<div style="border:1px solid #223342;border-radius:8px;overflow:hidden">
<table style="width:100%;border-collapse:collapse;background:#0E1720">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:8px 12px;text-align:left;font-size:0.68rem;color:#8A9CB0;text-transform:uppercase">Rule Name</th>
      <th style="padding:8px 12px;text-align:center;font-size:0.68rem;color:#8A9CB0;text-transform:uppercase">Points</th>
      <th style="padding:8px 12px;text-align:left;font-size:0.68rem;color:#8A9CB0;text-transform:uppercase">Detection Reason</th>
    </tr>
  </thead>
  <tbody>{table_rows}</tbody>
</table>
</div>
""",
            unsafe_allow_html=True,
        )

st.divider()

# ── Customer Out-of-Band Verification & Admin Authorization Panel ──────────
st.markdown('<div class="panel-header">CUSTOMER VERIFICATION &amp; TRANSFER AUTHORIZATION</div>', unsafe_allow_html=True)

if raw_tx_status == "COMPLETED":
    st.markdown(
        f"""
<div style="background:#07291B;border:1px solid #10B98155;border-left:4px solid #10B981;border-radius:8px;padding:16px 20px">
  <div style="font-size:0.92rem;font-weight:700;color:#10B981;margin-bottom:4px">✅ Transfer Completed &amp; Released</div>
  <div style="font-size:0.82rem;color:#CBD5E1">
    This transfer has been verified and authorized. Funds were debited from the sender's account exactly once and disbursed to the beneficiary.
  </div>
  <div style="font-size:0.75rem;color:#8A9CB0;margin-top:6px">
    <b>Resolution Details:</b> {tx.get('decision_reason', 'Authorized legitimate transfer.')}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
elif raw_tx_status == "BLOCKED":
    st.markdown(
        f"""
<div style="background:#2A0E12;border:1px solid #EF444455;border-left:4px solid #EF4444;border-radius:8px;padding:16px 20px">
  <div style="font-size:0.92rem;font-weight:700;color:#EF4444;margin-bottom:4px">🛑 Transfer Blocked &amp; Protected</div>
  <div style="font-size:0.82rem;color:#CBD5E1">
    This transfer was blocked due to confirmed security risk or customer denial. Funds were <b>never debited</b> and remain protected in the customer's account.
  </div>
  <div style="font-size:0.75rem;color:#8A9CB0;margin-top:6px">
    <b>Reason:</b> {tx.get('decision_reason', 'Blocked due to suspicious activity.')}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
else:
    # Transaction is HELD or PENDING
    st.markdown(
        """
<p style="color:#8A9CB0;font-size:0.82rem;margin-bottom:12px">
  This transfer is currently held. In production banking operations, high-risk holds require contacting the account owner
  via a trusted, registered channel (such as verified phone call or registered email) to authenticate transfer intent
  before release.
</p>
""",
        unsafe_allow_html=True,
    )

    flow_col1, flow_col2 = st.columns([1.2, 1.2], gap="large")

    with flow_col1:
        st.markdown("**1. Out-of-Band Customer Verification**")
        verification_status = st.radio(
            "Contact Result with Account Holder",
            options=[
                "Customer Confirmed (Genuine transfer intent confirmed)",
                "Customer Denied (Fraudulent or unauthorized activity)",
                "Customer Unreachable (Maintain security hold)",
            ],
            index=0,
            key=f"cust_ver_radio_{selected_tx_id}",
        )

        if "Confirmed" in verification_status:
            st.info(
                "✓ **Customer Confirmed:** Account holder confirmed initiating this transfer. "
                "You may authorize release. Balance will be revalidated and debited exactly once."
            )
        elif "Denied" in verification_status:
            st.error(
                "🚨 **Customer Denied:** Account holder reported unauthorized activity. "
                "Blocking will keep funds in the customer's account and create a formal forensic incident."
            )
        else:
            st.warning(
                "🔒 **Customer Unreachable:** Under TRACE-Fin security policy, transfers cannot be released "
                "without positive confirmation. Funds remain held safely."
            )

    with flow_col2:
        st.markdown("**2. Administrator Decision &amp; Audit Trail**")
        default_note = (
            "Contacted account holder via registered contact; confirmed genuine transfer intent."
            if "Confirmed" in verification_status
            else (
                "Account holder confirmed unauthorized transaction; blocked to protect account balance."
                if "Denied" in verification_status
                else "Attempted customer contact via registered phone; customer unreachable. Maintained hold."
            )
        )
        admin_note = st.text_input(
            "Investigation Audit Note (Mandatory)",
            value=default_note,
            key=f"admin_note_input_{selected_tx_id}",
        )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if "Confirmed" in verification_status:
            if st.button(
                "✅ Authorize & Release Transfer",
                key=f"btn_release_{selected_tx_id}",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Authorizing and releasing transfer..."):
                    res = submit_admin_transaction_decision_live(selected_tx_id, "approve", admin_note)
                    if res["ok"]:
                        st.success(f"Transfer {selected_tx_id} successfully authorized! Balance debited.")
                        st.rerun()
                    else:
                        st.error(res.get("error", "Failed to authorize transfer."))
        elif "Denied" in verification_status:
            if st.button(
                "🛑 Confirm Fraud & Block Transfer",
                key=f"btn_block_{selected_tx_id}",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Blocking transfer and creating incident..."):
                    res = submit_admin_transaction_decision_live(selected_tx_id, "block", admin_note)
                    if res["ok"]:
                        inc_id = (res.get("data") or {}).get("linked_incident_id")
                        st.warning(
                            f"Transfer {selected_tx_id} blocked. Funds protected in customer balance. "
                            f"Forensic incident {inc_id or ''} created."
                        )
                        st.rerun()
                    else:
                        st.error(res.get("error", "Failed to block transfer."))
        else:
            st.button(
                "🔒 Cannot Release While Unreachable",
                disabled=True,
                use_container_width=True,
                help="Customer verification is required before releasing held funds.",
            )
