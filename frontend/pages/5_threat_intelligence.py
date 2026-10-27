"""
PAGE 5 — Threat Intelligence Registry
Freshness-aware threat intelligence indicators from SQLite, confidence vs score impact chart,
and one-click navigation to associated transactions.
"""

from __future__ import annotations

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import get_threat_indicators, get_transaction
from ui.components import (
    inject_css,
    plotly_layout_defaults,
    render_demo_banner,
    ti_badge_html,
)

inject_css()
render_demo_banner()

st.markdown("<h1>Threat Intelligence Registry &amp; Freshness Gating</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Synthetic threat-intelligence feed stored in the <code>threat_intelligence</code> SQLite table. '
    'Enforces strict indicator freshness validation: <b>ACTIVE</b> indicators boost Method 3 scores '
    '(+35 High / +20 Medium / +10 Low), while <b>EXPIRED</b> indicators contribute <b style="color:#F59E0B">0 points</b> '
    'and log a stale-indicator audit notice.</p>',
    unsafe_allow_html=True,
)
st.divider()

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

# ── Summary Stats ─────────────────────────────────────────────────────────
active_count = sum(1 for i in indicators if i["status"] == "ACTIVE")
expired_count = sum(1 for i in indicators if i["status"] == "EXPIRED")
high_conf = sum(1 for i in indicators if i["confidence"] == "High" and i["status"] == "ACTIVE")
matched_tx_cnt = sum(len(i.get("associated_tx_ids", [])) for i in indicators)

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("Total SQLite Indicators", len(indicators))
kc2.metric("Active Fresh Indicators", active_count)
kc3.metric("Expired Indicators (0 Pts)", expired_count)
kc4.metric("Matched Transactions in DB", matched_tx_cnt)

st.markdown("<br>", unsafe_allow_html=True)

# ── Indicator Table ────────────────────────────────────────────────────────
st.markdown(
    '<div class="panel-header">SQLITE THREAT INTELLIGENCE INDICATOR REGISTRY</div>',
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
            else '<span style="color:#9CA3AF;font-family:monospace">0 pts (expired)</span>'
        )
        type_color = "#EF4444" if ind["type"] == "IP_ADDRESS" else "#8B5CF6"
        tx_cnt = len(ind.get("associated_tx_ids", []))

        html_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#21D4C2;font-weight:600">{ind['indicator_id']}</td>
  <td style="padding:8px 10px">
    <span style="font-size:0.68rem;padding:2px 7px;border-radius:4px;background:{type_color}22;color:{type_color};font-weight:600">{ind['type']}</span>
  </td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#F1F5F9;font-family:'JetBrains Mono',monospace;font-weight:600">{ind['masked_value']}</td>
  <td style="padding:8px 10px;font-size:0.75rem;color:#CBD5E1;font-family:monospace">{ind['source_name']}</td>
  <td style="padding:8px 10px;text-align:center">
    <span style="font-size:0.72rem;font-weight:700;color:{conf_color}">{ind['confidence']}</span>
  </td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#8A9CB0;font-family:monospace">{ind.get('last_seen','')[:10]}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#8A9CB0;font-family:monospace">{ind.get('expires_at','')[:10]}</td>
  <td style="padding:8px 10px;text-align:center">{status_html}</td>
  <td style="padding:8px 10px;text-align:center">{impact_html}</td>
  <td style="padding:8px 10px;text-align:center;font-family:monospace;color:#67E8F9">{tx_cnt} txs</td>
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
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Synthetic Feed Source</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Confidence</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Last Seen</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Expires</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Status</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M3 Score Δ</th>
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
    ("Indicator Type", sel_ind["type"]),
    ("Synthetic Source", sel_ind["source_name"]),
    ("Threat Category", sel_ind.get("threat_actor_or_campaign","—")),
    ("Confidence Tier", sel_ind["confidence"]),
    ("First Seen (UTC)", sel_ind.get("first_seen","—")),
    ("Last Seen (UTC)", sel_ind.get("last_seen","—")),
    ("Expires At (UTC)", sel_ind.get("expires_at","—")),
    ("Freshness Status", sel_ind["status"]),
    ("Method 3 Score Impact", f"+{impact} pts" if impact > 0 else "0 pts (Stale / Expired)"),
  ])}
