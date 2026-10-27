"""
PAGE 6 — Incident Register & Stage 10 Evaluation Dashboard
Live SQLite incident lifecycle management, cryptographic SHA-256 tamper verification,
and reproducible 3-method evaluation metrics across 500+ synthetic transactions.
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    get_evaluation_metrics,
    get_incident,
    get_incidents,
    update_incident_status_live,
)
from ui.components import (
     COLORS,
    RISK_COLOR_MAP,
    fmt_currency,
    fmt_ts,
    inject_css,
    plotly_layout_defaults,
    render_demo_banner,
    status_badge_html,
)

inject_css()
render_demo_banner()

st.markdown("<h1>Incident Register &amp; Comparative Evaluation</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#8A9CB0;font-size:0.85rem;margin-bottom:16px">'
    'Manage forensic incidents with real-time SHA-256 tamper-evident verification, '
    'and inspect comparative Precision, Recall, F1, and False-Positive Rates across all three scoring methods.</p>',
    unsafe_allow_html=True,
)

tab_inc, tab_eval = st.tabs(["📋 Incident Register & SHA-256 Integrity", "📊 Comparative Evaluation"])

# ══════════════════════════════════════════════════════════════════════════
# TAB A: INCIDENT REGISTER
# ══════════════════════════════════════════════════════════════════════════
with tab_inc:
    st.divider()
    all_incidents = get_incidents()

    open_cnt = sum(1 for i in all_incidents if i["raw_status"] == "open")
    inv_cnt = sum(1 for i in all_incidents if i["raw_status"] == "investigating")
    closed_cnt = sum(1 for i in all_incidents if i["raw_status"] == "closed")

    ic1, ic2, ic3, ic4 = st.columns(4)
    ic1.metric("Total Incidents", len(all_incidents))
    ic2.metric("Open (Action Required)", open_cnt)
    ic3.metric("Investigating (In Review)", inv_cnt)
    ic4.metric("Closed / Resolved", closed_cnt)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="panel-header">FORENSIC INCIDENT REGISTER</div>', unsafe_allow_html=True)

    if not all_incidents:
        st.info("No incidents currently recorded. Use Forensic Investigation to deny a verification request and generate an incident.")
    else:
        html_rows = ""
        for inc in all_incidents:
            status_b = status_badge_html(inc["status"])
            risk_score = inc.get("risk_score_at_creation", 0)
            risk_level = (
                "Critical"
                if risk_score >= 85
                else "High"
                if risk_score >= 60
                else "Medium"
                if risk_score >= 30
                else "Low"
            )
            score_color = RISK_COLOR_MAP.get(risk_level, "#8A9CB0")
            short_hash = inc.get("sha256_hash", "—")[:24] + "…"

            html_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:#21D4C2;font-weight:600">{inc['incident_id']}</td>
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#CBD5E1">{inc['tx_id']}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#E2E8F0">{inc.get('user_display_name','')[:24]}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#F1F5F9;font-weight:600;font-family:monospace">{fmt_currency(inc.get('amount',0))}</td>
  <td style="padding:8px 10px;font-size:0.73rem;color:#8A9CB0;font-family:monospace">{fmt_ts(inc.get('created_at',''))}</td>
  <td style="padding:8px 10px;text-align:center">{status_b}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{score_color};font-family:monospace">{risk_score}/100</td>
  <td style="padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#67E8F9">{short_hash}</td>
</tr>"""

        st.markdown(
            f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720;font-family:'Inter',sans-serif">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Incident ID</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">TX ID</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Account Holder</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Amount</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Created (UTC)</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Status</th>
      <th style="padding:9px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Score</th>
      <th style="padding:9px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">SHA-256 Digest</th>
    </tr>
  </thead>
  <tbody>{html_rows}</tbody>
</table>
</div>
""",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Incident Detail, Lifecycle Update & Cryptographic Verification ─────
    st.markdown(
        '<div class="panel-header">INCIDENT DETAIL, PLAYBOOK &amp; SHA-256 INTEGRITY VERIFICATION</div>',
        unsafe_allow_html=True,
    )

    inc_ids = [i["incident_id"] for i in all_incidents]
    if inc_ids:
        sel_inc_id = st.selectbox(
            "Select Incident Record",
            options=inc_ids,
            format_func=lambda iid: next(
                (f"{i['incident_id']} · TX: {i['tx_id']} · {i['user_display_name']} ({i['status']})" for i in all_incidents if i["incident_id"] == iid),
                iid,
            ),
            key="inc_detail_select",
        )
        sel_inc = get_incident(sel_inc_id)

        if sel_inc:
            id1, id2 = st.columns([1.5, 2.0], gap="large")

            with id1:
                st.markdown(
                    '<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:16px 20px">'
                    + "".join(
                        f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1E2D3B;font-size:0.78rem">'
                        f'<span style="color:#8A9CB0">{k}</span>'
                        f'<span style="color:#F1F5F9;font-weight:500;font-family:monospace">{v}</span></div>'
                        for k, v in [
                            ("Incident ID", sel_inc["incident_id"]),
                            ("Transaction ID", sel_inc["tx_id"]),
                            ("Account Holder", sel_inc.get("user_display_name", "—")[:26]),
                            ("Created At", fmt_ts(sel_inc.get("created_at", ""))),
                            ("Status", sel_inc["status"]),
                            ("Severity", sel_inc["severity"]),
                            ("Risk Score at Creation", f"{sel_inc.get('risk_score_at_creation','—')}/100"),
                            ("Linked Evidence Rows", sel_inc.get("evidence_records_count", 0)),
                        ]
                    )
                    + "</div>",
                    unsafe_allow_html=True,
                )

                st.markdown("**Summary & Audit Trail**")
                st.markdown(
                    f'<div style="padding:10px 14px;background:#070B10;border:1px solid #223342;'
                    f'border-radius:6px;font-size:0.79rem;color:#E2E8F0;line-height:1.5;margin-bottom:12px">'
                    f'{sel_inc.get("summary","—")}</div>',
                    unsafe_allow_html=True,
                )

                st.markdown("**Advisory Incident Response Playbook (`recommended_actions`)**")
                for action in sel_inc.get("recommended_actions", []):
                    st.markdown(
                        f'<div style="padding:6px 10px;background:#0B1929;border-left:2.5px solid #21D4C2;'
                        f'border-radius:4px;font-size:0.75rem;color:#CBD5E1;margin-bottom:5px;line-height:1.4">'
                        f'▸ {action}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown("**Update Incident Status**")
                status_opts = ["open", "investigating", "closed"]
                curr_raw = sel_inc.get("raw_status", "open")
                new_status = st.selectbox(
                    "Lifecycle Status",
                    options=status_opts,
                    index=status_opts.index(curr_raw) if curr_raw in status_opts else 0,
                    format_func=lambda s: {"open": "🔴 Open", "investigating": "🟡 Investigating", "closed": "🟢 Closed (Evidence Preserved)"}[s],
                    key="inc_new_status",
                )
                inv_note = st.text_input("Investigator Audit Note", placeholder="Add containment or resolution note...", key="inc_inv_note")
                if st.button("💾 Update Incident Status", use_container_width=True, key="patch_inc_btn"):
                    res = update_incident_status_live(sel_inc["incident_id"], new_status, inv_note)
                    if res["ok"]:
                        st.success(f"Updated {sel_inc['incident_id']} to '{new_status}'!")
                        st.rerun()
                    else:
                        st.error(res.get("error", "Failed to update incident."))

            with id2:
                integrity = sel_inc.get("evidence_integrity", {})
                is_valid = integrity.get("integrity_verified", True)
                int_col = "#10B981" if is_valid else "#EF4444"
                int_title = (
                    "✅ CRYPTOGRAPHIC SHA-256 INTEGRITY VERIFIED (TAMPER-EVIDENT SNAPSHOT INTACT)"
                    if is_valid
                    else "🚨 TAMPER DETECTED — STORED SHA-256 DOES NOT MATCH RECOMPUTED SNAPSHOT"
                )

                st.markdown(
                    f"""
<div style="padding:12px 16px;background:{int_col}14;border:1px solid {int_col}55;border-left:4px solid {int_col};
border-radius:8px;margin-bottom:14px">
  <div style="font-size:0.8rem;font-weight:700;color:{int_col};margin-bottom:4px">{int_title}</div>
  <div style="font-size:0.75rem;color:#CBD5E1;margin-bottom:6px">{integrity.get("verification_message","")}</div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:0.69rem;color:#94A3B8;word-break:break-all">
    Stored SHA-256: &nbsp;&nbsp;&nbsp;<span style="color:#21D4C2">{integrity.get("stored_sha256", sel_inc.get("sha256_hash",""))}</span><br>
    Recomputed SHA-256: <span style="color:{int_col}">{integrity.get("recomputed_sha256", sel_inc.get("sha256_hash",""))}</span>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

                st.markdown("**Linked Evidence Records**")
                for ev in sel_inc.get("linked_evidence", []):
                    st.markdown(
                        f'<div style="padding:6px 10px;border-bottom:1px solid #1E2D3B;font-size:0.75rem">'
                        f'<code style="color:#21D4C2">{ev["source_record_id"]}</code> '
                        f'<span style="color:#8A9CB0;font-family:monospace">({ev["timestamp_utc"]})</span><br>'
                        f'<span style="color:#CBD5E1">{ev["explanation"]}</span></div>',
                        unsafe_allow_html=True,
                    )

                with st.expander("View Canonical Evidence Snapshot JSON"):
                    st.code(json.dumps(sel_inc.get("canonical_snapshot", {}), indent=2), language="json")


# ══════════════════════════════════════════════════════════════════════════
# TAB B: STAGE 10 EVALUATION DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
with tab_eval:
    st.divider()

    ev_col1, ev_col2 = st.columns([2, 2], gap="large")
    with ev_col1:
        eval_thresh = st.slider(
            "Evaluation Alert Threshold (Score ≥)",
            min_value=20,
            max_value=90,
            value=60,
            step=5,
            key="eval_thr_slider",
        )
    with ev_col2:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        use_user_pref = st.checkbox(
            "Evaluate against each user's personalized risk_threshold (`user_preferences` table)",
            value=False,
            key="eval_use_user_pref",
        )

    eval_data = get_evaluation_metrics(
        threshold=eval_thresh,
        use_user_preferences_threshold=use_user_pref,
    )

    if not eval_data:
        st.error("Failed to load evaluation metrics.")
        st.stop()

    st.info(f"**Academic Evaluation Note:** {eval_data.get('note', '')}", icon="📘")

    methods = ["method1", "method2", "method3"]
    method_labels = {
        "method1": "M1: Transaction-Only Baseline",
        "method2": "M2: Contextual Forensic Scoring",
        "method3": "M3: Contextual + Threat Intelligence",
    }

    # ── 1. Model Comparison Table ───────────────────────────────────────────
    st.markdown(
        f'<div class="panel-header">COMPARATIVE MODEL PERFORMANCE (THRESHOLD = {"PER-USER" if use_user_pref else eval_thresh})</div>',
        unsafe_allow_html=True,
    )

    comparison_rows = ""
    for m in methods:
        md = eval_data[m]
        prec = f"{md['precision']:.1%}"
        rec = f"{md['recall']:.1%}"
        f1 = f"{md['f1_score']:.4f}"
        fpr = f"{md['false_positive_rate']:.2%}"
        capex_fpr = f"{md.get('capex_fpr', 0):.1%}"
        ato_rec = f"{md.get('ato_detection_rate', 0):.1%}"
        bec_rec = f"{md.get('bec_detection_rate', 0):.1%}"

        f1_val = md["f1_score"]
        f1_color = "#10B981" if f1_val >= 0.85 else "#F59E0B" if f1_val >= 0.6 else "#EF4444"
        comparison_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:10px 12px;font-size:0.8rem;color:#F1F5F9;font-weight:600">{method_labels[m]}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.82rem;color:#E2E8F0;font-family:monospace">{prec}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.82rem;color:#E2E8F0;font-family:monospace">{rec}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.9rem;font-weight:700;color:{f1_color};font-family:monospace">{f1}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.82rem;color:#EF4444;font-family:monospace">{fpr}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.82rem;color:#F59E0B;font-family:monospace">{capex_fpr}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.82rem;color:#21D4C2;font-family:monospace">{ato_rec}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.82rem;color:#21D4C2;font-family:monospace">{bec_rec}</td>
  <td style="padding:10px 12px;text-align:center;font-size:0.8rem;color:#94A3B8;font-family:monospace">{md['total_alerts']} ({md.get('flagged_percentage',0)}%)</td>
</tr>"""

    st.markdown(
        f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720;font-family:'Inter',sans-serif">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:10px 12px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Scoring Method</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Precision</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Recall</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">F1 Score</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#EF4444;text-transform:uppercase">Overall FPR</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#F59E0B;text-transform:uppercase">CapEx FPR</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#21D4C2;text-transform:uppercase">ATO Recall</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#21D4C2;text-transform:uppercase">BEC Recall</th>
      <th style="padding:10px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Alert Volume</th>
    </tr>
  </thead>
  <tbody>{comparison_rows}</tbody>
</table>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 2. Confusion Matrices ───────────────────────────────────────────────
    st.markdown('<div class="panel-header">CONFUSION MATRICES (TP / FP / TN / FN)</div>', unsafe_allow_html=True)

    cm_cols = st.columns(3, gap="medium")
    for i, m in enumerate(methods):
        md = eval_data[m]
        with cm_cols[i]:
            z = [[md["tn"], md["fp"]], [md["fn"], md["tp"]]]
            text = [[f"TN = {md['tn']}", f"FP = {md['fp']}"], [f"FN = {md['fn']}", f"TP = {md['tp']}"]]
            colorscale = [[0, "#091119"], [0.33, "#13212E"], [0.66, "#1E3A5F"], [1, "#21D4C2"]]

            fig_cm = go.Figure(
                go.Heatmap(
                    z=z,
                    text=text,
                    texttemplate="%{text}",
                    textfont=dict(size=12, family="JetBrains Mono"),
                    colorscale=colorscale,
                    showscale=False,
                    xgap=4,
                    ygap=4,
                    hovertemplate="<b>%{text}</b><extra></extra>",
                )
            )
            layout = plotly_layout_defaults(method_labels[m], height=215)
            layout["xaxis"]["tickvals"] = [0, 1]
            layout["xaxis"]["ticktext"] = ["Pred: Legit (0)", "Pred: Flagged (1)"]
            layout["yaxis"]["tickvals"] = [0, 1]
            layout["yaxis"]["ticktext"] = ["Actual: Legit (0)", "Actual: Attack (1)"]
            layout["margin"] = dict(l=105, r=14, t=42, b=40)
            fig_cm.update_layout(**layout)
            st.plotly_chart(fig_cm, use_container_width=True, config={"displayModeBar": False})

    st.divider()

    # ── 3. F1 Score Comparison Bar & Threshold Sweep ────────────────────────
    f1_chart_col, vol_rec_col = st.columns([1.35, 2.0], gap="large")

    with f1_chart_col:
        st.markdown('<div class="panel-header">F1 SCORE PROGRESSION</div>', unsafe_allow_html=True)
        f1_vals = [eval_data[m]["f1_score"] for m in methods]
        f1_labels = ["M1: Baseline", "M2: Contextual", "M3: +Threat Intel"]
        f1_colors = ["#EF4444", "#21D4C2", "#8B5CF6"]

        fig_f1 = go.Figure(
            go.Bar(
                x=f1_labels,
                y=f1_vals,
                marker_color=f1_colors,
                text=[f"{v:.3f}" for v in f1_vals],
                textposition="outside",
                textfont=dict(color=COLORS["text_primary"], size=12),
                hovertemplate="<b>%{x}</b><br>F1: %{y:.4f}<extra></extra>",
            )
        )
        layout_f1 = plotly_layout_defaults("", height=290)
        layout_f1["yaxis"]["range"] = [0, 1.12]
        layout_f1["yaxis"]["title"] = "F1 Score"
        fig_f1.update_layout(**layout_f1)
        st.plotly_chart(fig_f1, use_container_width=True, config={"displayModeBar": False})

    with vol_rec_col:
        st.markdown(
            '<div class="panel-header">THRESHOLD SWEEP (20–90): F1 SCORE ACROSS ALL 3 METHODS</div>',
            unsafe_allow_html=True,
        )
        sweep = eval_data.get("threshold_sweep", [])
        df_sweep = pd.DataFrame(sweep)

        if not df_sweep.empty:
            fig_avr = go.Figure()
            for col_name, label, line_col in [
                ("f1_method1", "M1: Baseline", "#EF4444"),
                ("f1_method2", "M2: Contextual", "#21D4C2"),
                ("f1_method3", "M3: +Threat Intel", "#8B5CF6"),
            ]:
                if col_name in df_sweep.columns:
                    fig_avr.add_trace(
                        go.Scatter(
                            x=df_sweep["threshold"],
                            y=df_sweep[col_name],
                            mode="lines+markers",
                            name=label,
                            line=dict(color=line_col, width=2.2),
                            marker=dict(size=6),
                            hovertemplate=f"<b>{label}</b><br>Threshold: %{{x}}<br>F1: %{{y:.3f}}<extra></extra>",
                        )
                    )
            layout_avr = plotly_layout_defaults("", height=290)
            layout_avr["xaxis"]["title"] = "Alert Score Threshold (20–90)"
            layout_avr["yaxis"]["title"] = "F1 Score"
            layout_avr["yaxis"]["range"] = [0, 1.08]
            fig_avr.update_layout(**layout_avr)
            st.plotly_chart(fig_avr, use_container_width=True, config={"displayModeBar": False})

    st.divider()

    # ── 4. Expenditure Model Breakdown (CapEx vs OpEx vs Personal) ──────────
    exp_breakdown = eval_data.get("per_expenditure_model_breakdown", [])
    if exp_breakdown:
        st.markdown(
            '<div class="panel-header">STRATIFIED EVALUATION BY EXPENDITURE MODEL (CAPEX vs OPEX vs PERSONAL)</div>',
            unsafe_allow_html=True,
        )
        exp_rows = ""
        for eb in exp_breakdown:
            exp_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 12px;font-family:monospace;font-size:0.78rem;color:#21D4C2;font-weight:600">{eb['expenditure_model']}</td>
  <td style="padding:8px 12px;text-align:center;color:#CBD5E1">{eb['total_transactions']}</td>
  <td style="padding:8px 12px;text-align:center;color:#EF4444;font-family:monospace">{eb['baseline_fpr']:.1%}</td>
  <td style="padding:8px 12px;text-align:center;color:#10B981;font-family:monospace;font-weight:700">{eb['contextual_fpr']:.1%}</td>
  <td style="padding:8px 12px;text-align:center;color:#94A3B8;font-family:monospace">{eb['baseline_f1']:.3f}</td>
  <td style="padding:8px 12px;text-align:center;color:#21D4C2;font-family:monospace;font-weight:700">{eb['contextual_f1']:.3f}</td>
  <td style="padding:8px 12px;text-align:center;color:#8B5CF6;font-family:monospace;font-weight:700">{eb['contextual_ti_f1']:.3f}</td>
</tr>"""
        st.markdown(
            f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto;margin-bottom:16px">
<table style="width:100%;border-collapse:collapse;background:#0E1720">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:9px 12px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Expenditure Model</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Sample Size</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#EF4444;text-transform:uppercase">M1 Baseline FPR</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#10B981;text-transform:uppercase">M2 Contextual FPR</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M1 F1</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#21D4C2;text-transform:uppercase">M2 Contextual F1</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8B5CF6;text-transform:uppercase">M3 +Threat Intel F1</th>
    </tr>
  </thead>
  <tbody>{exp_rows}</tbody>
</table>
</div>
""",
            unsafe_allow_html=True,
        )

    # ── 5. Per-Scenario Flagging Rates Across All 3 Methods ─────────────────
    st.markdown(
        '<div class="panel-header">PER-SCENARIO FLAGGING RATES ACROSS ALL 3 METHODS</div>',
        unsafe_allow_html=True,
    )
    scenario_rates = eval_data.get("scenario_detection_rates", {})
    if scenario_rates:
        sr_rows = ""
        for scen_id, data in scenario_rates.items():
            is_attack = data["type"] == "Attack"
            type_color = "#EF4444" if is_attack else "#10B981"
            b_rate = data.get("baseline_rate", 0)
            c_rate = data.get("detection_rate", 0)
            t_rate = data.get("ti_rate", 0)
            sr_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 12px;font-family:monospace;font-size:0.75rem;color:#21D4C2">{data['scenario_label']}</td>
  <td style="padding:8px 12px;text-align:center;font-size:0.74rem;font-weight:700;color:{type_color}">{data['type']}</td>
  <td style="padding:8px 12px;text-align:center;color:#CBD5E1">{data['total']}</td>
  <td style="padding:8px 12px;text-align:center;font-family:monospace;color:#94A3B8">{b_rate:.1%}</td>
  <td style="padding:8px 12px;text-align:center;font-family:monospace;font-weight:700;color:#21D4C2">{c_rate:.1%}</td>
  <td style="padding:8px 12px;text-align:center;font-family:monospace;font-weight:700;color:#8B5CF6">{t_rate:.1%}</td>
</tr>"""

        st.markdown(
            f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:9px 12px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Scenario Archetype</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Ground Truth Class</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Cases</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M1 Flagged Rate</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#21D4C2;text-transform:uppercase">M2 Contextual Rate</th>
      <th style="padding:9px 12px;text-align:center;font-size:0.65rem;color:#8B5CF6;text-transform:uppercase">M3 +Threat Intel Rate</th>
    </tr>
  </thead>
  <tbody>{sr_rows}</tbody>
</table>
</div>
""",
            unsafe_allow_html=True,
        )
