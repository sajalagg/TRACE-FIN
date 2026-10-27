"""
TRACE-Fin Main Application Entry Point.
Configures Streamlit multipage navigation with Live Transaction & Risk Scorer as the primary landing page.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.config import API_BASE_URL, APP_VERSION
from services.data_provider import check_backend_health, invalidate_dataset_cache
from ui.components import SIDEBAR_LOGO_HTML, inject_css, render_error

st.set_page_config(
    page_title="TRACE-Fin · Live Transaction Verification & DFIR Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Initialize global session state defaults ───────────────────────────────
if "selected_tx_id" not in st.session_state:
    st.session_state["selected_tx_id"] = "TX-0391"

# ── Build multipage navigation (Live Transaction Scorer is #1 Default Page) ─
pages = [
    st.Page("pages/7_live_demo_studio.py", title="Live Transaction Scorer", icon="⚡", default=True),
    st.Page("pages/3_risk_analysis_lab.py", title="Risk Analysis & Policy Lab", icon="⚗️"),
    st.Page("pages/4_forensic_investigation.py", title="Forensic Timeline & Verify", icon="🔬"),
    st.Page("pages/1_overview_dashboard.py", title="SOC Overview & Queue", icon="🏠"),
    st.Page("pages/2_transaction_explorer.py", title="Historical Account Ledger", icon="🔍"),
    st.Page("pages/5_threat_intelligence.py", title="Threat Intelligence Feed", icon="🕵️"),
    st.Page("pages/6_incident_register_evaluation.py", title="Incidents & Model Eval", icon="📋"),
]

pg = st.navigation(pages, position="sidebar")

# ── Global Sidebar Branding & Live FastAPI Health ──────────────────────────
st.sidebar.markdown(SIDEBAR_LOGO_HTML, unsafe_allow_html=True)

health = check_backend_health()
if health["connected"]:
    st.sidebar.markdown(
        f'<div style="margin:0 0 8px;padding:7px 11px;border-radius:6px;'
        f'border:1px solid #10B98155;background:#10B98114;'
        f'font-size:0.71rem;color:#6EE7B7;font-weight:600">'
        f'● FastAPI + SQLite Engine Online<br>'
        f'<span style="font-size:0.63rem;color:#94A3B8;font-family:monospace">{API_BASE_URL}</span></div>',
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        f'<div style="margin:0 0 8px;padding:7px 11px;border-radius:6px;'
        f'border:1px solid #EF444466;background:#EF444418;'
        f'font-size:0.71rem;color:#FCA5A5;font-weight:600">'
        f'✕ FastAPI Backend Offline<br>'
        f'<span style="font-size:0.63rem;color:#FCA5A5;font-family:monospace">{API_BASE_URL}</span></div>',
        unsafe_allow_html=True,
    )

if st.sidebar.button("🔄 Sync SQLite Ledger", use_container_width=True, key="global_refresh_btn"):
    invalidate_dataset_cache()
    st.rerun()

st.sidebar.markdown(
    f'<div style="font-size:0.64rem;color:#64748B;padding:4px 4px 8px">'
    f'{APP_VERSION}</div>',
    unsafe_allow_html=True,
)

if not health["connected"]:
    render_error(
        f"<b>FastAPI Backend Not Reachable at {API_BASE_URL}</b><br>"
        f"Start the backend server with: <code>.venv/bin/uvicorn app.main:app --reload --port 8000</code>"
    )
    st.stop()

pg.run()
