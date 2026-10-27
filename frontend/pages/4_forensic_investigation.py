"""
PAGE 4 — Forensic Investigation
Interactive Kill-Chain evidence timeline for ALL 500+ SQLite transactions,
telemetry completeness check, and live transaction verification & SHA-256 incident creation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_evidence_timeline,
    get_evidence_timeline_metadata,
    get_incidents,
    get_risk_scores,
    get_scenario_summary,
    get_transaction,
    get_transactions,
    verify_transaction,
)
from ui.components import (
    RISK_COLOR_MAP,
    fmt_currency,
    inject_css,
    render_demo_banner,
    render_timeline,
)

inject_css()
render_demo_banner()

st.markdown("<h1>Forensic Investigation &amp; Kill-Chain Reconstruction</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Reconstruct the chronological attack lifecycle across authentication, device, beneficiary, threat-intelligence, '
    'and transaction tables in SQLite. Explicitly separates <b>Recorded Database Telemetry</b> from '
    '<b>System Forensic Inference</b>, and executes live verification &amp; SHA-256 incident escalation.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Transaction Selector (Supports ALL 500+ SQLite Transactions) ──────────
all_txs = get_transactions()
all_tx_ids = [t["id"] for t in all_txs]
scenarios = get_scenario_summary()

sel_col1, sel_col2 = st.columns([2.2, 2.8], gap="large")

with sel_col1:
    scen_map = {
        f"{s['id']} · {s['name']} [{s['tx_id']}]": s["tx_id"]
        for s in scenarios
    }
    scen_options = ["-- Select Scenario Case or Use Full Selector --"] + list(scen_map.keys())

    def _on_for_preset() -> None:
        lbl = st.session_state.get("for_preset_sel")
        if lbl and lbl in scen_map:
            st.session_state["selected_tx_id"] = scen_map[lbl]
            st.session_state["forensic_tx_select"] = scen_map[lbl]

    st.selectbox(
        "Quick Scenario Case Selector",
        options=scen_options,
        index=0,
        key="for_preset_sel",
        on_change=_on_for_preset,
    )

with sel_col2:
    default_tx = st.session_state.get("selected_tx_id", all_tx_ids[0] if all_tx_ids else "TX-0391")
    if default_tx not in all_tx_ids and all_tx_ids:
        default_tx = all_tx_ids[0]
    default_idx = all_tx_ids.index(default_tx) if default_tx in all_tx_ids else 0

    def _on_for_tx_change() -> None:
        st.session_state["selected_tx_id"] = st.session_state["forensic_tx_select"]

    selected_case = st.selectbox(
        "Investigation Case (⚡ Live-Created Shown First, Then Historical Ledger)",
        options=all_tx_ids,
        index=default_idx,
        format_func=lambda tid: (
            f"{'⚡ LIVE CREATED · ' if get_transaction(tid).get('is_live_created') else ''}"
            f"{tid} · {get_transaction(tid)['sender_name'][:20]} → "
            f"{get_transaction(tid)['beneficiary_name'][:18]} · "
            f"{fmt_currency(get_transaction(tid)['amount'])} (M3={get_transaction(tid)['method3_score']})"
        ),
        key="forensic_tx_select",
        on_change=_on_for_tx_change,
    )

st.session_state["selected_tx_id"] = selected_case

tx = get_transaction(selected_case)
scores = get_risk_scores(selected_case)
events = get_evidence_timeline(selected_case)
tl_meta = get_evidence_timeline_metadata(selected_case)

if tx and scores:
    m1s = scores["method1"]["score"]
    m2s = scores["method2"]["score"]
    m3s = scores["method3"]["score"]
    col = RISK_COLOR_MAP.get(tx["method3_level"], "#8A9CB0")
    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;
padding:12px 18px;display:flex;gap:22px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin-top:8px">
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Case ID</span><br>
    <span style="font-size:0.95rem;font-weight:700;color:#21D4C2;font-family:monospace">{tx["id"]}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Sender Profile</span><br>
    <span style="font-size:0.86rem;font-weight:600;color:#F1F5F9">{tx["sender_name"]} ({tx["sender_expenditure_model"]})</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Amount</span><br>
    <span style="font-size:0.95rem;font-weight:700;color:#F1F5F9;font-family:monospace">{fmt_currency(tx["amount"])}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M1 / M2 / M3 Scores</span><br>
    <span style="font-size:0.92rem;font-weight:700;color:{col};font-family:monospace">{m1s} / {m2s} / {m3s}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Correlated Events</span><br>
    <span style="font-size:0.92rem;font-weight:700;color:#21D4C2;font-family:monospace">{len(events)} records</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Ground Truth</span><br>
    <span style="font-size:0.85rem;font-weight:700;color:{'#EF4444' if tx.get('ground_truth')==1 else '#10B981'}">
      {'⚠ ATTACK' if tx.get("ground_truth")==1 else '✓ LEGITIMATE'}
    </span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Timeline + Detail Panel ────────────────────────────────────────────────
tl_col, detail_col = st.columns([1.75, 1.15], gap="large")

with tl_col:
    st.markdown(
        '<div class="panel-header">UNIFIED CHRONOLOGICAL EVIDENCE TIMELINE &amp; KILL-CHAIN</div>',
        unsafe_allow_html=True,
    )
    render_timeline(events)

with detail_col:
    st.markdown(
        '<div class="panel-header">TELEMETRY COVERAGE &amp; FORENSIC SUMMARY</div>',
        unsafe_allow_html=True,
    )

    present_cats = tl_meta.get("present_categories", [])
    missing_cats = tl_meta.get("missing_categories", [])
    st.markdown("**Telemetry Categories Observed (`present_categories`)**")
    if present_cats:
        st.markdown(
            " ".join(
                f'<span style="display:inline-block;margin:2px 4px 4px 0;padding:2px 8px;border-radius:4px;'
                f'background:#07291B;color:#6EE7B7;border:1px solid #10B98155;font-size:0.7rem;font-family:monospace">✓ {c}</span>'
                for c in present_cats
            ),
            unsafe_allow_html=True,
        )
    if missing_cats:
        st.markdown("**Absent Telemetry Categories (`missing_categories`)**")
        st.markdown(
            " ".join(
                f'<span style="display:inline-block;margin:2px 4px 4px 0;padding:2px 8px;border-radius:4px;'
                f'background:#1E293B;color:#94A3B8;border:1px solid #334155;font-size:0.7rem;font-family:monospace">○ {c}</span>'
                for c in missing_cats
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    if tx and scores:
        st.markdown("**Triggered Forensic Explanations**")
        for reason in scores.get("alert_reasons", []):
            st.markdown(
                f'<div style="padding:7px 10px;background:#1A111E;border:1px solid #EF444433;'
                f'border-left:2.5px solid #EF4444;border-radius:5px;'
                f'font-size:0.77rem;color:#FCA5A5;margin-bottom:6px;line-height:1.4">▸ {reason}</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div style="font-size:0.67rem;color:#8A9CB0;font-weight:700;letter-spacing:0.07em;'
            'text-transform:uppercase;margin:12px 0 8px">ACTIVE RULE FLAGS</div>',
            unsafe_allow_html=True,
        )
        for flag in scores.get("evidence_flags", []):
            st.markdown(
                f'<div style="font-size:0.74rem;font-family:monospace;color:#21D4C2;'
                f'padding:3px 0;border-bottom:1px solid #1E2D3B">▸ {flag}</div>',
                unsafe_allow_html=True,
            )

st.divider()

# ── Live Transaction Verification & SHA-256 Incident Creation ─────────────
st.markdown(
    '<div class="panel-header">LIVE TRANSACTION VERIFICATION &amp; INCIDENT ESCALATION (FASTAPI + SQLITE)</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.8rem;margin-bottom:14px">'
    'Submit a verification response to <code>POST /verification-requests</code> &amp; <code>/respond</code>. '
    'Confirming fraud or escalating automatically persists an immutable forensic incident in SQLite with a '
    'canonical SHA-256 evidence snapshot hash.</p>',
    unsafe_allow_html=True,
)

vc1, vc2 = st.columns([2, 2], gap="large")
with vc1:
    analyst_note = st.text_area(
        "Verification / Investigator Audit Note",
        placeholder="E.g. Account holder denied initiating transfer; impossible travel and unseen device confirmed.",
        height=85,
        key="analyst_note_input",
    )
    outcome_choice = st.radio(
        "Verification Decision",
        options=["confirmed_fraud", "escalated", "cleared_legitimate"],
        format_func=lambda x: {
            "confirmed_fraud": "🔴 Deny & Open Critical Incident (Fraud)",
            "escalated": "🟡 Deny & Escalate to Investigating",
            "cleared_legitimate": "🟢 Approve as Confirmed Legitimate",
        }[x],
        horizontal=True,
        key="verification_outcome",
    )

with vc2:
    existing_incidents = [i for i in get_incidents() if i["tx_id"] == selected_case]
    if existing_incidents:
        st.markdown(
            f'<div style="padding:10px 14px;background:#082330;border:1px solid #21D4C255;'
            f'border-radius:7px;font-size:0.8rem;color:#67E8F9;margin-bottom:8px">'
            f'ℹ️ <b>{len(existing_incidents)}</b> SQLite incident record(s) linked to <code>{selected_case}</code>:</div>',
            unsafe_allow_html=True,
        )
        for inc in existing_incidents:
            st.markdown(
                f'<div style="padding:4px 0;font-size:0.76rem">'
                f'<code style="color:#21D4C2">{inc["incident_id"]}</code> · '
                f'<b>{inc["status"]}</b> · SHA-256: <code style="color:#94A3B8">{inc["sha256_hash"][:20]}…</code></div>',
                unsafe_allow_html=True,
            )

    if st.button("⚡ Execute Verification Decision in SQLite", key="submit_verification", type="primary", use_container_width=True):
        result = verify_transaction(selected_case, outcome_choice, analyst_note)
        if result["success"]:
            inc = result.get("incident")
            if inc:
                st.success(f"Incident **{inc['incident_id']}** persisted in SQLite! Open Incident Register to inspect.")
                st.markdown(
                    f'<div style="font-family:monospace;font-size:0.72rem;color:#8A9CB0;'
                    f'background:#070B10;padding:10px 12px;border-radius:6px;border:1px solid #223342;margin-top:8px">'
                    f'Canonical SHA-256 Evidence Hash:<br>'
                    f'<span style="color:#21D4C2">{inc["sha256_hash"]}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.success(f"Transaction **{selected_case}** marked as **Confirmed Legitimate** in SQLite (all forensic telemetry preserved).")
        else:
            st.warning(f"Verification response notice: {result.get('error')}")

st.divider()

# ── Evidence Report Export ─────────────────────────────────────────────────
if events and tx:
    report_lines = [
        "TRACE-Fin Forensic Evidence & Kill-Chain Report",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Case ID: {selected_case}",
        f"Sender: {tx.get('sender_name','—')} ({tx.get('sender_profile','—')} / {tx.get('sender_expenditure_model','—')})",
        f"Beneficiary: {tx.get('beneficiary_name','—')} ({tx.get('beneficiary_category','—')})",
        f"Amount: {fmt_currency(tx['amount'])}",
        f"Scores: M1={tx.get('method1_score')} | M2={tx.get('method2_score')} | M3={tx.get('method3_score')}",
        "",
        f"CHRONOLOGICAL EVIDENCE TIMELINE ({len(events)} SQLite records)",
        "─" * 72,
    ]
    for ev in events:
        report_lines.extend(
            [
                f"[{ev.get('timestamp','')}] {ev.get('event_type','')} | Phase: {ev.get('phase','')} | Severity: {ev.get('severity','')}",
                f"  Recorded Fact: {ev.get('recorded_fact','')}",
                f"  System Interp: {ev.get('system_interpretation','')}",
                f"  Provenance:    {ev.get('source','')} ({ev.get('entity','')})",
                "",
            ]
        )
    st.download_button(
        label="⬇ Export Forensic Case Report (.txt)",
        data="\n".join(report_lines),
        file_name=f"tracefin_forensic_report_{selected_case}.txt",
        mime="text/plain",
        key="evidence_export",
    )
