"""
PAGE 6 — Scoring Model Benchmark & Comparative Evaluation
Macro-level evaluation across 500 transactions proving multi-layer risk accuracy,
and interactive transaction inspection comparing M1, M2, and M3 scoring engines side-by-side.
"""

from __future__ import annotations

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_evaluation_metrics,
    get_risk_scores,
    get_transaction_index,
    get_transactions,
)
from ui.components import (
    COLORS,
    RISK_COLOR_MAP,
    fmt_currency,
    fmt_ts,
    inject_css,
    plotly_layout_defaults,
    risk_badge_html,
    status_badge_html,
)

inject_css()

st.markdown("<h1>Scoring Model Benchmark &amp; Comparative Evaluation</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Comprehensive evaluation across 500 transactions demonstrating how contextual baseline modeling '
    'and threat intelligence integration eliminate false positives and maximize detection accuracy over traditional static rules.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Macro Benchmark Controls ───────────────────────────────────────────────
ev_c1, ev_c2 = st.columns([2.5, 1.5], gap="large")
with ev_c1:
    eval_thresh = st.slider(
        "Evaluation Alert Threshold (Risk Score ≥)",
        min_value=20,
        max_value=90,
        value=60,
        step=5,
        key="eval_thr_slider",
        help="Transactions with scores at or above this threshold trigger an automated security alert.",
    )
with ev_c2:
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    use_user_pref = st.checkbox(
        "Use personalized user thresholds (`user_preferences`)",
        value=False,
        key="eval_use_user_pref",
    )

eval_data = get_evaluation_metrics(
    threshold=eval_thresh,
    use_user_preferences_threshold=use_user_pref,
)

if not eval_data:
    st.error("Failed to load evaluation metrics from backend.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════
# SECTION 1: MACRO MODEL BENCHMARK (All 500 Transactions)
# ══════════════════════════════════════════════════════════════════════════
st.markdown(
    f'<div class="panel-header">1. MACRO BENCHMARK SCORECARD: THE 3-STAGE EVOLUTION (ALERT THRESHOLD = {eval_thresh})</div>',
    unsafe_allow_html=True,
)

m1 = eval_data["method1"]
m2 = eval_data["method2"]
m3 = eval_data["method3"]

sc1, sc2, sc3 = st.columns(3, gap="large")

with sc1:
    st.markdown(
        f"""
<div style="background:#131B24;border:1px solid #223342;border-top:4px solid #EF4444;border-radius:8px;padding:16px 18px">
  <div style="font-size:0.75rem;font-weight:700;color:#EF4444;text-transform:uppercase;letter-spacing:0.06em">
    M1 · Transaction-Only Baseline
  </div>
  <div style="font-size:0.72rem;color:#8A9CB0;margin-top:2px;margin-bottom:14px">Static rules (Amount, velocity, night hours)</div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Detection F1 Score</span>
    <span style="font-weight:700;color:#EF4444;font-family:monospace;font-size:0.95rem">{m1['f1_score']:.3f}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">False Alarm Rate (FPR)</span>
    <span style="font-weight:700;color:#EF4444;font-family:monospace">{m1['false_positive_rate']:.1%} (High!)</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Precision</span>
    <span style="font-weight:600;color:#E2E8F0;font-family:monospace">{m1['precision']:.1%}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Recall (Attack Coverage)</span>
    <span style="font-weight:600;color:#E2E8F0;font-family:monospace">{m1['recall']:.1%}</span>
  </div>
  <div style="font-size:0.72rem;color:#94A3B8;margin-top:12px;line-height:1.4">
    ⚠️ <b>Weakness:</b> Blindly flags legitimate high-value business transfers (CapEx) because it lacks customer profile context.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

with sc2:
    st.markdown(
        f"""
<div style="background:#0F2022;border:1px solid #223342;border-top:4px solid #21D4C2;border-radius:8px;padding:16px 18px">
  <div style="font-size:0.75rem;font-weight:700;color:#21D4C2;text-transform:uppercase;letter-spacing:0.06em">
    M2 · Contextual Forensic Engine
  </div>
  <div style="font-size:0.72rem;color:#8A9CB0;margin-top:2px;margin-bottom:14px">Profile baseline + historical expenditure models</div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Detection F1 Score</span>
    <span style="font-weight:700;color:#21D4C2;font-family:monospace;font-size:0.95rem">{m2['f1_score']:.3f}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">False Alarm Rate (FPR)</span>
    <span style="font-weight:700;color:#10B981;font-family:monospace">{m2['false_positive_rate']:.1%} (Low!)</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Precision</span>
    <span style="font-weight:600;color:#E2E8F0;font-family:monospace">{m2['precision']:.1%}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Recall (Attack Coverage)</span>
    <span style="font-weight:600;color:#E2E8F0;font-family:monospace">{m2['recall']:.1%}</span>
  </div>
  <div style="font-size:0.72rem;color:#94A3B8;margin-top:12px;line-height:1.4">
    💡 <b>Advantage:</b> Drastically suppresses false alarms on legitimate business payments by learning expected turnover.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

with sc3:
    st.markdown(
        f"""
<div style="background:#1B162B;border:1px solid #223342;border-top:4px solid #8B5CF6;border-radius:8px;padding:16px 18px">
  <div style="font-size:0.75rem;font-weight:700;color:#A78BFA;text-transform:uppercase;letter-spacing:0.06em">
    M3 · Contextual + Threat Intel
  </div>
  <div style="font-size:0.72rem;color:#8A9CB0;margin-top:2px;margin-bottom:14px">Context + Tor relays, botnets &amp; mule watchlists</div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Detection F1 Score</span>
    <span style="font-weight:700;color:#A78BFA;font-family:monospace;font-size:0.95rem">{m3['f1_score']:.3f} (Peak)</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">False Alarm Rate (FPR)</span>
    <span style="font-weight:700;color:#10B981;font-family:monospace">{m3['false_positive_rate']:.1%}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Precision</span>
    <span style="font-weight:600;color:#E2E8F0;font-family:monospace">{m3['precision']:.1%}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1E2D3B;font-size:0.80rem">
    <span style="color:#8A9CB0">Recall (Attack Coverage)</span>
    <span style="font-weight:700;color:#21D4C2;font-family:monospace">{m3['recall']:.1%}</span>
  </div>
  <div style="font-size:0.72rem;color:#94A3B8;margin-top:12px;line-height:1.4">
    🛡️ <b>Optimal:</b> Fuses live threat intelligence with context to catch stealthy account takeovers with minimal false alarms.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Visual Proof: Accuracy vs False Alarms Chart ───────────────────────────
methods_names = [
    "M1: Baseline Rules",
    "M2: Contextual Engine",
    "M3: Contextual + Threat Intel",
]
f1_scores = [m1["f1_score"] * 100, m2["f1_score"] * 100, m3["f1_score"] * 100]
fpr_rates = [m1["false_positive_rate"] * 100, m2["false_positive_rate"] * 100, m3["false_positive_rate"] * 100]

fig_comp = go.Figure()
fig_comp.add_trace(
    go.Bar(
        name="Detection Accuracy (F1 Score %)",
        x=methods_names,
        y=f1_scores,
        marker_color="#21D4C2",
        text=[f"{v:.1f}%" for v in f1_scores],
        textposition="outside",
        textfont=dict(size=12, color="#F1F5F9", family="Inter"),
    )
)
fig_comp.add_trace(
    go.Bar(
        name="False Alarm Rate (FPR %)",
        x=methods_names,
        y=fpr_rates,
        marker_color="#EF4444",
        text=[f"{v:.1f}%" for v in fpr_rates],
        textposition="outside",
        textfont=dict(size=12, color="#F1F5F9", family="Inter"),
    )
)

layout_comp = plotly_layout_defaults("Core Evaluation Tradeoff: Detection Accuracy (F1) vs False Alarm Rate (FPR)", height=310)
layout_comp["barmode"] = "group"
layout_comp["yaxis"]["range"] = [0, 115]
layout_comp["yaxis"]["title"] = "Percentage (%)"
layout_comp["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
fig_comp.update_layout(**layout_comp)
st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ══════════════════════════════════════════════════════════════════════════
# SECTION 2: LIVE TRANSACTION INSPECTION (3-Engine Deep Dive)
# ══════════════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="panel-header">2. LIVE TRANSACTION INSPECTION: 3-ENGINE SCORING COMPARISON</div>',
    unsafe_allow_html=True,
)
st.caption(
    "Select any transaction from the database to see how M1, M2, and M3 evaluate it side-by-side, "
    "and observe how contextual profile suppression and threat-intel boosts change the outcome."
)

all_txs = get_transactions()
tx_index = get_transaction_index()
all_tx_ids = [t["id"] for t in all_txs] if all_txs else []

default_tx = st.session_state.get("selected_tx_id", all_tx_ids[0] if all_tx_ids else None)
if default_tx not in all_tx_ids and all_tx_ids:
    default_tx = all_tx_ids[0]
default_idx = all_tx_ids.index(default_tx) if default_tx in all_tx_ids else 0

selected_tx_id = st.selectbox(
    "Select Transaction to Inspect Across All 3 Engines",
    options=all_tx_ids,
    index=default_idx,
    format_func=lambda tid: (
        f"{tid} · {tx_index[tid]['sender_name'][:20]} → {tx_index[tid]['beneficiary_name'][:18]} · "
        f"{fmt_currency(tx_index[tid]['amount'])} · "
        f"M1={tx_index[tid].get('method1_score',0)} ──► M2={tx_index[tid].get('method2_score',0)} ──► M3={tx_index[tid].get('method3_score',0)} "
        f"[{tx_index[tid].get('raw_status', tx_index[tid].get('status',''))}]"
        if tid in tx_index
        else str(tid)
    ),
    key="eval_tx_select",
)

st.session_state["selected_tx_id"] = selected_tx_id

tx = tx_index.get(selected_tx_id)
scores = get_risk_scores(selected_tx_id)

if tx and scores:
    # Transaction snapshot banner
    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:12px 18px;
display:flex;gap:20px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin:10px 0 16px">
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Case Identifier</span><br>
    <span style="font-size:0.95rem;font-weight:700;color:#21D4C2;font-family:monospace">{tx['id']}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Account Holder</span><br>
    <span style="font-size:0.86rem;font-weight:600;color:#F1F5F9">{tx.get('sender_name','—')}</span>
    <span style="font-size:0.70rem;color:#8A9CB0">({tx.get('sender_profile','Individual')})</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Counterparty &amp; Amount</span><br>
    <span style="font-size:0.86rem;font-weight:600;color:#F1F5F9">{tx.get('beneficiary_name','—')}</span> ·
    <span style="font-size:0.95rem;font-weight:700;color:#F1F5F9;font-family:monospace">{fmt_currency(tx['amount'])}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Timestamp (UTC)</span><br>
    <span style="font-size:0.80rem;color:#E2E8F0;font-family:monospace">{fmt_ts(tx.get('timestamp',''))}</span>
  </div>
  <div>
    <span style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Operational State</span><br>
    <div style="margin-top:2px">{status_badge_html(tx.get('status','Settled'))}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # 3 Engines Side-by-Side Comparison
    m1_score = scores["method1"]["score"]
    m1_level = scores["method1"]["level"]
    m1_col = RISK_COLOR_MAP.get(m1_level, "#8A9CB0")

    m2_score = scores["method2"]["score"]
    m2_level = scores["method2"]["level"]
    m2_col = RISK_COLOR_MAP.get(m2_level, "#8A9CB0")
    delta_ctx = scores.get("delta_contextual_vs_baseline", m2_score - m1_score)

    m3_score = scores["method3"]["score"]
    m3_level = scores["method3"]["level"]
    m3_col = RISK_COLOR_MAP.get(m3_level, "#8A9CB0")
    delta_ti = scores.get("delta_ti_vs_contextual", m3_score - m2_score)

    tc1, tc2, tc3 = st.columns(3, gap="large")

    with tc1:
        st.markdown(
            f"""
<div style="background:#09121A;border:1px solid #223342;border-top:3.5px solid {m1_col};border-radius:8px;padding:14px 16px;text-align:center">
  <div style="font-size:0.72rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.06em">Engine 1: Baseline Rules</div>
  <div style="font-size:2.4rem;font-weight:700;color:{m1_col};font-family:monospace;margin:6px 0">{m1_score}/100</div>
  <div>{risk_badge_html(m1_level)}</div>
  <div style="font-size:0.72rem;color:#94A3B8;margin-top:10px;text-align:left;border-top:1px solid #1E2D3B;padding-top:8px">
    Evaluates amount threshold, velocity, and basic anomalies without customer baseline context.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with tc2:
        delta_ctx_badge = (
            f'<span style="color:#10B981;font-weight:700">▼ {abs(delta_ctx)} pts (Context Suppressed)</span>'
            if delta_ctx < 0
            else (
                f'<span style="color:#EF4444;font-weight:700">▲ +{delta_ctx} pts (Context Escalated)</span>'
                if delta_ctx > 0
                else '<span style="color:#8A9CB0">0 pts change</span>'
            )
        )
        st.markdown(
            f"""
<div style="background:#09121A;border:1px solid #223342;border-top:3.5px solid {m2_col};border-radius:8px;padding:14px 16px;text-align:center">
  <div style="font-size:0.72rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.06em">Engine 2: Contextual Engine</div>
  <div style="font-size:2.4rem;font-weight:700;color:{m2_col};font-family:monospace;margin:6px 0">{m2_score}/100</div>
  <div>{risk_badge_html(m2_level)}</div>
  <div style="font-size:0.72rem;margin-top:6px">{delta_ctx_badge}</div>
  <div style="font-size:0.72rem;color:#94A3B8;margin-top:10px;text-align:left;border-top:1px solid #1E2D3B;padding-top:8px">
    Adjusts score using account turnover, typical transaction ceilings, and expenditure models.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with tc3:
        delta_ti_badge = (
            f'<span style="color:#EF4444;font-weight:700">▲ +{delta_ti} pts (Active Threat Match)</span>'
            if delta_ti > 0
            else '<span style="color:#10B981">Clean IP &amp; Payee (0 pts)</span>'
        )
        st.markdown(
            f"""
<div style="background:#09121A;border:1px solid #223342;border-top:3.5px solid {m3_col};border-radius:8px;padding:14px 16px;text-align:center">
  <div style="font-size:0.72rem;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.06em">Engine 3: Contextual + Threat Intel</div>
  <div style="font-size:2.4rem;font-weight:700;color:{m3_col};font-family:monospace;margin:6px 0">{m3_score}/100</div>
  <div>{risk_badge_html(m3_level)}</div>
  <div style="font-size:0.72rem;margin-top:6px">{delta_ti_badge}</div>
  <div style="font-size:0.72rem;color:#94A3B8;margin-top:10px;text-align:left;border-top:1px solid #1E2D3B;padding-top:8px">
    Fuses real-time Threat Intelligence (Tor nodes, VPN proxies, mule registries) into final score.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Narrative explanation box
    narrative_text = scores.get("comparison_narrative", "")
    if not narrative_text:
        if delta_ctx < 0:
            narrative_text = (
                f"Contextual suppression applied: Baseline rules initially rated this transaction higher, "
                f"but contextual analysis confirmed the amount and beneficiary align with the account's historical "
                f"expenditure profile, safely reducing the risk by {abs(delta_ctx)} points."
            )
        elif delta_ti > 0:
            narrative_text = (
                f"Threat intelligence boost applied: Contextual score was escalated by +{delta_ti} points "
                f"due to active correlation with threat intelligence indicators at transaction time."
            )
        else:
            narrative_text = "Transaction risk evaluation remained consistent across contextual and threat-intelligence models."

    st.markdown(
        f"""
<div style="padding:14px 18px;background:#081A2A;border:1px solid #21D4C255;border-left:4px solid #21D4C2;
border-radius:8px;margin-bottom:16px">
  <div style="font-size:0.76rem;font-weight:700;color:#21D4C2;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">
    ENGINE COMPARISON FINDINGS &amp; CONTEXTUAL EXPLANATION
  </div>
  <div style="font-size:0.80rem;color:#E2E8F0;line-height:1.5">
    {narrative_text}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Active triggered security rules for this transaction
    flags = scores.get("evidence_flags", [])
    if flags:
        st.markdown("**Triggered Rule Identifiers across Engines**")
        rule_pills = " ".join(
            f'<span style="display:inline-block;margin:3px 4px 6px 0;padding:3px 9px;border-radius:4px;'
            f'background:#182533;color:#21D4C2;border:1px solid #223342;font-size:0.73rem;font-family:monospace">▸ {f}</span>'
            for f in flags
        )
        st.markdown(rule_pills, unsafe_allow_html=True)

    # Direct shortcut to deep investigation
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🔬 Open Full Forensic Timeline & Dossier for this Transaction →", key="btn_eval_open_forensic", use_container_width=True):
        st.session_state["selected_tx_id"] = selected_tx_id
        st.switch_page("pages/4_forensic_investigation.py")
