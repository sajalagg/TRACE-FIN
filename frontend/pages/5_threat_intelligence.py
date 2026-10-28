"""
PAGE 5 — Threat Intelligence & Network Reputation
Freshness-aware threat intelligence indicators from SQLite, interactive registration of new indicators,
and direct correlation to customer transactions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import create_threat_indicator, get_threat_indicators, get_transaction
from ui.components import (
    fmt_currency,
    inject_css,
    plotly_layout_defaults,
    ti_badge_html,
)

inject_css()

st.markdown("<h1>Threat Intelligence &amp; Network Reputation</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Correlate real-time IP reputation feeds, Tor exit nodes, bulletproof proxies, and inter-bank mule registries. '
    'Enforces <b>automated freshness gating</b>: active indicators contribute risk points to transaction scoring, '
    'while expired indicators are safely suppressed to eliminate false positives on reassigned residential IPs.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Source & Category Formatting Helpers ──────────────────────────────────
def _clean_source_name(name: str) -> str:
    cleaned = name.replace("SIMULATED_DEMO_FEED_", "").replace("SIMULATED_DEMO_", "")
    mapping = {
        "TOR_EXIT": "Tor Exit Node Directory",
        "BOTNET_C2": "Botnet C2 Intelligence Feed",
        "VPN_SUSPECT": "Bulletproof VPN Watchlist",
        "STALE_2025": "Legacy ISP Pool (Expired)",
        "CONSORTIUM_MULE_LIST": "Inter-Bank Mule Consortium",
    }
    return mapping.get(cleaned, cleaned.replace("_", " ").title())


def _clean_category_name(cat: str) -> str:
    mapping = {
        "anonymizer_proxy_node": "Tor / Anonymizer Proxy",
        "credential_stuffing_botnet": "Botnet / Credential Stuffing",
        "bulletproof_hosting_vpn": "Bulletproof Hosting VPN",
        "historical_Residential_reassigned_ip": "Historical Reassigned IP",
        "historical_residential_reassigned_ip": "Historical Reassigned IP",
        "suspected_drop_beneficiary": "Suspected Mule Account",
    }
    return mapping.get(cat, cat.replace("_", " ").title())


# ── Sidebar Filters ─────────────────────────────────────────────────────────
st.sidebar.markdown(
    '<div style="font-size:0.68rem;color:#8A9CB0;font-weight:700;letter-spacing:0.08em;'
    'text-transform:uppercase;padding:4px 4px 6px">Threat Intel Filters</div>',
    unsafe_allow_html=True,
)

conf_filter = st.sidebar.multiselect(
    "Source Confidence",
    options=["High", "Medium", "Low"],
    default=["High", "Medium", "Low"],
    key="ti_conf_filter",
)
status_filter = st.sidebar.multiselect(
    "Freshness Status",
    options=["ACTIVE", "EXPIRED"],
    default=["ACTIVE", "EXPIRED"],
    key="ti_status_filter",
)
type_filter = st.sidebar.multiselect(
    "Indicator Type",
    options=["IP_ADDRESS", "BENEFICIARY_IBAN"],
    default=["IP_ADDRESS", "BENEFICIARY_IBAN"],
    format_func=lambda x: "IP Address" if x == "IP_ADDRESS" else "Beneficiary Account",
    key="ti_type_filter",
)
linked_tx_filter = st.sidebar.text_input("Filter by Associated TX ID", key="ti_tx_filter")

ti_filters = {}
if conf_filter and len(conf_filter) < 3:
    ti_filters["confidence_levels"] = conf_filter
if status_filter and len(status_filter) < 2:
    ti_filters["statuses"] = status_filter
if type_filter and len(type_filter) < 2:
    ti_filters["types"] = type_filter
if linked_tx_filter.strip():
    ti_filters["transaction_id"] = linked_tx_filter.strip()

indicators = get_threat_indicators(ti_filters if ti_filters else None)
all_indicators = get_threat_indicators()

# ── Summary KPI Row ────────────────────────────────────────────────────────
active_count = sum(1 for i in indicators if i["status"] == "ACTIVE")
expired_count = sum(1 for i in indicators if i["status"] == "EXPIRED")
matched_tx_cnt = sum(len(i.get("associated_tx_ids", [])) for i in indicators)

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("Total Tracked Indicators", len(indicators))
kc2.metric("Active Threat Feeds", active_count)
kc3.metric("Expired (Suppressed · 0 Pts)", expired_count)
kc4.metric("Correlated Transactions", matched_tx_cnt)

st.markdown("<br>", unsafe_allow_html=True)

# ── Register New Threat Indicator Form (Expandable) ────────────────────────
with st.expander("➕ Register New Threat Intelligence Indicator", expanded=False):
    st.markdown(
        '<p style="font-size:0.8rem;color:#8A9CB0;margin-bottom:12px">'
        'Add a newly identified malicious IP or fraudulent beneficiary account to the bank\'s active watchlist. '
        'The risk scoring engine will immediately evaluate subsequent transactions against this entry.</p>',
        unsafe_allow_html=True,
    )
    rf1, rf2 = st.columns(2, gap="large")

    with rf1:
        new_ind_val = st.text_input(
            "Indicator Value",
            placeholder="e.g. 194.26.29.112 or BEN-MULE-4402",
            key="input_new_ti_val",
        )
        new_ind_type = st.radio(
            "Indicator Type",
            options=["ip_address", "beneficiary_account"],
            format_func=lambda x: "🌐 IP Address" if x == "ip_address" else "🏦 Beneficiary Account",
            horizontal=True,
            key="input_new_ti_type",
        )
        new_source = st.selectbox(
            "Intelligence Feed / Provenance",
            options=[
                "Internal Forensic Escalation",
                "AbuseIPDB Threat Feed",
                "Tor Project Exit Directory",
                "Inter-Bank Mule Consortium",
                "Law Enforcement Directive",
            ],
            key="input_new_ti_source",
        )

    with rf2:
        new_category = st.selectbox(
            "Threat Category",
            options=[
                "bulletproof_hosting_vpn",
                "anonymizer_proxy_node",
                "credential_stuffing_botnet",
                "suspected_drop_beneficiary",
                "unclassified_threat",
            ],
            format_func=_clean_category_name,
            key="input_new_ti_cat",
        )
        new_conf = st.radio(
            "Confidence Tier",
            options=["high", "medium", "low"],
            format_func=lambda x: {
                "high": "High (+35 risk points)",
                "medium": "Medium (+20 risk points)",
                "low": "Low (+10 risk points)",
            }[x],
            horizontal=True,
            key="input_new_ti_conf",
        )
        new_ttl_days = st.selectbox(
            "Active Validity Window (TTL)",
            options=[30, 90, 180, 365],
            index=1,
            format_func=lambda d: f"{d} Days ({'Standard' if d==90 else 'Extended'})",
            key="input_new_ti_ttl",
        )

    new_notes = st.text_area(
        "Investigation Rationale / Context",
        placeholder="e.g. Identified during forensic investigation of unauthorized wire transfer; confirmed Tor relay node.",
        height=65,
        key="input_new_ti_notes",
    )

    if st.button("🛡️ Register Indicator into Active Registry", type="primary", use_container_width=True, key="btn_submit_ti"):
        if not new_ind_val.strip():
            st.warning("Please provide a valid IP address or Beneficiary Account ID.")
        else:
            payload = {
                "indicator": new_ind_val.strip(),
                "indicator_type": new_ind_type,
                "source_label": new_source,
                "threat_category": new_category,
                "confidence_level": new_conf,
                "expires_in_days": new_ttl_days,
                "description": new_notes.strip() or "Registered by fraud investigator.",
            }
            res = create_threat_indicator(payload)
            if res.get("success"):
                st.success(f"Threat indicator **{new_ind_val.strip()}** successfully registered and active in scoring engine!")
                st.rerun()
            else:
                st.error(f"Failed to register indicator: {res.get('error')}")

st.markdown("<br>", unsafe_allow_html=True)

# ── Threat Intelligence Registry Table ─────────────────────────────────────
st.markdown(
    '<div class="panel-header">THREAT INTELLIGENCE INDICATOR REGISTRY</div>',
    unsafe_allow_html=True,
)

if not indicators:
    st.info("No indicators match your current filter criteria.")
else:
    html_rows = ""
    for ind in indicators:
        status_html = ti_badge_html(ind["status"])
        conf_color = (
            "#10B981"
            if ind["confidence"] == "High"
            else "#F59E0B"
            if ind["confidence"] == "Medium"
            else "#94A3B8"
        )
        impact_val = ind.get("score_impact", 0)
        impact_html = (
            f'<span style="color:#EF4444;font-weight:700;font-family:monospace">+{impact_val} pts</span>'
            if impact_val > 0
            else '<span style="color:#9CA3AF;font-family:monospace">0 pts (stale)</span>'
        )
        type_color = "#EF4444" if ind["type"] == "IP_ADDRESS" else "#8B5CF6"
        type_label = "IP Address" if ind["type"] == "IP_ADDRESS" else "Beneficiary"
        source_clean = _clean_source_name(ind["source_name"])
        tx_cnt = len(ind.get("associated_tx_ids", []))

        html_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#21D4C2;font-weight:600">{ind['indicator_id']}</td>
  <td style="padding:8px 10px">
    <span style="font-size:0.68rem;padding:2px 7px;border-radius:4px;background:{type_color}22;color:{type_color};font-weight:600">{type_label}</span>
  </td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#F1F5F9;font-family:'JetBrains Mono',monospace;font-weight:600">{ind['masked_value']}</td>
  <td style="padding:8px 10px;font-size:0.76rem;color:#E2E8F0">{source_clean}</td>
  <td style="padding:8px 10px;text-align:center">
    <span style="font-size:0.72rem;font-weight:700;color:{conf_color}">{ind['confidence']}</span>
  </td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#8A9CB0;font-family:monospace">{ind.get('last_seen','')[:10]}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#8A9CB0;font-family:monospace">{ind.get('expires_at','')[:10]}</td>
  <td style="padding:8px 10px;text-align:center">{status_html}</td>
  <td style="padding:8px 10px;text-align:center">{impact_html}</td>
  <td style="padding:8px 10px;text-align:center;font-family:monospace;color:#67E8F9;font-weight:600">{tx_cnt} txs</td>
</tr>"""

    st.markdown(
        f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720;font-family:'Inter',sans-serif">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">ID</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Type</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Indicator Value</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Intelligence Feed Source</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Confidence</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Last Seen</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Expires (TTL)</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Status</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Risk Impact</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Matches</th>
    </tr>
  </thead>
  <tbody>{html_rows}</tbody>
</table>
</div>
""",
        unsafe_allow_html=True,
    )

st.divider()

# ── Indicator Detail Inspection ─────────────────────────────────────────────
st.markdown(
    '<div class="panel-header">INDICATOR FRESHNESS &amp; LINKED TRANSACTION INSPECTOR</div>',
    unsafe_allow_html=True,
)

all_ids = [i["indicator_id"] for i in indicators]
if all_ids:
    sel_ind_id = st.selectbox(
        "Select Threat Indicator to Inspect",
        options=all_ids,
        format_func=lambda iid: next(
            (f"{i['indicator_id']} · {i['masked_value']} ({i['status']} · +{i['score_impact']} pts)" for i in indicators if i["indicator_id"] == iid),
            iid,
        ),
        key="ti_detail_select",
    )
    sel_ind = next((i for i in indicators if i["indicator_id"] == sel_ind_id), None)

    if sel_ind:
        ic1, ic2 = st.columns([1.4, 2.0], gap="large")
        with ic1:
            impact = sel_ind.get("score_impact", 0)
            st.markdown(
                f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:18px 22px">
  <div style="font-size:0.84rem;font-family:monospace;color:#21D4C2;font-weight:700;margin-bottom:12px">
    {sel_ind['indicator_id']} — {sel_ind['masked_value']}
  </div>
  {''.join(f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.78rem"><span style="color:#8A9CB0">{k}</span><span style="color:#F1F5F9;font-family:monospace">{v}</span></div>' for k,v in [
    ("Indicator Type", "IP Address" if sel_ind["type"] == "IP_ADDRESS" else "Beneficiary Account"),
    ("Feed Source", _clean_source_name(sel_ind["source_name"])),
    ("Threat Category", _clean_category_name(sel_ind.get("threat_actor_or_campaign","—"))),
    ("Confidence Tier", sel_ind["confidence"]),
    ("First Seen (UTC)", sel_ind.get("first_seen","—")[:19].replace("T", " ")),
    ("Last Seen (UTC)", sel_ind.get("last_seen","—")[:19].replace("T", " ")),
    ("Expires At (UTC)", sel_ind.get("expires_at","—")[:19].replace("T", " ")),
    ("Freshness Status", sel_ind["status"]),
    ("Risk Score Impact", f"+{impact} pts" if impact > 0 else "0 pts (Suppressed / Stale)"),
  ])}
</div>
""",
                unsafe_allow_html=True,
            )

        with ic2:
            st.markdown("**Forensic Context & Provenance**")
            st.markdown(
                f'<div style="padding:12px 16px;background:#070B10;border:1px solid #223342;'
                f'border-radius:6px;font-size:0.82rem;color:#E2E8F0;line-height:1.5">'
                f'{sel_ind.get("notes","No investigation notes recorded.")}</div>',
                unsafe_allow_html=True,
            )

            if sel_ind["status"] == "EXPIRED":
                st.markdown(
                    '<div style="margin-top:12px;padding:12px 16px;background:#2D1B0A;'
                    'border:1px solid #F59E0B55;border-left:3.5px solid #F59E0B;'
                    'border-radius:6px;font-size:0.8rem;color:#FDE68A;line-height:1.45">'
                    '⏰ <b>FRESHNESS GATING POLICY (STALE INDICATOR SUPPRESSED):</b> '
                    'Because this indicator passed its validity window, TRACE-Fin assigns '
                    '<b>0 risk points</b> to this indicator so reassigned historical IPs do not cause false positives.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="margin-top:12px;padding:12px 16px;background:#082330;'
                    f'border:1px solid #21D4C255;border-left:3.5px solid #21D4C2;'
                    'border-radius:6px;font-size:0.8rem;color:#67E8F9;line-height:1.45">'
                    f'✅ <b>ACTIVE THREAT INTEL MATCH:</b> Verified active at transaction time; contributes '
                    f'<b>+{sel_ind.get("score_impact",0)} points</b> to composite risk scoring.</div>',
                    unsafe_allow_html=True,
                )

            assoc_txs = sel_ind.get("associated_tx_ids", [])
            st.markdown(f"**Correlated Transactions ({len(assoc_txs)} matches)**")
            if assoc_txs:
                sel_assoc_tx = st.selectbox(
                    "Select a matched transaction to inspect",
                    options=assoc_txs[:30],
                    format_func=lambda tid: (
                        f"{tid} · {get_transaction(tid)['sender_name'][:18]} → {get_transaction(tid)['beneficiary_name'][:16]} · "
                        f"{fmt_currency(get_transaction(tid)['amount'])} · "
                        f"Risk: {get_transaction(tid).get('method3_score', get_transaction(tid).get('risk_score', 0))}/100 "
                        f"[{get_transaction(tid).get('raw_status', get_transaction(tid).get('status', ''))}]"
                        if get_transaction(tid)
                        else tid
                    ),
                    key="ti_assoc_tx_sel",
                )
                if st.button(f"⚗️ Open {sel_assoc_tx} in Risk Analysis Lab →", key="ti_jump_btn", type="primary"):
                    st.session_state["selected_tx_id"] = sel_assoc_tx
                    st.switch_page("pages/3_risk_analysis_lab.py")