</div>
""",
                unsafe_allow_html=True,
            )

        with ic2:
            st.markdown("**Forensic Description & Provenance**")
            st.markdown(
                f'<div style="padding:12px 16px;background:#070B10;border:1px solid #223342;'
                f'border-radius:6px;font-size:0.82rem;color:#E2E8F0;line-height:1.5">'
                f'{sel_ind.get("notes","—")}</div>',
                unsafe_allow_html=True,
            )

            if sel_ind["status"] == "EXPIRED":
                st.markdown(
                    '<div style="margin-top:12px;padding:12px 16px;background:#2D1B0A;'
                    'border:1px solid #F59E0B55;border-left:3.5px solid #F59E0B;'
                    'border-radius:6px;font-size:0.8rem;color:#FDE68A;line-height:1.45">'
                    '⏰ <b>FRESHNESS VALIDATION GATE (STAGE 4 RULE <code>TI_STALE_INDICATOR_IGNORED</code>):</b> '
                    'Because <code>expires_at_utc &lt; transaction.timestamp_utc</code>, TRACE-Fin assigns '
                    '<b>0 risk points</b> to this indicator so reassigned historical IPs do not cause false positives.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="margin-top:12px;padding:12px 16px;background:#082330;'
                    f'border:1px solid #21D4C255;border-left:3.5px solid #21D4C2;'
                    f'border-radius:6px;font-size:0.8rem;color:#67E8F9;line-height:1.45">'
                    f'✅ <b>ACTIVE FRESH INDICATOR:</b> Verified active at transaction time; contributes '
                    f'<b>+{sel_ind.get("score_impact",0)} points</b> in Method 3 (Contextual + Threat Intel).</div>',
                    unsafe_allow_html=True,
                )

            assoc_txs = sel_ind.get("associated_tx_ids", [])
            st.markdown(f"**Associated SQLite Transactions ({len(assoc_txs)} matches)**")
            if assoc_txs:
                sel_assoc_tx = st.selectbox(
                    "Select a matched transaction to inspect in Risk Analysis Lab",
                    options=assoc_txs[:30],
                    format_func=lambda tid: (
                        f"{tid} · {get_transaction(tid)['sender_name'][:20]} · "
                        f"M2={get_transaction(tid)['method2_score']} → M3={get_transaction(tid)['method3_score']}"
                        if get_transaction(tid)
                        else tid
                    ),
                    key="ti_assoc_tx_sel",
                )
                if st.button(f"⚗️ Open {sel_assoc_tx} in Risk Analysis Lab →", key="ti_jump_btn"):
                    st.session_state["selected_tx_id"] = sel_assoc_tx
                    st.switch_page("pages/3_risk_analysis_lab.py")

st.divider()

# ── Freshness vs Confidence Scatter Chart ──────────────────────────────────
st.markdown(
    '<div class="panel-header">SOURCE CONFIDENCE vs METHOD 3 SCORE IMPACT</div>',
    unsafe_allow_html=True,
)

all_indicators = get_threat_indicators()
if all_indicators:
    color_map = {"ACTIVE": "#21D4C2", "EXPIRED": "#64748B"}
    marker_colors = [color_map.get(i["status"], "#8A9CB0") for i in all_indicators]

    fig_scatter = go.Figure(
        go.Scatter(
            x=[i.get("confidence_score", 0) * 100 for i in all_indicators],
            y=[i.get("score_impact", 0) for i in all_indicators],
            mode="markers+text",
            text=[f"{i['indicator_id']} ({i['masked_value']})" for i in all_indicators],
            textposition="top center",
            textfont=dict(size=10, color="#CBD5E1"),
            marker=dict(
                color=marker_colors,
                size=14,
                line=dict(color="#223342", width=1.5),
                symbol=["circle" if i["status"] == "ACTIVE" else "x" for i in all_indicators],
            ),
            hovertemplate="<b>%{text}</b><br>Confidence: %{x:.0f}%<br>Score Impact: +%{y} pts<extra></extra>",
        )
    )

    layout = plotly_layout_defaults("Confidence (%) vs M3 Points Awarded | ● Active  ✕ Expired", height=320)
    layout["xaxis"]["title"] = "Source Confidence (%)"
    layout["xaxis"]["range"] = [30, 108]
    layout["yaxis"]["title"] = "Score Impact (Points)"
    layout["yaxis"]["range"] = [-5, 45]
    fig_scatter.update_layout(**layout)
    st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})
