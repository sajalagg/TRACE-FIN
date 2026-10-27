"""
TRACE-Fin Public Landing Page, Sign-In (with Session Network Context Selector),
and Demo Account Registration (with Home IP/Location Onboarding).
"""

from __future__ import annotations

import streamlit as st

from services.data_provider import (
    get_login_network_presets,
    get_users_list,
    login_user,
    register_user,
)
from ui.components import fmt_currency

DEMO_CUSTOMER_PASSWORD = "DemoUser@123"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "AdminTrace@123"
CUSTOM_PRESET_LABEL = "5. Custom IP Address, Location & Device"
NETWORK_TYPES = [
    "home_broadband",
    "corporate_network",
    "public_wifi",
    "commercial_vpn",
    "mobile_roaming",
    "anonymizer_proxy",
]

# ── Page-local styles ──────────────────────────────────────────────────────
st.markdown(
    """
<style>
.tf-hero { text-align:center; padding:26px 20px 18px; margin-bottom:18px;
  background:radial-gradient(ellipse at top,#0F2A33 0%,#09131E 70%);
  border:1px solid #21D4C233; border-radius:16px; }
.tf-logo { width:62px; height:62px; margin:0 auto 10px; border-radius:16px;
  display:flex; align-items:center; justify-content:center; font-size:2rem;
  background:linear-gradient(135deg,#21D4C2 0%,#0E7490 100%);
  box-shadow:0 6px 22px rgba(33,212,194,0.35); }
.tf-title { font-size:2rem; font-weight:800; color:#F8FAFC; letter-spacing:-0.01em; }
.tf-title span { color:#21D4C2; }
.tf-sub { font-size:0.9rem; color:#94A3B8; margin-top:4px; }
.tf-card { background:#0B1520; border:1px solid #1E2E3E; border-radius:12px; padding:14px 16px; margin-top:6px; }
.tf-card-title { font-size:0.7rem; font-weight:700; color:#21D4C2; text-transform:uppercase;
  letter-spacing:0.07em; margin-bottom:8px; }
.tf-ctx { display:grid; grid-template-columns:1fr 1fr; gap:8px 14px; font-size:0.8rem; color:#E2E8F0; }
.tf-ctx div span { display:block; font-size:0.66rem; color:#8A9CB0; text-transform:uppercase; letter-spacing:0.05em; }
.tf-details summary { cursor:pointer; list-style:none; margin-bottom:0; }
.tf-details summary::-webkit-details-marker { display:none; }
.tf-details summary::before { content:"▸ "; }
.tf-details[open] summary::before { content:"▾ "; }
.tf-cred { width:100%; border-collapse:collapse; font-size:0.78rem; color:#CBD5E1; }
.tf-cred th { text-align:left; color:#8A9CB0; font-weight:600; padding:4px 6px; border-bottom:1px solid #1E2D3B; }
.tf-cred td { padding:5px 6px; border-bottom:1px solid #15222E; }
.tf-cred tr:last-child td { border-bottom:none; }
.tf-section { font-size:0.74rem; font-weight:700; color:#CBD5E1; text-transform:uppercase;
  letter-spacing:0.06em; margin:4px 0 6px; padding-bottom:4px; border-bottom:1px solid #1E2D3B; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Hero ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="tf-hero">
  <div class="tf-logo">🛡️</div>
  <div class="tf-title">TRACE<span>-Fin</span></div>
  <div class="tf-sub">Explainable Digital Banking &amp; Forensic Risk Protection</div>
</div>
""",
    unsafe_allow_html=True,
)


def _store_auth(auth_data: dict) -> None:
    st.session_state["auth_token"] = auth_data["session_token"]
    st.session_state["auth_user"] = auth_data["user"]
    st.session_state["auth_session"] = auth_data["session"]


tab_signin, tab_register = st.tabs(["Sign In", "Create Account"])

