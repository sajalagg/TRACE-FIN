"""
TRACE-Fin Customer Page 2: Beneficiaries Management.
Allows the signed-in customer to view their saved beneficiaries and add new counterparties
(or update bank account details to test B2B Vendor BEC protection).
"""

from __future__ import annotations

import streamlit as st

from services.data_provider import (
    create_beneficiary_live,
    get_user_beneficiaries_list,
)
from ui.components import fmt_ts

auth_user = st.session_state.get("auth_user") or {}
uid = auth_user.get("user_id", "USR-001")

st.markdown("# 👥 Saved Beneficiaries & Counterparties")
st.markdown(
    '<div style="color:#8A9CB0;font-size:0.85rem;margin-top:-10px;margin-bottom:18px">'
    'Manage your trusted payees and suppliers. Newly added beneficiaries or recent bank-detail changes '
    'are automatically evaluated as part of transfer risk protection.</div>',
    unsafe_allow_html=True,
)

col_list, col_add = st.columns([1.35, 1.0])

events = get_user_beneficiaries_list(uid)
latest_by_id = {}
for ev in events:
    latest_by_id[ev["beneficiary_id"]] = ev

with col_list:
    st.markdown(
        f'<div class="panel-header">Your Active Beneficiaries ({len(latest_by_id)})</div>',
        unsafe_allow_html=True,
    )
    if not latest_by_id:
        st.info("You have not added any beneficiaries yet. Use the form on the right to add one.")
    else:
        for ben_id, b in latest_by_id.items():
            ev_type = b.get("event_type", "beneficiary_added")
            badge_col = "#F59E0B" if ev_type == "beneficiary_bank_updated" else "#10B981"
            badge_txt = "Bank Routing Recently Modified" if ev_type == "beneficiary_bank_updated" else "Active Counterparty"
            st.markdown(
                f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:8px;padding:14px 16px;margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
    <div>
      <div style="font-size:0.92rem;font-weight:700;color:#F1F5F9">{b["beneficiary_name"]}</div>
      <div style="font-size:0.74rem;color:#21D4C2;font-family:monospace;margin-top:2px">
        ID: {ben_id} &nbsp;·&nbsp; Category: {b["beneficiary_category"]} &nbsp;·&nbsp; Sector: {b["beneficiary_industry"]}
      </div>
    </div>
    <span style="font-size:0.68rem;font-weight:600;padding:3px 8px;border-radius:4px;
    background:{badge_col}22;color:{badge_col};border:1px solid {badge_col}55">{badge_txt}</span>
  </div>
  <div style="font-size:0.73rem;color:#8A9CB0;margin-top:8px">
    Last Updated: {fmt_ts(b["timestamp_utc"])} · {b.get("notes") or "Saved beneficiary"}
  </div>
</div>""",
                unsafe_allow_html=True,
            )

with col_add:
    st.markdown('<div class="panel-header">Add New Beneficiary or Update Bank Routing</div>', unsafe_allow_html=True)

    action_mode = st.radio(
        "Action",
        options=[
            "Add a New Beneficiary",
            "Update Bank Routing for an Existing Beneficiary",
        ],
        key="cust_ben_action_mode",
    )

    if action_mode.startswith("Add"):
        b_name = st.text_input("Beneficiary Display Name", placeholder="e.g., Horizon Digital Services Ltd", key="cust_ben_name")
        b_id_custom = st.text_input("Optional Beneficiary Reference ID (Leave blank to auto-generate)", value="", key="cust_ben_id")
        b_cat = st.selectbox(
            "Beneficiary Category",
            options=["personal_peer", "verified_b2b_vendor", "employee_payroll", "utility_tax", "financial_brokerage"],
            index=0,
            key="cust_ben_cat",
        )
        b_ind = st.selectbox(
            "Beneficiary Industry / Purpose",
            options=[
                "general_consumer",
                "wholesale_fmcg_inventory",
                "cloud_saas_hosting",
                "heavy_machinery_equipment",
                "raw_materials_steel_cement",
                "digital_assets_brokerage",
                "luxury_retail_jewelry",
                "utilities_municipal",
            ],
            index=0,
            key="cust_ben_ind",
        )
        b_notes = st.text_input("Reference Note", value="Added by account holder in online banking.", key="cust_ben_notes")
        ev_type_val = "beneficiary_added"
    else:
        existing_options = [f"{bid} · {b['beneficiary_name']}" for bid, b in latest_by_id.items()]
        chosen_existing = st.selectbox("Select Existing Beneficiary to Update", options=existing_options or ["None"], key="cust_ben_existing")
        chosen_bid = chosen_existing.split(" · ")[0] if " · " in chosen_existing else "BEN-DEMO-01"
        chosen_obj = latest_by_id.get(chosen_bid, {})
        b_id_custom = chosen_bid
        b_name = chosen_obj.get("beneficiary_name", "Existing Supplier")
        b_cat = chosen_obj.get("beneficiary_category", "verified_b2b_vendor")
        b_ind = chosen_obj.get("beneficiary_industry", "wholesale_fmcg_inventory")
        b_notes = st.text_input(
            "Bank Routing Change Note",
            value="Supplier requested urgent IBAN/routing update prior to invoice payment.",
            key="cust_ben_bec_notes",
        )
        ev_type_val = "beneficiary_bank_updated"

    if st.button("💾 Save Beneficiary Record", type="primary", use_container_width=True, key="cust_save_ben_btn"):
        if not b_name.strip():
            st.error("Please enter a beneficiary name.")
        else:
            res = create_beneficiary_live(
                {
                    "user_id": uid,
                    "beneficiary_id": b_id_custom.strip() or None,
                    "beneficiary_name": b_name.strip(),
                    "beneficiary_category": b_cat,
                    "beneficiary_industry": b_ind,
                    "event_type": ev_type_val,
                    "notes": b_notes.strip(),
                }
            )
            if res["ok"]:
                st.success(f"Saved beneficiary **{b_name.strip()}** for your account!")
                st.rerun()
            else:
                st.error(res.get("error", "Could not save beneficiary."))
