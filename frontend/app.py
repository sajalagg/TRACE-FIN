"""
TRACE-Fin Main Application Entry Point.
Provides a role-based navigation shell:
- Unauthenticated visitors see the Public Landing Page, Sign-In (with Session Network Selector), and Demo Account Registration.
- Authenticated Customers see the 6 Digital Banking pages (Dashboard, Beneficiaries, Transfer Money, Transactions, Security Alerts, Profile / Preferences).
- Authenticated Administrators see the SOC & Forensic Investigation Console (Admin Dashboard, Risk Analysis Lab, Forensic Timeline & Verify, Transaction Ledger, Threat Intelligence, Incidents & Evaluation).
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.config import API_BASE_URL, APP_VERSION
from services.data_provider import (
    check_backend_health,
    invalidate_dataset_cache,
    logout_user,
)
from ui.components import SIDEBAR_LOGO_HTML, fmt_currency, inject_css, render_error

st.set_page_config(
    page_title="TRACE-Fin · Digital Banking & Forensic Risk Protection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Initialize global session state defaults ───────────────────────────────
if "selected_tx_id" not in st.session_state:
    st.session_state["selected_tx_id"] = "TX-0391"
if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = None
if "auth_user" not in st.session_state:
    st.session_state["auth_user"] = None
if "auth_session" not in st.session_state:
    st.session_state["auth_session"] = None

auth_token = st.session_state.get("auth_token")
auth_user = st.session_state.get("auth_user") or {}
auth_session = st.session_state.get("auth_session") or {}
role = auth_user.get("role") if auth_token else None

# ── Build Role-Gated Navigation ────────────────────────────────────────────
if not auth_token or not role:
    pages = [
        st.Page("pages/0_landing_auth.py", title="Welcome & Sign In", default=True),
    ]
elif role == "admin":
    pages = [
        st.Page("pages/1_overview_dashboard.py", title="Admin Dashboard", icon="🏠", default=True),
        st.Page("pages/2_transaction_explorer.py", title="Transaction Explorer", icon="🔍"),
        st.Page("pages/3_risk_analysis_lab.py", title="Risk Analysis Lab", icon="⚗️"),
        st.Page("pages/4_forensic_investigation.py", title="Forensic Investigation", icon="🔬"),
        st.Page("pages/5_threat_intelligence.py", title="Threat Intelligence", icon="🕵️"),
        st.Page("pages/6_incident_register_evaluation.py", title="Model Evaluation", icon="📊"),
    ]
else:
    pages = [
        st.Page("pages/c1_customer_dashboard.py", title="Dashboard", icon="🏦", default=True),
        st.Page("pages/c2_customer_beneficiaries.py", title="Beneficiaries", icon="👥"),
        st.Page("pages/c3_customer_transfer.py", title="Transfer Money", icon="💸"),
        st.Page("pages/c4_customer_transactions.py", title="Transactions", icon="📜"),
        st.Page("pages/c5_customer_security_alerts.py", title="Security Alerts", icon="🚨"),
        st.Page("pages/c6_customer_profile_preferences.py", title="Profile / Preferences", icon="⚙️"),
    ]

pg = st.navigation(pages, position="sidebar")

# ── Global Sidebar Branding & Account Summary ──────────────────────────────
st.sidebar.markdown(SIDEBAR_LOGO_HTML, unsafe_allow_html=True)

health = check_backend_health()

if auth_token and role == "customer":
    bal = float(auth_user.get("simulated_balance", 10000.0))
    st.sidebar.markdown(
        f"""
<div style="margin:0 0 10px;padding:10px 12px;border-radius:8px;border:1px solid #21D4C244;background:#0D1C2A">
  <div style="font-size:0.65rem;color:#21D4C2;font-weight:700;text-transform:uppercase;letter-spacing:0.06em">
    Customer Account · {auth_user.get("user_id","")}
  </div>
  <div style="font-size:0.84rem;font-weight:700;color:#F8FAFC;margin-top:2px">
    {auth_user.get("display_name","Customer")}
  </div>
  <div style="font-size:0.95rem;font-weight:700;color:#10B981;margin-top:6px">
    {fmt_currency(bal)}
  </div>
  <div style="font-size:0.68rem;color:#94A3B8;margin-top:6px;padding-top:6px;border-top:1px solid #1E2D3B">
    📍 {auth_session.get("geo_location","—")} · <code>{auth_session.get("ip_address","—")}</code>
  </div>
</div>""",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🚪 Sign Out", use_container_width=True, key="sidebar_logout_btn"):
        logout_user()
        st.session_state["auth_token"] = None
        st.session_state["auth_user"] = None
        st.session_state["auth_session"] = None
        st.session_state.pop("last_customer_transfer_result", None)
        st.rerun()

elif auth_token and role == "admin":
    st.sidebar.markdown(
        f"""
<div style="margin:0 0 10px;padding:10px 12px;border-radius:8px;border:1px solid #8B5CF655;background:#16122B">
  <div style="font-size:0.65rem;color:#A78BFA;font-weight:700;text-transform:uppercase;letter-spacing:0.06em">
    SOC Administrator · {auth_user.get("user_id","ADMIN-001")}
  </div>
  <div style="font-size:0.83rem;font-weight:700;color:#F8FAFC;margin-top:2px">
    {auth_user.get("display_name","SOC Investigator")}
  </div>
  <div style="font-size:0.68rem;color:#94A3B8;margin-top:6px">
    Session: <code>{auth_session.get("session_id","—")}</code> ({auth_session.get("ip_address","—")})
  </div>
</div>""",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🚪 Sign Out", use_container_width=True, key="sidebar_admin_logout_btn"):
        logout_user()
        st.session_state["auth_token"] = None
        st.session_state["auth_user"] = None
        st.session_state["auth_session"] = None
        st.rerun()

    with st.sidebar.expander("⚙️ System Settings", expanded=False):
        st.caption(f"Service: {API_BASE_URL}")
        if st.button("🔄 Refresh Data Cache", use_container_width=True, key="admin_refresh_btn"):
            invalidate_dataset_cache()
            st.rerun()

if not health["connected"]:
    render_error(
        f"<b>TRACE-Fin API Service Not Reachable at {API_BASE_URL}</b><br>"
        f"Start the backend server with: <code>.venv/bin/uvicorn app.main:app --reload --port 8000</code>"
    )
    st.stop()

pg.run()
