"""
PRIMARY LANDING PAGE — Live Transaction & Risk Scoring Engine
Allows the presenter or evaluator to create a custom User, Beneficiary, and Transaction live,
persist them to SQLite, and immediately inspect the real-time 3-Method Risk Score, Waterfall Chart,
Rule Matrix, Counterfactuals, and Forensic Kill-Chain without relying on pre-baked static cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_provider import (
    create_beneficiary_live,
    create_transaction_live,
    create_user_live,
    get_risk_scores,
    get_transaction,
    get_transactions,
    get_user_beneficiaries_list,
    get_users_list,
    verify_transaction,
)
from ui.components import (
    RISK_COLOR_MAP,
    build_score_comparison_chart,
    build_waterfall_chart,
    expenditure_badge_html,
    fmt_currency,
    fmt_ts,
    inject_css,
    render_demo_banner,
    render_financial_calibration_card,
    render_score_card,
    risk_badge_html,
    status_badge_html,
)

inject_css()
render_demo_banner()

st.markdown(
    """
<div style="margin-bottom:6px">
  <h1 style="margin:0;font-size:1.8rem;font-weight:700;color:#F1F5F9">
    ⚡ Live Transaction Verification &amp; Risk Scoring Engine
  </h1>
  <p style="margin:5px 0 0;color:#8A9CB0;font-size:0.86rem;max-width:920px;line-height:1.45">
    Submit any custom transaction (or create a brand-new user &amp; beneficiary on the spot) to evaluate it dynamically
    against the account's historical SQLite ledger using <b>Method 1 (Transaction-Only Baseline)</b>,
    <b>Method 2 (Contextual Forensic Scoring)</b>, and <b>Method 3 (Contextual + Threat Intelligence)</b>.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

st.divider()

users = get_users_list()
user_map = {u["user_id"]: u for u in users}
user_ids = list(user_map.keys())