# ===========================================================================
# TAB 1: SIGN IN WITH SESSION NETWORK & LOCATION SELECTOR
# ===========================================================================
with tab_signin:
    users = get_users_list()
    admin_label = "🛡️ Administrator · SOC Lead Investigator"
    quick_options = ["Custom Username Entry", admin_label]
    user_lookup = {admin_label: (ADMIN_USERNAME, ADMIN_PASSWORD)}
    for u in users:
        uname = u.get("username") or u["user_id"].lower()
        display = u.get("display_name", uname)
        label = f"Customer · {display}"
        if label in user_lookup:
            label = f"Customer · {display} ({u['user_id']})"
        quick_options.append(label)
        user_lookup[label] = (uname, DEMO_CUSTOMER_PASSWORD)

    def _apply_quick_fill() -> None:
        sel = st.session_state.get("login_quick_select")
        if sel in user_lookup:
            st.session_state["login_username_input"], st.session_state["login_password_input"] = user_lookup[sel]

    # Initialise defaults once so quick-fill updates the inputs reliably
    if "login_quick_select" not in st.session_state:
        st.session_state["login_quick_select"] = quick_options[2] if len(quick_options) > 2 else quick_options[0]
        _apply_quick_fill()

    col_login, col_net = st.columns([1, 1.15], gap="large")

    # ── Credentials ────────────────────────────────────────────────────────
    with col_login:
        st.markdown('<div class="panel-header">1 · Account Credentials</div>', unsafe_allow_html=True)
        st.selectbox(
            "Quick-Fill Account",
            options=quick_options,
            key="login_quick_select",
            on_change=_apply_quick_fill,
        )
        username_in = st.text_input(
            "Username or User ID",
            placeholder="e.g., aarav.sharma, novamart.retail, or admin",
            key="login_username_input",
        )
        password_in = st.text_input(
            "Password",
            type="password",
            help="Entering an incorrect password records a failed sign-in attempt on the account timeline.",
            key="login_password_input",
        )

        rows = [
            f"<tr><td>🛡️ Administrator</td><td><code>{ADMIN_USERNAME}</code></td><td><code>{ADMIN_PASSWORD}</code></td></tr>"
        ]
        for u in users:
            uname = u.get("username") or u["user_id"].lower()
            rows.append(
                f"<tr><td>{u.get('display_name', uname)}</td><td><code>{uname}</code></td>"
                f"<td><code>{DEMO_CUSTOMER_PASSWORD}</code></td></tr>"
            )
        st.markdown(
            f"""
<details class="tf-card tf-details">
  <summary class="tf-card-title">🔑 Account Credentials <span style="color:#8A9CB0;font-weight:500;text-transform:none;letter-spacing:0">({len(rows)} accounts · click to expand)</span></summary>
  <table class="tf-cred" style="margin-top:8px">
    <thead><tr><th>Account</th><th>Username</th><th>Password</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</details>""",
            unsafe_allow_html=True,
        )

    # ── Session network / location context ────────────────────────────────
    with col_net:
        st.markdown(
            '<div class="panel-header">2 · Session Network &amp; Location</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Choose the network context for this sign-in. Transfers made during the session are scored "
            "against your historical baseline using this IP, location and device."
        )

        presets = get_login_network_presets(username=(username_in or "").strip() or "aarav.sharma")
        preset_labels = [p["label"] for p in presets] + [CUSTOM_PRESET_LABEL]
        selected_preset_label = st.selectbox("Network Scenario", options=preset_labels, key="login_net_preset")
        chosen = next((p for p in presets if p["label"] == selected_preset_label), presets[0] if presets else {})
        is_custom = selected_preset_label == CUSTOM_PRESET_LABEL

        if is_custom:
            nc1, nc2 = st.columns(2)
            with nc1:
                sim_ip = st.text_input("Session IP Address", value=chosen.get("ip_address", "103.21.244.25"), key="login_sim_ip")
                sim_dev_id = st.text_input("Session Device ID", value=chosen.get("device_id", "DEV-001-PRIMARY"), key="login_sim_dev_id")
                sim_dev_label = st.text_input(
                    "Device Label", value=chosen.get("device_label", "Primary Registered Workstation"), key="login_sim_dev_label"
                )
            with nc2:
                sim_geo = st.text_input(
                    "Approximate Location (City/Country)", value=chosen.get("geo_location", "IN-Mumbai"), key="login_sim_geo"
                )
                default_nt = chosen.get("network_type", "home_broadband")
                sim_net_type = st.selectbox(
                    "Network Environment",
                    options=NETWORK_TYPES,
                    index=NETWORK_TYPES.index(default_nt) if default_nt in NETWORK_TYPES else 0,
                    key="login_sim_net_type",
                )
                sim_fails = st.number_input(
                    "Preceding Failed Logins (0–10)",
                    min_value=0,
                    max_value=10,
                    value=int(chosen.get("simulate_failed_attempts", 0)),
                    key="login_sim_fails",
                )
        else:
            sim_ip = chosen.get("ip_address", "")
            sim_geo = chosen.get("geo_location", "")
            sim_dev_id = chosen.get("device_id", "")
            sim_dev_label = chosen.get("device_label", "")
            sim_net_type = chosen.get("network_type", "home_broadband")
            sim_fails = int(chosen.get("simulate_failed_attempts", 0))

            st.markdown(
                f"""
<div class="tf-card">
  <div class="tf-card-title">📡 Session Context</div>
  <div class="tf-ctx">
    <div><span>IP Address</span><code>{sim_ip or '—'}</code></div>
    <div><span>Location</span>📍 {sim_geo or '—'}</div>
    <div><span>Device</span>{sim_dev_label or '—'}<br><code style="font-size:0.7rem">{sim_dev_id}</code></div>
    <div><span>Network · Failed Logins</span>{sim_net_type} · {sim_fails}</div>
  </div>
  {f'<div style="font-size:0.72rem;color:#94A3B8;margin-top:10px">{chosen.get("description","")}</div>' if chosen.get("description") else ''}
</div>""",
                unsafe_allow_html=True,
            )

        if chosen.get("expected_signal_note"):
            st.markdown(
                f'<div style="font-size:0.75rem;color:#67E8F9;background:#082330;border:1px solid #21D4C244;'
                f'padding:8px 12px;border-radius:8px;margin-top:10px">'
                f'<b>Forensic Signal Preview:</b> {chosen["expected_signal_note"]}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("Sign In & Establish Session", type="primary", use_container_width=True, key="btn_do_login"):
        if not (username_in or "").strip() or not password_in:
            st.error("Please enter both your username and password.")
        else:
            res = login_user(
                {
                    "username": username_in.strip(),
                    "password": password_in,
                    "ip_address": str(sim_ip).strip(),
                    "geo_location": str(sim_geo).strip(),
                    "device_id": str(sim_dev_id).strip(),
                    "device_label": str(sim_dev_label).strip(),
                    "network_type": sim_net_type,
                    "simulate_failed_attempts": int(sim_fails),
                }
            )
            if res["ok"] and isinstance(res["data"], dict):
                _store_auth(res["data"])
                st.rerun()
            else:
                st.error(res.get("error", "Sign-in failed. Please verify your credentials."))

# ===========================================================================
# TAB 2: CREATE NEW ACCOUNT (WITH HOME IP & LOCATION ONBOARDING)
# ===========================================================================
with tab_register:
    st.caption(
        "We record your Home Location, Home IP Address and Primary Trusted Device so the risk engine can "
        "distinguish your normal banking sessions from unfamiliar activity."
    )

    rc1, rc2, rc3 = st.columns(3, gap="large")
    with rc1:
        st.markdown('<div class="tf-section">👤 Account</div>', unsafe_allow_html=True)
        reg_display = st.text_input("Full Name or Business Name", placeholder="e.g., Priya Nair (Product Lead)", key="reg_disp")
        reg_username = st.text_input("Choose Username", placeholder="e.g., priya.nair", key="reg_uname")
        reg_password = st.text_input("Create Password (min 6 chars)", type="password", value=DEMO_CUSTOMER_PASSWORD, key="reg_pw")
        reg_balance = st.number_input(
            "Initial Balance (INR)", min_value=500.0, max_value=5000000.0, value=25000.0, step=1000.0, key="reg_bal"
        )

    with rc2:
        st.markdown('<div class="tf-section">📊 Financial Profile</div>', unsafe_allow_html=True)
        reg_cat = st.selectbox("Account Category", options=["individual", "business"], index=0, key="reg_cat")
        reg_profile = st.selectbox(
            "Employment Type",
            options=[
                "salaried_individual",
                "student",
                "freelancer",
                "HNI indiviuals",
                "small business",
                "enterprise",
            ],
            index=0,
            key="reg_prof",
        )
        reg_exp_model = st.selectbox(
            "Expense Type",
            options=["personal_consumption", "opex_heavy", "capex_heavy"],
            index=0,
            key="reg_exp",
        )
        reg_typical_max = st.number_input(
            "Typical Max Single Transfer (INR)", min_value=100.0, max_value=500000.0, value=1500.0, step=250.0, key="reg_max_tx"
        )

    with rc3:
        st.markdown('<div class="tf-section">🏠 Trusted Baseline</div>', unsafe_allow_html=True)
        reg_home_geo = st.selectbox(
            "Baseline Home Location (City/Country)",
            options=[
                "IN-Bengaluru",
                "IN-Mumbai",
                "IN-Pune",
                "IN-Delhi",
                "SG-Singapore",
                "GB-London",
                "AE-Dubai",
                "US-NewYork",
                "US-SanFrancisco",
            ],
            index=0,
            key="reg_home_geo",
        )
        reg_home_ip = st.text_input(
            "Baseline Home IP Address",
            value="106.51.72.18",
            help="Establishes your trusted home IP prefix for future session comparisons.",
            key="reg_home_ip",
        )
        reg_dev_label = st.text_input("Primary Trusted Device Label", value="Personal Laptop (Trusted)", key="reg_dev_label")
        reg_tz = st.selectbox(
            "Local Time Zone (IANA)",
            options=["Asia/Kolkata", "Asia/Singapore", "Europe/London", "Asia/Dubai", "America/New_York", "America/Los_Angeles", "UTC"],
            index=0,
            key="reg_tz",
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("Create Account & Sign In", type="primary", use_container_width=True, key="btn_do_register"):
        if len(reg_username.strip()) < 3:
            st.error("Please enter a username of at least 3 characters.")
        elif len(reg_password) < 6:
            st.error("Password must be at least 6 characters.")
        elif len(reg_display.strip()) < 2:
            st.error("Please enter your display name or business name.")
        else:
            typical_amt = max(25.0, round(float(reg_typical_max) * 0.15, 2))
            res = register_user(
                {
                    "username": reg_username.strip(),
                    "password": reg_password,
                    "display_name": reg_display.strip(),
                    "account_category": reg_cat,
                    "profile_type": reg_profile,
                    "industry_sector": "personal_finance" if reg_cat == "individual" else "retail_ecommerce",
                    "expenditure_model": reg_exp_model,
                    "net_worth_band": "₹25K-₹100K" if reg_cat == "individual" else "₹250K-₹1M",
                    "estimated_net_worth": float(reg_balance) * 2.5,
                    "declared_monthly_turnover": float(reg_typical_max) * 3.5,
                    "typical_tx_amount": typical_amt,
                    "typical_max_tx_amount": float(reg_typical_max),
                    "expected_monthly_tx_count": 30,
                    "operating_hours_utc": "04:00-18:00",
                    "home_geo_location": reg_home_geo,
                    "home_ip_address": reg_home_ip.strip(),
                    "primary_device_label": reg_dev_label.strip(),
                    "simulated_balance": float(reg_balance),
                    "risk_threshold": 60,
                    "timezone_iana": reg_tz,
                }
            )
            if res["ok"] and isinstance(res["data"], dict):
                _store_auth(res["data"])
                st.rerun()
            else:
                st.error(res.get("error", "Registration failed."))
