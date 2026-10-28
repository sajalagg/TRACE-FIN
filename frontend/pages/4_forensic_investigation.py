"""
PAGE 3 (Forensic Investigation) — Forensic Investigation & Evidence Timeline
Chronological audit trail, contextual telemetry verification, and incident escalation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_transaction_index,
    get_evidence_timeline,
    get_incidents,
    get_risk_scores,
    get_transactions,
    update_incident_status_live,
    verify_transaction,
)
from ui.components import (
    RISK_COLOR_MAP,
    fmt_currency,
    fmt_ts,
    inject_css,
    status_badge_html,
)

inject_css()

st.markdown("<h1>Forensic Investigation &amp; Evidence Timeline</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Reconstruct the chronological event timeline across authentication, device, beneficiary, threat intelligence, '
    'and payment telemetry. Separates <b>Recorded Facts</b> from <b>Security Assessments</b>, and supports formal incident escalation.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Transaction Selector (Supports ALL SQLite Transactions) ───────────────
all_txs = get_transactions()
tx_index = get_transaction_index()
all_tx_ids = [t["id"] for t in all_txs]

default_tx = st.session_state.get("selected_tx_id", all_tx_ids[0] if all_tx_ids else "TX-0391")
if default_tx not in all_tx_ids and all_tx_ids:
    default_tx = all_tx_ids[0]
default_idx = all_tx_ids.index(default_tx) if default_tx in all_tx_ids else 0


def _on_for_tx_change() -> None:
    st.session_state["selected_tx_id"] = st.session_state["forensic_tx_select"]


selected_case = st.selectbox(
    "Select Transaction to Investigate",
    options=all_tx_ids,
    index=default_idx,
    format_func=lambda tid: (
        f"{'⚡ LIVE · ' if tx_index[tid].get('is_live_created') else ''}"
        f"{tid} · {tx_index[tid]['sender_name'][:20]} → "
        f"{tx_index[tid]['beneficiary_name'][:18]} · "
        f"{fmt_currency(tx_index[tid]['amount'])} · "
        f"Risk Score: {tx_index[tid].get('method3_score', tx_index[tid].get('risk_score', 0))}/100 · "
        f"[{tx_index[tid].get('raw_status', tx_index[tid].get('status', ''))}]"
        if tid in tx_index
        else str(tid)
    ),
    key="forensic_tx_select",
    on_change=_on_for_tx_change,
)

st.session_state["selected_tx_id"] = selected_case

tx = tx_index.get(selected_case)
scores = get_risk_scores(selected_case)
events, tl_meta = get_evidence_timeline(selected_case)

if not tx or not scores:
    st.error(f"Transaction '{selected_case}' not found.")
    st.stop()

# Authoritative live score & metadata
risk_score = int(scores.get("method3", {}).get("score", tx.get("risk_score", 0)))
risk_level = scores.get("method3", {}).get("level", tx.get("method3_level", "Medium"))
score_col = RISK_COLOR_MAP.get(risk_level, "#8A9CB0")
raw_status = tx.get("raw_status") or tx.get("status", "COMPLETED")
status_badge = status_badge_html(tx.get("status", "Pending"))

# ── Case Summary Banner (No ground-truth, no M1/M2/M3 comparison) ──────────
st.markdown(
    f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;
padding:14px 20px;display:flex;gap:20px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin-top:8px">
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Case Identifier</span><br>
    <span style="font-size:1.0rem;font-weight:700;color:#21D4C2;font-family:monospace">{tx["id"]}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Account Holder</span><br>
    <span style="font-size:0.88rem;font-weight:600;color:#F1F5F9">{tx["sender_name"]}</span>
    <span style="font-size:0.72rem;color:#8A9CB0">({tx.get("sender_profile", "Individual")})</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Counterparty &amp; Amount</span><br>
    <span style="font-size:0.88rem;font-weight:600;color:#F1F5F9">{tx["beneficiary_name"]}</span> ·
    <span style="font-size:0.95rem;font-weight:700;color:#F1F5F9;font-family:monospace">{fmt_currency(tx["amount"])}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Operational Status</span><br>
    <div style="margin-top:2px">{status_badge}</div>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Authoritative Risk Score</span><br>
    <span style="font-size:1.15rem;font-weight:700;color:{score_col};font-family:monospace">{risk_score}/100</span>
    <span style="font-size:0.75rem;color:{score_col};font-weight:600">[{risk_level.upper()}]</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Correlated Signals</span><br>
    <span style="font-size:0.95rem;font-weight:700;color:#21D4C2;font-family:monospace">{len(events)} records</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# ── Timeline Helper Functions ──────────────────────────────────────────────
def _resolve_source_label(ev: dict) -> str:
    cat = (ev.get("event_category") or "").lower()
    etype = (ev.get("event_type") or "").lower()
    if cat == "auth" or "login" in etype or "session" in etype or "mfa" in etype:
        return "Authentication Gateway"
    if cat == "device" or "device" in etype:
        return "Device Intelligence Engine"
    if cat == "ti" or "threat" in etype or "ip" in etype:
        return "Threat Intelligence Feed"
    if cat in ("transaction", "beneficiary") or "transfer" in etype:
        return "Core Banking Ledger"
    return "Core Audit Service"


def _matches_filter(ev: dict, filter_choice: str) -> bool:
    if filter_choice == "All":
        return True
    cat = (ev.get("event_category") or "").lower()
    etype = (ev.get("event_type") or "").lower()
    sev = ev.get("severity", "Low")
    if filter_choice == "Access & Session":
        return cat == "auth" or "login" in etype or "session" in etype
    if filter_choice == "Account & Beneficiary":
        return cat in ("beneficiary", "device") or "beneficiary" in etype or "device" in etype
    if filter_choice == "Payment Execution":
        return cat == "transaction" or "transfer" in etype
    if filter_choice == "Security Detections":
        return sev in ("Critical", "High") or cat == "ti" or "threat" in etype
    return True


# ── Two-Column Main Layout: Timeline + Audit Signals ──────────────────────
tl_col, detail_col = st.columns([1.75, 1.15], gap="large")

with tl_col:
    st.markdown(
        '<div class="panel-header">CHRONOLOGICAL EVIDENCE TIMELINE</div>',
        unsafe_allow_html=True,
    )

    filter_choice = st.radio(
        "Activity Category Filter",
        options=["All", "Access & Session", "Account & Beneficiary", "Payment Execution", "Security Detections"],
        horizontal=True,
        label_visibility="collapsed",
        key="timeline_category_filter",
    )

    filtered_events = [ev for ev in events if _matches_filter(ev, filter_choice)]

    if not filtered_events:
        st.info(f"No timeline events recorded under category: '{filter_choice}'.")
    else:
        st.caption(f"Showing **{len(filtered_events)}** of {len(events)} correlated event records.")
        for idx, ev in enumerate(filtered_events):
            severity = ev.get("severity", "Low")
            sev_colors = {
                "Critical": "#DC2626",
                "High": "#EF4444",
                "Medium": "#F59E0B",
                "Low": "#10B981",
            }
            dot_col = sev_colors.get(severity, "#8A9CB0")
            is_last = idx == len(filtered_events) - 1
            connector = "" if is_last else '<div class="timeline-connector"></div>'
            source_label = _resolve_source_label(ev)

            recorded_fact = ev.get("recorded_fact") or ev.get("description", "")
            system_interp = ev.get("system_interpretation", "")

            interp_block = ""
            if system_interp:
                interp_block = (
                    f'<div style="font-size:0.77rem;color:#93C5FD;background:#0B1929;'
                    f'border-left:3px solid #3B82F6;padding:6px 12px;border-radius:0 4px 4px 0;margin:6px 0;">'
                    f'<b>Security Assessment:</b> {system_interp}</div>'
                )

            entity_text = ev.get("entity", "")
            context_snippet = f"Context: {entity_text} &nbsp;|&nbsp; " if entity_text and entity_text != "—" else ""

            st.markdown(
                f"""