# ── Optional Quick Onboarding Drawer for Creating a Brand-New User / Beneficiary ─
with st.expander("➕ Optional Step 0: Onboard a Brand-New Customer Profile or Counterparty into SQLite First", expanded=False):
    ob_tab1, ob_tab2 = st.tabs(
        [
            "👤 Create New Customer / Business Account (POST /users)",
            "🏦 Register or Tamper Counterparty in Ledger (POST /beneficiaries)",
        ]
    )
    with ob_tab1:
        uc1, uc2, uc3 = st.columns(3, gap="medium")
        with uc1:
            u_name = st.text_input("Account Holder / Company Name", value="Zenith Global Manufacturing Ltd", key="u_name")
            u_cat = st.selectbox("Account Category", options=["business", "individual"], key="u_cat")
            p_types = ["enterprise", "small business", "student", "salaried_individual", "freelancer", "HNI indiviuals", "enterprise_capex_firm", "sme_opex_merchant", "high_net_worth"]
            u_ptype = st.selectbox("Employment Type", options=p_types, key="u_ptype")
            u_exp = st.selectbox("Expense Type", options=["capex_heavy", "opex_heavy", "personal_consumption"], key="u_exp")
        with uc2:
            u_sector = st.text_input("Industry Sector", value="manufacturing_heavy_machinery", key="u_sector")
            u_nw = st.number_input("Estimated Net Worth (INR)", min_value=500.0, value=4500000.0, step=10000.0, key="u_nw")
            u_turnover = st.number_input("Declared Monthly Turnover (INR)", min_value=200.0, value=320000.0, step=5000.0, key="u_turn")
            u_typ_tx = st.number_input("Typical Single Tx Amount (INR)", min_value=5.0, value=22000.0, step=500.0, key="u_typ")
        with uc3:
            u_max_tx = st.number_input("Historical Max Single Tx Ceiling (INR)", min_value=20.0, value=95000.0, step=1000.0, key="u_max")
            u_hours = st.text_input("Operating Hours Window (UTC)", value="04:00-16:00", key="u_hours")
            u_geo = st.text_input("Home Geo-Location", value="IN-Mumbai", key="u_geo")
            u_thresh = st.slider("Personal Alert Threshold", min_value=20, max_value=90, value=60, step=5, key="u_thresh")

        if st.button("➕ Save New Customer Profile to SQLite", type="primary", key="create_user_btn"):
            u_res = create_user_live(
                {
                    "display_name": u_name,
                    "account_category": u_cat,
                    "profile_type": u_ptype,
                    "industry_sector": u_sector,
                    "expenditure_model": u_exp,
                    "net_worth_band": ">₹1M" if u_nw >= 1_000_000 else "₹100K-₹1M" if u_nw >= 100_000 else "<₹100K",
                    "estimated_net_worth": u_nw,
                    "declared_monthly_turnover": u_turnover,
                    "typical_tx_amount": u_typ_tx,
                    "typical_max_tx_amount": u_max_tx,
                    "expected_monthly_tx_count": 25,
                    "operating_hours_utc": u_hours,
                    "home_geo_location": u_geo,
                    "risk_threshold": u_thresh,
                    "timezone_iana": "Asia/Kolkata",
                }
            )
            if u_res["ok"] and isinstance(u_res["data"], dict):
                new_u = u_res["data"]
                st.session_state["last_created_user_id"] = new_u["user_id"]
                st.success(f"Created **{new_u['user_id']} ({new_u['display_name']})** in SQLite! Selected automatically below.")
                st.rerun()
            else:
                st.error(u_res.get("error", "Failed to create user."))

    with ob_tab2:
        bc1, bc2 = st.columns(2, gap="large")
        with bc1:
            b_uid = st.selectbox(
                "Account Owner",
                options=user_ids,
                format_func=lambda uid: f"{uid} · {user_map[uid]['display_name']}",
                key="ben_uid_sel",
            )
            b_id = st.text_input("Beneficiary ID", value="BEN-VENDOR-88", key="ben_id_in")
            b_name = st.text_input("Beneficiary / Vendor Name", value="Siemens Industrial Automation AG", key="ben_name_in")
        with bc2:
            b_cat = st.selectbox(
                "Counterparty Category",
                options=["verified_b2b_vendor", "employee_payroll", "utility_tax", "personal_peer", "financial_brokerage"],
                key="ben_cat_in",
            )
            b_ind = st.selectbox(
                "Counterparty Industry",
                options=[
                    "heavy_machinery_equipment",
                    "raw_materials_steel_cement",
                    "wholesale_fmcg_inventory",
                    "cloud_saas_hosting",
                    "payroll_settlement",
                    "digital_assets_brokerage",
                    "luxury_retail_jewelry",
                    "general_consumer",
                ],
                key="ben_ind_in",
            )
            b_ev_type = st.selectbox(
                "Event Action",
                options=["beneficiary_verified", "beneficiary_added", "beneficiary_bank_updated"],
                format_func=lambda et: {
                    "beneficiary_verified": "✅ Verify Established Counterparty (Trusted Supply-Chain)",
                    "beneficiary_added": "➕ Onboard New Counterparty",
                    "beneficiary_bank_updated": "🚨 Modify Counterparty Bank IBAN (Simulate Vendor BEC Attack)",
                }[et],
                key="ben_ev_in",
            )
        if st.button("🏦 Record Counterparty Event in SQLite", type="primary", key="create_ben_btn"):
            b_res = create_beneficiary_live(
                {
                    "user_id": b_uid,
                    "beneficiary_id": b_id.strip() or None,
                    "beneficiary_name": b_name.strip(),
                    "beneficiary_category": b_cat,
                    "beneficiary_industry": b_ind,
                    "event_type": b_ev_type,
                    "notes": "Recorded live via UI.",
                }
            )
            if b_res["ok"]:
                st.success(f"Recorded `{b_ev_type}` for **{b_name}** in SQLite!")
                st.rerun()
            else:
                st.error(b_res.get("error", "Failed to record beneficiary event."))


