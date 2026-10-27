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

# ── Hero Section ───────────────────────────────────────────────────────────
st.markdown(
    """
<div style="background:linear-gradient(135deg,#0B1D30 0%,#09131E 60%,#0D2329 100%);
border:1px solid #21D4C244;border-radius:14px;padding:28px 32px;margin-bottom:20px;
box-shadow:0 8px 28px rgba(0,0,0,0.35)">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">
    <div style="max-width:760px">
      <div style="display:inline-block;padding:4px 10px;border-radius:20px;background:#21D4C21A;
      border:1px solid #21D4C255;color:#21D4C2;font-size:0.7rem;font-weight:700;
      letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px">
        🛡️ Explainable Digital Banking &amp; Forensic Security
      </div>
      <h1 style="margin:0 0 8px 0;font-size:2.05rem !important;color:#F8FAFC !important">
        TRACE-Fin Digital Banking Portal
      </h1>
      <div style="font-size:0.95rem;color:#CBD5E1;line-height:1.55;margin-bottom:12px">
        <b>Transaction Risk Analysis, Correlation, and Escalation for Finance.</b>
        Experience a simulated online banking platform protected by an explainable, multi-signal forensic risk engine
        that evaluates login session context, beneficiary provenance, and account behavior before funds move.
      </div>
      <div style="font-size:0.78rem;color:#FDE68A;background:#2D220A;border:1px solid #F59E0B66;
      padding:7px 12px;border-radius:7px;display:inline-block">
        ℹ️ <b>Simulation Notice:</b> Educational prototype only — all accounts, balances, beneficiaries, and transfers are 100% synthetic. No real money moves.
      </div>
    </div>
    <div style="background:#0B1520;border:1px solid #1E2E3E;border-radius:10px;padding:16px 20px;min-width:260px">
      <div style="font-size:0.7rem;font-weight:700;color:#21D4C2;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:8px">
        How Risk Protection Works
      </div>
      <div style="font-size:0.78rem;color:#CBD5E1;line-height:1.6">
        • <b>Low Risk (&lt;40):</b> Instant transfer completion<br>
        • <b>Medium Risk (40–74):</b> Step-up customer verification<br>
        • <b>High Risk (75–100):</b> Security hold &amp; Risk Lab review<br>
        • <b>Travel-Safe:</b> A new IP or VPN alone never auto-blocks
      </div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Primary Actions: Sign In vs Create Demo Account ────────────────────────
tab_signin, tab_register, tab_how = st.tabs(
    [
        "🔐 Sign In to Your Account (Primary)",
        "✨ Create New Demo Account (Secondary)",
        "📖 Multi-Signal Session & Risk Overview",
    ]
)

# ===========================================================================
# TAB 1: SIGN IN WITH SESSION NETWORK & LOCATION SELECTOR
# ===========================================================================
with tab_signin:
    col_login, col_net = st.columns([1.05, 1.25])

    users = get_users_list()
    quick_options = ["Custom Username Entry"]
    user_lookup = {}
    for u in users:
        uname = u.get("username") or u["user_id"].lower()
        label = (
            f"Customer · {u['display_name']} (@{uname} | Bal: {fmt_currency(float(u.get('simulated_balance', 10000)))})"
        )
        quick_options.append(label)
        user_lookup[label] = (uname, "DemoUser@123", u)

    admin_label = "🛡️ Administrator · TRACE-Fin SOC Lead Investigator (@admin)"
    quick_options.insert(1, admin_label)
    user_lookup[admin_label] = ("admin", "AdminTrace@123", {"user_id": "ADMIN-001", "home_geo_location": "IN-Mumbai"})

    with col_login:
        st.markdown('<div class="panel-header">1. Account Credentials</div>', unsafe_allow_html=True)

        selected_quick = st.selectbox(
            "Quick-Fill Demo Account (or choose Custom Username)",
            options=quick_options,
            index=2 if len(quick_options) > 2 else 0,
            key="login_quick_select",
        )

        default_uname = ""
        default_pw = ""
        if selected_quick in user_lookup:
            default_uname, default_pw, _ = user_lookup[selected_quick]

        username_in = st.text_input(
            "Username or User ID",
            value=default_uname,
            placeholder="e.g., aarav.sharma, novamart.retail, or admin",
            key="login_username_input",
        )
        password_in = st.text_input(
            "Password",
            value=default_pw,
            type="password",
            help="Default customer password: DemoUser@123 · Default admin password: AdminTrace@123",
            key="login_password_input",
        )

        st.markdown(
            '<div style="font-size:0.74rem;color:#94A3B8;margin-top:6px">'
            '💡 <b>Tip:</b> Entering an incorrect password records a failed sign-in attempt on your account timeline. '
            'Demo customer password: <code>DemoUser@123</code> · Admin password: <code>AdminTrace@123</code></div>',
            unsafe_allow_html=True,
        )

    with col_net:
        st.markdown(
            '<div class="panel-header">2. Session Network &amp; Location Selector (Demo Simulation)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:0.76rem;color:#94A3B8;margin-bottom:10px">'
            'Select the network context for this sign-in session. When you initiate a transfer during this session, '
            'the risk engine compares this session with your historical baseline.</div>',
            unsafe_allow_html=True,
        )

        presets = get_login_network_presets(username=username_in.strip() or "aarav.sharma")
        preset_labels = [p["label"] for p in presets] + ["5. Custom IP Address, Location & Device"]
        selected_preset_label = st.selectbox(
            "Session Network Scenario Preset",
            options=preset_labels,
            index=0,
            key="login_net_preset",
        )

        chosen_preset = next((p for p in presets if p["label"] == selected_preset_label), presets[0] if presets else {})
        is_custom = selected_preset_label.startswith("5.")

        nc1, nc2 = st.columns(2)
        with nc1:
            sim_ip = st.text_input(
                "Session IP Address",
                value=chosen_preset.get("ip_address", "103.21.244.25"),
                disabled=not is_custom,
                key="login_sim_ip",
            )
            sim_dev_id = st.text_input(
                "Session Device ID",
                value=chosen_preset.get("device_id", "DEV-001-PRIMARY"),
                disabled=not is_custom,
                key="login_sim_dev_id",
            )
        with nc2:
            sim_geo = st.text_input(
                "Approximate Location (City/Country)",
                value=chosen_preset.get("geo_location", "IN-Mumbai"),
                disabled=not is_custom,
                key="login_sim_geo",
            )
            net_types = [
                "home_broadband",
                "corporate_network",
                "public_wifi",
                "commercial_vpn",
                "mobile_roaming",
                "anonymizer_proxy",
            ]
            default_nt = chosen_preset.get("network_type", "home_broadband")
            nt_idx = net_types.index(default_nt) if default_nt in net_types else 0
            sim_net_type = st.selectbox(
                "Network Environment",
                options=net_types,
                index=nt_idx,
                disabled=not is_custom,
                key="login_sim_net_type",
            )

        nc3, nc4 = st.columns([1.4, 1.0])
        with nc3:
            sim_dev_label = st.text_input(
                "Device Label",
                value=chosen_preset.get("device_label", "Primary Registered Workstation"),
                disabled=not is_custom,
                key="login_sim_dev_label",
            )
        with nc4:
            sim_fails = st.number_input(
                "Preceding Failed Logins (0–10)",
                min_value=0,
                max_value=10,
                value=int(chosen_preset.get("simulate_failed_attempts", 0)),
                disabled=not is_custom,
                key="login_sim_fails",
            )

        if chosen_preset.get("expected_signal_note"):
            st.markdown(
                f'<div style="font-size:0.75rem;color:#67E8F9;background:#082330;border:1px solid #21D4C244;'
                f'padding:8px 12px;border-radius:6px;margin-top:6px">'
                f'<b>Forensic Signal Preview:</b> {chosen_preset["expected_signal_note"]}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🔐 Sign In & Establish Session", type="primary", use_container_width=True, key="btn_do_login"):
        if not username_in.strip() or not password_in:
            st.error("Please enter both your username and password.")
        else:
            res = login_user(
                {
                    "username": username_in.strip(),
                    "password": password_in,
                    "ip_address": sim_ip.strip(),
                    "geo_location": sim_geo.strip(),
                    "device_id": sim_dev_id.strip(),
                    "device_label": sim_dev_label.strip(),
                    "network_type": sim_net_type,
                    "simulate_failed_attempts": int(sim_fails),
                }
            )
            if res["ok"] and isinstance(res["data"], dict):
                auth_data = res["data"]
                st.session_state["auth_token"] = auth_data["session_token"]
                st.session_state["auth_user"] = auth_data["user"]
                st.session_state["auth_session"] = auth_data["session"]
                st.rerun()
            else:
                st.error(res.get("error", "Sign-in failed. Please verify your credentials."))

# ===========================================================================
# TAB 2: CREATE NEW DEMO ACCOUNT (WITH HOME IP & LOCATION ONBOARDING)
# ===========================================================================
with tab_register:
    st.markdown(
        '<div class="panel-header">Create a New Demo Customer Account &amp; Establish Baseline Network Context</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:0.78rem;color:#94A3B8;margin-bottom:14px">'
        'When you create an account, we record your <b>Home City/Location</b>, <b>Home IP Address</b>, and '
        '<b>Primary Trusted Device</b> so the risk engine can distinguish your normal banking sessions from unfamiliar activity.</div>',
        unsafe_allow_html=True,
    )

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        reg_username = st.text_input("Choose Username", placeholder="e.g., priya.nair", key="reg_uname")
        reg_password = st.text_input("Create Password (min 6 chars)", type="password", value="DemoUser@123", key="reg_pw")
        reg_display = st.text_input("Full Name or Business Name", placeholder="e.g., Priya Nair (Product Lead)", key="reg_disp")
        reg_balance = st.number_input("Initial Simulated Balance (USD)", min_value=500.0, max_value=5000000.0, value=25000.0, step=1000.0, key="reg_bal")

    with rc2:
        reg_cat = st.selectbox("Account Category", options=["individual", "business"], index=0, key="reg_cat")
        reg_profile = st.selectbox(
            "Profile Archetype",
            options=[
                "salaried_individual",
                "student",
                "freelancer",
                "high_net_worth",
                "sme_opex_merchant",
                "enterprise_capex_firm",
            ],
            index=0,
            key="reg_prof",
        )
        reg_exp_model = st.selectbox(
            "Expenditure Model",
            options=["personal_consumption", "opex_heavy", "capex_heavy"],
            index=0,
            key="reg_exp",
        )
        reg_typical_max = st.number_input("Typical Max Single Transfer (USD)", min_value=100.0, max_value=500000.0, value=1500.0, step=250.0, key="reg_max_tx")

    with rc3:
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
        reg_dev_label = st.text_input(
            "Primary Trusted Device Label",
            value="Personal Laptop (Trusted)",
            key="reg_dev_label",
        )
        reg_tz = st.selectbox(
            "Local Time Zone (IANA)",
            options=["Asia/Kolkata", "Asia/Singapore", "Europe/London", "Asia/Dubai", "America/New_York", "America/Los_Angeles", "UTC"],
            index=0,
            key="reg_tz",
        )

    if st.button("✨ Create Demo Account & Sign In", type="primary", use_container_width=True, key="btn_do_register"):
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
                    "net_worth_band": "$25K-$100K" if reg_cat == "individual" else "$250K-$1M",
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
                auth_data = res["data"]
                st.session_state["auth_token"] = auth_data["session_token"]
                st.session_state["auth_user"] = auth_data["user"]
                st.session_state["auth_session"] = auth_data["session"]
                st.rerun()
            else:
                st.error(res.get("error", "Registration failed."))

# ===========================================================================
# TAB 3: EXPLAINABLE MULTI-SIGNAL CORRELATION TABLE
# ===========================================================================
with tab_how:
    st.markdown(
        """
<div class="panel">
  <div class="panel-header">How Login Session &amp; Transfer Signals Combine</div>
  <div style="font-size:0.83rem;color:#CBD5E1;line-height:1.6;margin-bottom:14px">
    A new IP address or unfamiliar location <b>alone</b> never automatically blocks a transaction—people travel,
    switch Wi-Fi networks, and use VPNs legitimately. Instead, TRACE-Fin combines signals across your login session,
    beneficiary history, and transaction profile, and explains every point.
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:0.8rem">
    <thead>
      <tr style="border-bottom:1px solid #223342;color:#8A9CB0;text-align:left">
        <th style="padding:8px 10px">Signal</th>
        <th style="padding:8px 10px">Example</th>
        <th style="padding:8px 10px">Typical Risk Contribution</th>
        <th style="padding:8px 10px">Standalone Policy Outcome</th>
      </tr>
    </thead>
    <tbody style="color:#E2E8F0">
      <tr style="border-bottom:1px solid #1E2D3B">
        <td style="padding:8px 10px;font-weight:600;color:#21D4C2">New IP / Unusual Location</td>
        <td style="padding:8px 10px">Bengaluru baseline, login from Singapore hotel Wi-Fi</td>
        <td style="padding:8px 10px">Low to Moderate (+10 to +15 pts)</td>
        <td style="padding:8px 10px"><span class="badge badge-settled">Completed</span> (Does not block travel)</td>
      </tr>
      <tr style="border-bottom:1px solid #1E2D3B">
        <td style="padding:8px 10px;font-weight:600;color:#21D4C2">New Unseen Device</td>
        <td style="padding:8px 10px">Device not previously associated with account</td>
        <td style="padding:8px 10px">Moderate (+18 pts)</td>
        <td style="padding:8px 10px"><span class="badge badge-settled">Completed</span> if routine amount &amp; payee</td>
      </tr>
      <tr style="border-bottom:1px solid #1E2D3B">
        <td style="padding:8px 10px;font-weight:600;color:#F59E0B">Failed Login Attempts</td>
        <td style="padding:8px 10px">3+ failed logins shortly before successful sign-in</td>
        <td style="padding:8px 10px">Moderate to High (+18 to +25 pts)</td>
        <td style="padding:8px 10px"><span class="badge badge-pending">Pending Verification</span> when paired with transfer</td>
      </tr>
      <tr style="border-bottom:1px solid #1E2D3B">
        <td style="padding:8px 10px;font-weight:600;color:#F59E0B">Rapid New Beneficiary / Bank Change</td>
        <td style="padding:8px 10px">Counterparty added or IBAN modified minutes before wire</td>
        <td style="padding:8px 10px">Moderate to High (+18 to +30 pts)</td>
        <td style="padding:8px 10px"><span class="badge badge-pending">Pending Verification</span></td>
      </tr>
      <tr>
        <td style="padding:8px 10px;font-weight:600;color:#EF4444">Multiple Signals Together</td>
        <td style="padding:8px 10px">New device + unusual IP + failed logins + new beneficiary</td>
        <td style="padding:8px 10px">High / Critical (75–100 pts)</td>
        <td style="padding:8px 10px"><span class="badge badge-flagged">Held (High Risk)</span> — Admin Risk Lab Review</td>
      </tr>
    </tbody>
  </table>
</div>
""",
        unsafe_allow_html=True,
    )