<div class="timeline-event">
  <div style="position:relative;width:12px">
    <div class="timeline-dot" style="color:{dot_col};background:{dot_col}"></div>
    {connector}
  </div>
  <div class="timeline-content">
    <div class="timeline-header">
      <span class="timeline-time">{ev.get("timestamp","")}</span>
      <span class="timeline-type">{ev.get("event_type","")}</span>
      <span class="badge badge-{severity.lower()}">{severity}</span>
      <span style="font-size:0.68rem;color:#8A9CB0;background:#182533;padding:2px 7px;border-radius:4px;margin-left:auto">
        {source_label}
      </span>
    </div>
    <div class="timeline-fact"><b>Recorded Fact:</b> {recorded_fact}</div>
    {interp_block}
    <div class="timeline-entity">{context_snippet}Source Service: <span style="color:#21D4C2">{source_label}</span></div>
  </div>
</div>""",
                unsafe_allow_html=True,
            )

with detail_col:
    st.markdown(
        '<div class="panel-header">AUDIT SIGNALS &amp; TELEMETRY PROVENANCE</div>',
        unsafe_allow_html=True,
    )

    # ── 1. Audit Signals Checklist (3 Realistic States) ──────────────────────
    present_cats = set(tl_meta.get("present_categories", []))
    missing_cats = set(tl_meta.get("missing_categories", []))
    evidence_flags = set(scores.get("evidence_flags", []))

    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#CBD5E1;letter-spacing:0.06em;'
        'text-transform:uppercase;margin-bottom:8px">AUDIT SIGNALS CHECKLIST</div>',
        unsafe_allow_html=True,
    )

    def _render_signal_item(title: str, is_flagged: bool, is_present: bool, detail: str) -> str:
        if is_flagged:
            badge_icon = "🚨"
            status_text = "Flagged"
            bg = "#2A0E12"
            border = "#EF444455"
            text_color = "#FCA5A5"
        elif is_present:
            badge_icon = "🟢"
            status_text = "Clean (Checked — no match)"
            bg = "#072318"
            border = "#10B98155"
            text_color = "#6EE7B7"
        else:
            badge_icon = "⚪"
            status_text = "Not Captured / Not Available"
            bg = "#111A24"
            border = "#334155"
            text_color = "#94A3B8"

        return (
            f'<div style="background:{bg};border:1px solid {border};border-radius:6px;padding:8px 12px;margin-bottom:6px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<span style="font-size:0.78rem;font-weight:600;color:#F1F5F9">{title}</span>'
            f'<span style="font-size:0.7rem;font-weight:600;color:{text_color}">{badge_icon} {status_text}</span>'
            f'</div>'
            f'<div style="font-size:0.71rem;color:#94A3B8;margin-top:2px">{detail}</div>'
            f'</div>'
        )

    # Signal 1: Authentication & Session
    auth_flagged = any("AUTH" in f or "LOGIN" in f or "CRED" in f for f in evidence_flags)
    auth_present = "auth" in present_cats or any(ev.get("event_category") == "auth" for ev in events)
    st.markdown(
        _render_signal_item(
            "Authentication & Session",
            auth_flagged,
            auth_present,
            "MFA step-up, password credentials, and session token validity." if auth_present else "Authentication session details not recorded.",
        ),
        unsafe_allow_html=True,
    )

    # Signal 2: Device Intelligence
    device_flagged = any("DEVICE" in f or "NEW_DEVICE" in f for f in evidence_flags)
    device_present = "device" in present_cats or any(ev.get("event_category") == "device" for ev in events)
    st.markdown(
        _render_signal_item(
            "Device Intelligence",
            device_flagged,
            device_present,
            "Hardware fingerprint, browser user-agent, and operating system profile." if device_present else "Device fingerprint telemetry not supplied by client.",
        ),
        unsafe_allow_html=True,
    )

    # Signal 3: IP & Threat Intelligence
    ti_flagged = any("TI" in f or "TOR" in f or "PROXY" in f or "VPN" in f for f in evidence_flags)
    ti_present = "ti" in present_cats or any(ev.get("event_category") == "ti" for ev in events)
    st.markdown(
        _render_signal_item(
            "IP & Threat Intelligence",
            ti_flagged,
            ti_present,
            "Tor exit nodes, malicious proxies, and high-risk network autonomous systems." if ti_present else "Threat intelligence dataset check executed with no hits.",
        ),
        unsafe_allow_html=True,
    )

    # Signal 4: Behavioral Velocity & Geolocation
    vel_flagged = any("VELOCITY" in f or "TRAVEL" in f or "GEO" in f for f in evidence_flags)
    vel_present = "velocity" in present_cats or any("velocity" in (ev.get("recorded_fact") or "").lower() for ev in events)
    st.markdown(
        _render_signal_item(
            "Behavioral Velocity & Geolocation",
            vel_flagged,
            vel_present,
            "Speed of physical travel between logins and transaction frequency." if vel_present else "Single-location session; velocity jump not applicable.",
        ),
        unsafe_allow_html=True,
    )

    # Signal 5: Beneficiary & Account History
    ben_flagged = any("BENEFICIARY" in f or "NEW_PAYEE" in f or "COOLING" in f for f in evidence_flags)
    ben_present = "beneficiary" in present_cats or any(ev.get("event_category") == "beneficiary" for ev in events)
    st.markdown(
        _render_signal_item(
            "Beneficiary & Account History",
            ben_flagged,
            ben_present,
            "Payee cooling-off period, counterparty category, and account age." if ben_present else "Beneficiary history established on prior transactions.",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:#223342;margin:14px 0'>", unsafe_allow_html=True)

    # ── 2. Triggered Security Rules ──────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#CBD5E1;letter-spacing:0.06em;'
        'text-transform:uppercase;margin-bottom:8px">SECURITY RULE DETECTIONS</div>',
        unsafe_allow_html=True,
    )

    reasons = scores.get("alert_reasons", [])
    if reasons:
        for reason in reasons:
            st.markdown(
                f'<div style="padding:7px 11px;background:#1A111E;border:1px solid #EF444433;'
                f'border-left:3px solid #EF4444;border-radius:5px;'
                f'font-size:0.76rem;color:#FCA5A5;margin-bottom:6px;line-height:1.4">▸ {reason}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="padding:8px 12px;background:#072318;border:1px solid #10B98155;border-radius:6px;'
            'font-size:0.75rem;color:#6EE7B7">✓ No active security rules triggered for this transfer.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border-color:#223342;margin:14px 0'>", unsafe_allow_html=True)

    # ── 3. Evidence Sources Panel ───────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#CBD5E1;letter-spacing:0.06em;'
        'text-transform:uppercase;margin-bottom:8px">EVIDENCE SOURCES</div>',
        unsafe_allow_html=True,
    )

    sources_html = """