# ══════════════════════════════════════════════════════════════════════════
# MAIN LIVE TRANSACTION BUILDER & REAL-TIME SCORER
# ══════════════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="panel-header">STEP 1 · CONFIGURE &amp; SUBMIT A LIVE TRANSACTION TO THE RISK ENGINE</div>',
    unsafe_allow_html=True,
)

col_f1, col_f2, col_f3 = st.columns(3, gap="large")

with col_f1:
    st.markdown("**1. Sender Account & Transfer Amount**")
    default_uid = st.session_state.get("last_created_user_id", user_ids[0] if user_ids else "USR-001")
    if default_uid not in user_ids and user_ids:
        default_uid = user_ids[0]

    sel_uid = st.selectbox(
        "Sender Account (From SQLite `users` table)",
        options=user_ids,
        index=user_ids.index(default_uid) if default_uid in user_ids else 0,
        format_func=lambda uid: f"{uid} · {user_map[uid]['display_name']} [{user_map[uid]['expenditure_model']}]",
        key="live_tx_uid",
    )
    u_obj = user_map[sel_uid]

    st.markdown(
        f"""
<div style="background:#0B1520;border:1px solid #1E2E3E;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:0.74rem;color:#CBD5E1">
  <b>Calibrated Profile Baseline:</b><br>
  • Model: <code style="color:#21D4C2">{u_obj['expenditure_model']}</code> ({u_obj['industry_sector']})<br>
  • Typical Tx: <b>₹{u_obj['typical_tx_amount']:,.0f}</b> &nbsp;|&nbsp; Max Ceiling: <b>₹{u_obj['typical_max_tx_amount']:,.0f}</b><br>
  • Monthly Turnover: <b>₹{u_obj['declared_monthly_turnover']:,.0f}</b> &nbsp;|&nbsp; Net Worth: <b>₹{u_obj['estimated_net_worth']:,.0f}</b><br>
  • Operating Hours: <b>{u_obj['operating_hours_utc']} UTC</b> &nbsp;|&nbsp; Home: <b>{u_obj['home_geo_location']}</b>
</div>
""",
        unsafe_allow_html=True,
    )

    tx_amount = st.number_input(
        "Transaction Amount (INR) — Type Any Custom Value",
        min_value=1.0,
        max_value=10_000_000.0,
        value=float(u_obj["typical_tx_amount"] * 2.0),
        step=250.0,
        key="live_tx_amt",
    )

with col_f2:
    st.markdown("**2. Counterparty / Beneficiary Details**")
    user_bens = get_user_beneficiaries_list(sel_uid)
    unique_bens = {}
    for b in user_bens:
        unique_bens.setdefault(b["beneficiary_id"], b)

    ben_mode = st.radio(
        "Counterparty Selection",
        options=["existing", "custom"],
        format_func=lambda m: "Select Known Counterparty" if m == "existing" else "Enter New / Custom Counterparty",
        horizontal=True,
        key="live_ben_mode",
    )

    if ben_mode == "existing" and unique_bens:
        chosen_ben_id = st.selectbox(
            "Known Counterparty",
            options=list(unique_bens.keys()),
            format_func=lambda bid: f"{bid} · {unique_bens[bid]['beneficiary_name']} ({unique_bens[bid]['beneficiary_category']})",
            key="live_known_ben_sel",
        )
        b_info = unique_bens[chosen_ben_id]
        ben_id_val = chosen_ben_id
        ben_name_val = b_info["beneficiary_name"]
        ben_cat_val = b_info["beneficiary_category"]
        ben_ind_val = b_info["beneficiary_industry"]
        st.caption(f"Category: `{ben_cat_val}` · Industry: `{ben_ind_val}`")
    else:
        ben_id_val = st.text_input("Beneficiary ID", value="BEN-LIVE-901", key="live_tx_ben_id")
        ben_name_val = st.text_input("Beneficiary Name", value="Global Peer / Vendor Account", key="live_tx_ben_name")
        ben_cat_val = st.selectbox(
            "Beneficiary Category",
            options=["personal_peer", "verified_b2b_vendor", "employee_payroll", "utility_tax", "financial_brokerage"],
            key="live_tx_ben_cat",
        )
        ben_ind_val = st.selectbox(
            "Beneficiary Industry",
            options=[
                "digital_assets_brokerage",
                "heavy_machinery_equipment",
                "raw_materials_steel_cement",
                "wholesale_fmcg_inventory",
                "cloud_saas_hosting",
                "payroll_settlement",
                "luxury_retail_jewelry",
                "general_consumer",
            ],
            key="live_tx_ben_ind",
        )

