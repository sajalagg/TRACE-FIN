"""
TRACE-Fin Customer Page 6: Profile, Alert Preferences & System Settings.
Displays the customer's baseline financial & home network profile, allows updating
alert thresholds and quiet hours, and houses the technical System / Database sync controls
so technical details appear only in Settings.
"""

from __future__ import annotations

import streamlit as st

from services.config import API_BASE_URL, APP_VERSION
from services.data_provider import (
    check_backend_health,
    get_user_preferences_live,
    get_user_profile,
    invalidate_dataset_cache,
    update_user_preferences_live,
)
from ui.components import fmt_currency, render_demo_banner

render_demo_banner()

auth_user = st.session_state.get("auth_user") or {}
uid = auth_user.get("user_id", "USR-001")
profile = get_user_profile(uid) or auth_user
prefs = get_user_preferences_live(uid) or {
    "risk_threshold": 60,
    "critical_bypass_threshold": 85,
    "timezone_iana": "Asia/Kolkata",
    "quiet_hours_enabled": True,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
}

st.markdown("# ⚙️ Profile, Alert Preferences & Settings")
st.markdown(
    '<div style="color:#8A9CB0;font-size:0.85rem;margin-top:-10px;margin-bottom:18px">'
    'Review your registered account baseline, customize your security alert preferences, '
    'and manage system connection settings.</div>',
    unsafe_allow_html=True,
)

col_prof, col_prefs = st.columns([1.15, 1.15])

with col_prof:
    st.markdown('<div class="panel-header">Account &amp; Home Network Baseline</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div style="background:#0E1720;border:1px solid #223342;border-radius:10px;padding:18px 20px;font-size:0.83rem;color:#CBD5E1;line-height:1.75">
  <div><b>Account Holder:</b> {profile.get("display_name","—")} (<code>{uid}</code>)</div>
  <div><b>Username:</b> <code>@{profile.get("username") or uid.lower()}</code></div>
  <div><b>Simulated Balance:</b> <b style="color:#10B981">{fmt_currency(float(profile.get("simulated_balance",10000.0)))}</b></div>
  <div><b>Account Category / Archetype:</b> {profile.get("account_category","—").title()} · <code>{profile.get("profile_type","—")}</code></div>
  <div><b>Expenditure Model:</b> <code>{profile.get("expenditure_model","—")}</code> ({profile.get("industry_sector","—")})</div>
  <div><b>Declared Monthly Turnover:</b> {fmt_currency(float(profile.get("declared_monthly_turnover",0)))}</div>
  <div><b>Typical / Max Single Transfer:</b> {fmt_currency(float(profile.get("typical_tx_amount",0)))} / {fmt_currency(float(profile.get("typical_max_tx_amount",0)))}</div>
  <hr style="margin:10px 0">
  <div><b>Registered Home Location:</b> <b style="color:#21D4C2">{profile.get("home_geo_location","—")}</b></div>
  <div><b>Trusted Home IP Prefix:</b> <code>{profile.get("home_ip_prefix","103.21.244.")}0/24</code></div>
  <div><b>Normal Operating Hours:</b> <code>{profile.get("operating_hours_utc","04:00-18:00")} UTC</code></div>
</div>""",
        unsafe_allow_html=True,
    )

with col_prefs:
    st.markdown('<div class="panel-header">Security Alert &amp; Quiet-Hours Preferences</div>', unsafe_allow_html=True)

    new_thr = st.slider(
        "Personal Alert Sensitivity Threshold (10–95)",
        min_value=10,
        max_value=95,
        value=int(prefs.get("risk_threshold", 60)),
        help="Transfers scoring at or above this threshold trigger a security notification.",
        key="cust_pref_thr",
    )
    new_crit = st.slider(
        "Critical Quiet-Hours Bypass Threshold (50–100)",
        min_value=50,
        max_value=100,
        value=int(prefs.get("critical_bypass_threshold", 85)),
        help="Critical alerts at or above this score notify you immediately even during quiet hours.",
        key="cust_pref_crit",
    )
    tz_options = [
        "Asia/Kolkata",
        "Asia/Singapore",
        "Europe/London",
        "Asia/Dubai",
        "America/New_York",
        "America/Los_Angeles",
        "UTC",
    ]
    curr_tz = prefs.get("timezone_iana", "Asia/Kolkata")
    tz_idx = tz_options.index(curr_tz) if curr_tz in tz_options else 0
    new_tz = st.selectbox("Local Time Zone (IANA)", options=tz_options, index=tz_idx, key="cust_pref_tz")

    qh_enabled = st.checkbox(
        "Enable Overnight Quiet Hours (Queue non-critical alerts until morning)",
        value=bool(prefs.get("quiet_hours_enabled", True)),
        key="cust_pref_qh_en",
    )
    qc1, qc2 = st.columns(2)
    with qc1:
        qh_start = st.text_input("Quiet Hours Start (HH:MM)", value=str(prefs.get("quiet_hours_start", "22:00")), key="cust_pref_qhs")
    with qc2:
        qh_end = st.text_input("Quiet Hours End (HH:MM)", value=str(prefs.get("quiet_hours_end", "07:00")), key="cust_pref_qhe")

    if st.button("💾 Save Alert Preferences", type="primary", use_container_width=True, key="cust_save_prefs_btn"):
        res = update_user_preferences_live(
            uid,
            {
                "risk_threshold": int(new_thr),
                "critical_bypass_threshold": int(new_crit),
                "timezone_iana": new_tz,
                "quiet_hours_enabled": bool(qh_enabled),
                "quiet_hours_start": qh_start.strip(),
                "quiet_hours_end": qh_end.strip(),
            },
        )
        if res["ok"]:
            st.success("Your security alert preferences have been updated.")
            st.rerun()
        else:
            st.error(res.get("error", "Could not update preferences."))

# ── Technical System & Database Sync Settings (Kept strictly inside Settings) ──
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
with st.expander("🛠️ Advanced System & Database Connection Settings", expanded=False):
    health = check_backend_health()
    st.markdown(
        f"""
<div style="font-size:0.8rem;color:#CBD5E1;line-height:1.6">
  <div><b>Application Build:</b> {APP_VERSION}</div>
  <div><b>API Service Endpoint:</b> <code>{API_BASE_URL}</code></div>
  <div><b>Database Engine Status:</b> {"🟢 Connected (SQLite Local Store)" if health["connected"] else "🔴 Offline"}</div>
</div>""",
        unsafe_allow_html=True,
    )
    if st.button("🔄 Refresh & Sync Local Database Cache", key="settings_sync_db_btn"):
        invalidate_dataset_cache()
        st.success("Database cache synchronized.")
        st.rerun()