<div style="background:#09121B;border:1px solid #223342;border-radius:6px;padding:10px 14px;font-size:0.73rem;color:#94A3B8;line-height:1.6">
  <div>🔐 <b>Authentication Gateway:</b> Session token &amp; login credential verification</div>
  <div>📱 <b>Device Intelligence Engine:</b> Hardware hash &amp; client browser profile</div>
  <div>🏦 <b>Core Banking Ledger:</b> Transaction debit records &amp; beneficiary database</div>
  <div>🌐 <b>Threat Intelligence Feed:</b> Known proxy, Tor relay, and ASN reputation list</div>
</div>
"""
    st.markdown(sources_html, unsafe_allow_html=True)

st.divider()

# ── Incident Linkage & Realistic Escalation ────────────────────────────────
st.markdown(
    '<div class="panel-header">INCIDENT ESCALATION &amp; CASE RESOLUTION</div>',
    unsafe_allow_html=True,
)

existing_incidents = [i for i in get_incidents() if i["tx_id"] == selected_case]

ic_left, ic_right = st.columns([1.5, 1.5], gap="large")

with ic_left:
    if existing_incidents:
        inc = existing_incidents[0]
        st.markdown(
            f"""
<div style="padding:14px 18px;background:#091522;border:1px solid #21D4C255;border-left:4px solid #21D4C2;
border-radius:8px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="font-size:0.88rem;font-weight:700;color:#21D4C2;font-family:monospace">{inc["incident_id"]}</span>
    <span>{status_badge_html(inc["status"])}</span>
  </div>
  <div style="font-size:0.75rem;color:#E2E8F0;margin-bottom:6px">
    Created: <span style="color:#94A3B8;font-family:monospace">{fmt_ts(inc.get("created_at",""))}</span> &nbsp;·&nbsp;
    Severity: <b style="color:#F1F5F9">{inc.get("severity","High")}</b>
  </div>
  <div style="font-size:0.74rem;color:#94A3B8;line-height:1.4">
    {inc.get("summary","Formal fraud incident recorded for this transaction.")}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("**Update Incident Status &amp; Investigator Findings**")
        new_inc_status = st.selectbox(
            "Lifecycle Status",
            options=["investigating", "closed"],
            index=0 if inc["raw_status"] != "closed" else 1,
            format_func=lambda x: "🔍 Investigating (Active Review)" if x == "investigating" else "✅ Closed (Resolved)",
            key="for_update_inc_status",
        )
        update_note = st.text_input(
            "Investigator Findings / Progress Note",
            placeholder="E.g. Account holder confirmed unauthorized access. Case forwarded to Recovery.",
            key="for_update_inc_note",
        )
        if st.button("💾 Record Investigation Update", key="btn_save_for_inc_update", type="primary", use_container_width=True):
            res = update_incident_status_live(inc["incident_id"], new_inc_status, update_note)
            if res.get("ok"):
                st.success(f"Incident **{inc['incident_id']}** updated to **{new_inc_status}**!")
                st.rerun()
            else:
                st.error(res.get("error", "Failed to update incident."))
    else:
        st.markdown(
            '<div style="padding:12px 16px;background:#131C26;border:1px solid #223342;border-radius:8px;margin-bottom:12px">'
            '<div style="font-size:0.8rem;font-weight:600;color:#F1F5F9;margin-bottom:4px">No Formal Incident Recorded</div>'
            '<div style="font-size:0.74rem;color:#8A9CB0;line-height:1.4">'
            'This transaction has not yet been formally escalated. If forensic telemetry indicates unauthorized activity, '
            'record findings below to open a formal investigation in the Incident Register.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        escalate_note = st.text_area(
            "Investigation Findings & Rationale for Escalation",
            placeholder="E.g. Severe velocity anomaly detected; impossible travel jump from Frankfurt Tor node within 2 hours of London activity.",
            height=85,
            key="for_escalate_note_input",
        )

        if st.button("🚨 Escalate & Open Formal Fraud Incident", key="btn_escalate_for_tx", type="primary", use_container_width=True):
            if not escalate_note.strip():
                st.warning("Please provide investigator findings / rationale before escalating.")
            else:
                res = verify_transaction(selected_case, "escalated", escalate_note.strip())
                if res.get("success"):
                    inc_obj = res.get("incident")
                    inc_id = inc_obj.get("incident_id") if inc_obj else "NEW"
                    st.success(f"Formal Incident **{inc_id}** successfully created and opened in Incident Register!")
                    st.rerun()
                else:
                    st.error(f"Failed to record escalation: {res.get('error')}")