with col_f3:
    st.markdown("**3. Session Network, Timing & Threat Intel**")
    tx_ip = st.text_input(
        "Origin IP Address (Use 198.51.100.201 for Tor TI match, 192.0.2.99 for Expired TI)",
        value="103.21.244.18",
        key="live_tx_ip_manual",
    )
    geo_opts = [
        u_obj["home_geo_location"],
        "IN-Mumbai",
        "IN-Pune",
        "IN-Bengaluru",
        "SG-Singapore",
        "AE-Dubai",
        "GB-London",
        "US-NewYork",
        "NL-Amsterdam",
    ]
    geo_opts = list(dict.fromkeys(geo_opts))
    tx_geo = st.selectbox("Origin Geo-Location", options=geo_opts, key="live_tx_geo")

    time_mode = st.selectbox(
        "Transaction Timestamp Window",
        options=["live_now", "in_operating_hours", "off_operating_hours", "month_end_payroll"],
        format_func=lambda tm: {
            "live_now": "🕒 Current Real-Time UTC Clock",
            "in_operating_hours": "☀️ Inside User's Declared Operating Hours (10:00 UTC)",
            "off_operating_hours": "🌙 Odd / Off-Operating Hours (03:15 UTC)",
            "month_end_payroll": "📅 Month-End Payroll / OpEx Settlement Window (28th, 10:00 UTC)",
        }[tm],
        key="live_tx_time_mode",
    )

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:0.75rem;color:#8A9CB0;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px">'
    '4. Surrounding Security &amp; Forensic Telemetry (Toggle to Simulate Attack Precursors Before This Transfer)'
    '</div>',
    unsafe_allow_html=True,
)

pcol1, pcol2, pcol3, pcol4, pcol5 = st.columns(5)
with pcol1:
    sim_fails = st.number_input("Failed Logins Prior (0–10)", min_value=0, max_value=10, value=0, key="live_p_fails")
with pcol2:
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    sim_unseen = st.checkbox("Unrecognized New Device", value=False, key="live_p_unseen")
with pcol3:
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    sim_travel = st.checkbox("Impossible Travel (Home Login 18m Ago)", value=False, key="live_p_travel")
with pcol4:
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    sim_rapid_ben = st.checkbox("Newly Added Beneficiary (4m Ago)", value=(ben_mode == "custom"), key="live_p_rapid")
with pcol5:
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    sim_bec = st.checkbox("Vendor BEC Bank Modified (12m Ago)", value=False, key="live_p_bec")

st.markdown("<br>", unsafe_allow_html=True)
if st.button(
    "⚡ Execute Transaction & Run Live 3-Method Risk Engine",
    type="primary",
    use_container_width=True,
    key="submit_live_tx_btn",
):
    now_dt = datetime.now(timezone.utc)
    if time_mode == "in_operating_hours":
        start_h = int(u_obj["operating_hours_utc"].split("-")[0].split(":")[0])
        ts_val = now_dt.replace(hour=(start_h + 2) % 24, minute=15, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif time_mode == "off_operating_hours":
        end_h = int(u_obj["operating_hours_utc"].split("-")[1].split(":")[0])
        ts_val = now_dt.replace(hour=(end_h + 3) % 24, minute=15, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif time_mode == "month_end_payroll":
        start_h = int(u_obj["operating_hours_utc"].split("-")[0].split(":")[0])
        ts_val = now_dt.replace(day=28, hour=(start_h + 2) % 24, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ts_val = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "user_id": sel_uid,
        "amount": float(tx_amount),
        "currency": "INR",
        "beneficiary_id": ben_id_val.strip(),
        "beneficiary_name": ben_name_val.strip(),
        "beneficiary_category": ben_cat_val,
        "beneficiary_industry": ben_ind_val,
        "ip_address": tx_ip.strip(),
        "geo_location": tx_geo,
        "timestamp_utc": ts_val,
        "simulate_failed_logins": int(sim_fails),
        "simulate_unseen_device": bool(sim_unseen),
        "simulate_impossible_travel_from_home": bool(sim_travel),
        "simulate_rapid_new_beneficiary": bool(sim_rapid_ben),
        "simulate_vendor_bec_bank_update": bool(sim_bec),
    }
    res = create_transaction_live(payload)
    if res["ok"] and isinstance(res["data"], dict):
        new_tx_id = res["data"]["transaction"]["transaction_id"]
        st.session_state["selected_tx_id"] = new_tx_id
        st.session_state["last_live_scored_tx_id"] = new_tx_id
        st.session_state["last_created_tx_response"] = res["data"]
        st.success(
            f"✅ Live Transaction **{new_tx_id}** recorded in SQLite and evaluated! "
            f"Full 3-Method Risk Breakdown is displayed below."
        )
    else:
        st.error(res.get("error", "Failed to create transaction."))


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 · LIVE RISK SCORE & FORENSIC BREAKDOWN FOR THE ACTIVE TRANSACTION
# ══════════════════════════════════════════════════════════════════════════
active_tx_id = st.session_state.get("last_live_scored_tx_id") or st.session_state.get("selected_tx_id", "TX-0391")
tx = get_transaction(active_tx_id)
scores = get_risk_scores(active_tx_id)

if tx and scores:
    st.divider()
    is_live = tx.get("is_live_created", False)
    live_badge = (
        '<span style="background:#10B98122;color:#6EE7B7;border:1px solid #10B981;padding:3px 10px;'
        'border-radius:5px;font-size:0.72rem;font-weight:700;margin-left:10px">⚡ LIVE CREATED TRANSACTION</span>'
        if is_live
        else '<span style="background:#1E293B;color:#94A3B8;border:1px solid #334155;padding:3px 10px;'
        'border-radius:5px;font-size:0.72rem;font-weight:600;margin-left:10px">📂 HISTORICAL BASELINE LEDGER</span>'
    )

    st.markdown(
        f'<div style="display:flex;align-items:center;margin-bottom:12px">'
        f'<h2 style="margin:0">Live Risk Evaluation Results: <code style="color:#21D4C2">{active_tx_id}</code> '
        f'({fmt_currency(tx["amount"])})</h2>{live_badge}</div>',
        unsafe_allow_html=True,
    )

    # 1. Sender Economic & Business Calibration Card
    render_financial_calibration_card(tx)

    # 2. 3-Method Score Cards
    sc1, sc2, sc3 = st.columns(3, gap="medium")
    with sc1:
        render_score_card(
            "Method 1 · Transaction-Only Baseline",
            scores["method1"]["score"],
            scores["method1"]["level"],
            scores["method1"]["description"],
        )
    with sc2:
        render_score_card(
            "Method 2 · Contextual Forensic Scoring",
            scores["method2"]["score"],
            scores["method2"]["level"],
            scores["method2"]["description"],
        )
    with sc3:
        render_score_card(
            "Method 3 · Contextual + Threat Intel",
            scores["method3"]["score"],
            scores["method3"]["level"],
            scores["method3"]["description"],
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Comparative Narrative
    m1s = scores["method1"]["score"]
    m2s = scores["method2"]["score"]
    m3s = scores["method3"]["score"]
    delta_ctx = scores.get("delta_contextual_vs_baseline", m2s - m1s)
    delta_ti = scores.get("delta_ti_vs_contextual", m3s - m2s)

    st.markdown(
        f"""
<div style="background:#0B1929;border:1px solid #1E3A5F;border-left:4px solid #21D4C2;
border-radius:8px;padding:12px 18px;margin-bottom:16px;font-size:0.84rem;color:#E2E8F0;line-height:1.5">
  <b>Comparative Engine Verdict:</b> {scores.get("comparison_narrative","")}
  <span style="margin-left:12px;font-family:monospace;color:#67E8F9">
    [Δ Contextual vs Baseline: {delta_ctx:+d} pts &nbsp;|&nbsp; Δ Threat Intel vs Contextual: {delta_ti:+d} pts]
  </span>
</div>
""",
        unsafe_allow_html=True,
    )

    # 4. Comparison Bar Chart & Rule Contribution Waterfall
    chart_col, waterfall_col = st.columns([1.4, 2.0], gap="large")
    with chart_col:
        fig_cmp = build_score_comparison_chart(scores, threshold=tx.get("user_alert_threshold", 60))
        st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})
    with waterfall_col:
        contribs = scores.get("score_contributions", {})
        if contribs:
            fig_wf = build_waterfall_chart(contribs)
            st.plotly_chart(fig_wf, use_container_width=True, config={"displayModeBar": False})
        else:
            st.success("✓ Zero anomaly points triggered across all 3 methods (0/100 — Clean Routine Transfer).")

    # 5. Triggered Rules Breakdown Table (Showing Exact Math)
    st.markdown(
        '<div class="panel-header">EXACT RULE-BY-RULE CALCULATION &amp; SQLITE EVIDENCE PROVENANCE</div>',
        unsafe_allow_html=True,
    )
    rt1, rt2, rt3 = st.tabs(
        [
            f"M3: Contextual + Threat Intel ({len(scores['method3']['triggered_rules'])} rules fired)",
            f"M2: Contextual Forensic ({len(scores['method2']['triggered_rules'])} rules fired)",
            f"M1: Transaction-Only Baseline ({len(scores['method1']['triggered_rules'])} rules fired)",
        ]
    )
    for tab_obj, method_key in [(rt1, "method3"), (rt2, "method2"), (rt3, "method1")]:
        with tab_obj:
            rules_list = scores[method_key].get("triggered_rules", [])
            if not rules_list:
                st.markdown(
                    '<div style="padding:12px 16px;background:#07291B;border:1px solid #10B98155;border-radius:7px;'
                    'color:#6EE7B7;font-size:0.82rem">✓ Zero anomaly rules triggered in this method (Score = 0/100).</div>',
                    unsafe_allow_html=True,
                )
            else:
                r_rows = ""
                for r in rules_list:
                    pts = r["points_awarded"]
                    max_pts = r["max_points"]
                    pt_col = "#EF4444" if pts >= 25 else "#F59E0B"
                    refs = ", ".join(r.get("evidence_refs", [])) or "transactions"
                    r_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:monospace;font-size:0.75rem;color:#21D4C2;font-weight:600">{r['rule_id']}</td>
  <td style="padding:8px 10px;font-size:0.79rem;color:#F1F5F9;font-weight:600">{r['rule_name']}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#94A3B8;font-family:monospace">{r['category']}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{pt_col};font-family:monospace">+{pts} / {max_pts}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#CBD5E1">{r['explanation']}</td>
  <td style="padding:8px 10px;font-family:monospace;font-size:0.71rem;color:#67E8F9">{refs}</td>
</tr>"""
                st.markdown(
                    f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Rule ID</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Rule Name</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Category</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Points</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Why It Fired</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">SQLite Record IDs</th>
    </tr>
  </thead>
  <tbody>{r_rows}</tbody>
</table>
</div>
""",
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Action Buttons for Deep Investigation or Immediate Incident Escalation
    act1, act2, act3 = st.columns(3, gap="medium")
    with act1:
        if st.button(f"🔬 Inspect {active_tx_id} Kill-Chain Timeline →", use_container_width=True, key="live_to_tl"):
            st.session_state["selected_tx_id"] = active_tx_id
            st.switch_page("pages/4_forensic_investigation.py")
    with act2:
        if st.button(f"⚗️ Open {active_tx_id} in Alert Policy Simulator →", use_container_width=True, key="live_to_pol"):
            st.session_state["selected_tx_id"] = active_tx_id
            st.switch_page("pages/3_risk_analysis_lab.py")
    with act3:
        if st.button(f"🚨 Deny & Create SHA-256 Incident for {active_tx_id}", use_container_width=True, key="live_to_inc"):
            v_res = verify_transaction(
                active_tx_id,
                "confirmed_fraud",
                "Flagged and denied during live interactive presentation.",
            )
            if v_res["success"] and v_res.get("incident"):
                inc = v_res["incident"]
                st.success(f"Created SHA-256 Incident **{inc['incident_id']}** (`{inc['sha256_hash'][:20]}...`)!")
            else:
                st.warning(v_res.get("error", "Incident already exists for this transaction."))


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 · LIVE SESSION TRANSACTIONS CREATED DURING PRESENTATION
# ══════════════════════════════════════════════════════════════════════════
all_txs = get_transactions()
live_txs = [t for t in all_txs if t.get("is_live_created")]

if live_txs:
    st.divider()
    st.markdown(
        f'<div class="panel-header">⚡ TRANSACTIONS CREATED LIVE IN THIS PRESENTATION ({len(live_txs)} RECORDS)</div>',
        unsafe_allow_html=True,
    )
    l_rows = ""
    for lt in live_txs:
        m1_col = RISK_COLOR_MAP.get(lt["method1_level"], "#8A9CB0")
        m2_col = RISK_COLOR_MAP.get(lt["method2_level"], "#8A9CB0")
        m3_col = RISK_COLOR_MAP.get(lt["method3_level"], "#8A9CB0")
        l_rows += f"""
<tr style="border-bottom:1px solid #1E2D3B">
  <td style="padding:8px 10px;font-family:monospace;font-size:0.78rem;color:#21D4C2;font-weight:700">{lt['id']} ⚡</td>
  <td style="padding:8px 10px;font-size:0.74rem;color:#8A9CB0;font-family:monospace">{fmt_ts(lt['timestamp'])}</td>
  <td style="padding:8px 10px;font-size:0.79rem;color:#F1F5F9">{lt['sender_name']}</td>
  <td style="padding:8px 10px">{expenditure_badge_html(lt['sender_expenditure_model'])}</td>
  <td style="padding:8px 10px;font-size:0.79rem;color:#CBD5E1">{lt['beneficiary_name']}</td>
  <td style="padding:8px 10px;font-size:0.82rem;color:#F1F5F9;font-weight:700;font-family:monospace">{fmt_currency(lt['amount'])}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{m1_col}">{lt['method1_score']}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{m2_col}">{lt['method2_score']}</td>
  <td style="padding:8px 10px;text-align:center;font-weight:700;color:{m3_col}">{lt['method3_score']}</td>
  <td style="padding:8px 10px;text-align:center">{risk_badge_html(lt['method3_level'])}</td>
  <td style="padding:8px 10px;text-align:center">{status_badge_html(lt['status'])}</td>
</tr>"""
    st.markdown(
        f"""
<div style="border:1px solid #223342;border-radius:8px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#0E1720">
  <thead>
    <tr style="background:#091119;border-bottom:2px solid #223342">
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Live TX ID</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Timestamp</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Sender</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Model</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Beneficiary</th>
      <th style="padding:8px 10px;text-align:left;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Amount</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M1</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M2</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">M3</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Risk Band</th>
      <th style="padding:8px 10px;text-align:center;font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Status</th>
    </tr>
  </thead>
  <tbody>{l_rows}</tbody>
</table>
</div>
""",
        unsafe_allow_html=True,
    )