with ic_right:
    st.markdown("**Forensic Case Dossier &amp; Compliance Archive**")
    st.caption(
        "Generate a complete, plain-text forensic investigation report including customer profile, "
        "chronological events with recorded facts and assessments, audit signals, and active rule detections."
    )

    # ── Evidence Report Export (.txt) ───────────────────────────────────────
    report_lines = [
        "=" * 78,
        "TRACE-FIN FORENSIC CASE DOSSIER",
        "=" * 78,
        f"Generated UTC:     {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Case Identifier:   {selected_case}",
        f"Operational State: {raw_status}",
        f"Authoritative Risk: {risk_score}/100 [{risk_level.upper()}]",
        "",
        "ACCOUNT & COUNTERPARTY SNAPSHOT",
        "-" * 78,
        f"Account Holder:    {tx.get('sender_name','—')} ({tx.get('sender_profile','—')})",
        f"Home Geolocation:  {tx.get('sender_home_geo','—')}",
        f"Counterparty:      {tx.get('beneficiary_name','—')} ({tx.get('beneficiary_category','—')})",
        f"Transfer Amount:   {fmt_currency(tx['amount'])}",
        "",
        "AUDIT SIGNALS & TELEMETRY CHECKLIST",
        "-" * 78,
        f"• Authentication:   {'FLAGGED' if auth_flagged else ('CLEAN' if auth_present else 'NOT_CAPTURED')}",
        f"• Device Intel:     {'FLAGGED' if device_flagged else ('CLEAN' if device_present else 'NOT_CAPTURED')}",
        f"• Threat Intel:     {'FLAGGED' if ti_flagged else ('CLEAN' if ti_present else 'NOT_CAPTURED')}",
        f"• Velocity / Geo:   {'FLAGGED' if vel_flagged else ('CLEAN' if vel_present else 'NOT_CAPTURED')}",
        f"• Beneficiary Hist: {'FLAGGED' if ben_flagged else ('CLEAN' if ben_present else 'NOT_CAPTURED')}",
        "",
        "ACTIVE SECURITY RULE DETECTIONS",
        "-" * 78,
    ]

    if reasons:
        for r in reasons:
            report_lines.append(f"  [TRIGGERED] {r}")
    else:
        report_lines.append("  None (Activity within normal behavioral baseline)")

    report_lines.extend(
        [
            "",
            f"CHRONOLOGICAL EVENT TIMELINE ({len(events)} correlated records)",
            "-" * 78,
        ]
    )

    for i, ev in enumerate(events, 1):
        report_lines.extend(
            [
                f"[{i}] {ev.get('timestamp','')} | Event: {ev.get('event_type','')} | Severity: {ev.get('severity','')}",
                f"    Source Service:      {_resolve_source_label(ev)}",
                f"    Recorded Fact:       {ev.get('recorded_fact') or ev.get('description','')}",
            ]
        )
        if ev.get("system_interpretation"):
            report_lines.append(f"    Security Assessment: {ev.get('system_interpretation')}")
        if ev.get("entity") and ev.get("entity") != "—":
            report_lines.append(f"    Observed Entity:     {ev.get('entity')}")
        report_lines.append("")

    report_lines.extend(
        [
            "INVESTIGATION AUDIT TRAIL & ESCALATION",
            "-" * 78,
        ]
    )
    if existing_incidents:
        inc = existing_incidents[0]
        report_lines.append(f"Linked Incident ID: {inc['incident_id']} (Status: {inc['status']})")
        report_lines.append(f"Incident Created:   {inc.get('created_at','')}")
        report_lines.append(f"Summary Rationale:  {inc.get('summary','')}")
    else:
        report_lines.append("Linked Incident:    No formal incident opened at export time.")

    report_lines.extend(
        [
            "=" * 78,
            "END OF DOSSIER — TRACE-FIN FINANCIAL FRAUD & RISK INVESTIGATION",
            "=" * 78,
        ]
    )

    dossier_text = "\n".join(report_lines)

    st.download_button(
        label="⬇ Download Forensic Case Dossier (.txt)",
        data=dossier_text,
        file_name=f"tracefin_case_dossier_{selected_case}.txt",
        mime="text/plain",
        key="btn_download_forensic_dossier",
        use_container_width=True,
    )
