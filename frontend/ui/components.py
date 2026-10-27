"""
TRACE-Fin UI Components Library.
Shared reusable components: badges, KPI cards, financial profile calibration cards,
kill-chain progress ribbon, chart templates, timeline renderer, and executive SOC CSS.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Design Tokens
# ---------------------------------------------------------------------------

COLORS = {
    "bg_primary": "#070B10",
    "bg_panel": "#0E1720",
    "bg_card": "#13202B",
    "border": "#223342",
    "text_primary": "#EDF2F7",
    "text_muted": "#8A9CB0",
    "accent_cyan": "#21D4C2",
    "accent_teal": "#21D4C2",
    "accent_purple": "#8B5CF6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "critical": "#DC2626",
    "low": "#10B981",
    "medium": "#F59E0B",
    "high": "#EF4444",
    "plotly_bg": "#0E1720",
    "plotly_grid": "#1E2D3B",
    "plotly_text": "#8A9CB0",
}

RISK_COLOR_MAP = {
    "Low": "#10B981",
    "Medium": "#F59E0B",
    "High": "#EF4444",
    "Critical": "#DC2626",
    "low": "#10B981",
    "medium": "#F59E0B",
    "high": "#EF4444",
    "critical": "#DC2626",
}

STATUS_COLOR_MAP = {
    "Settled": "#10B981",
    "Pending Review": "#F59E0B",
    "Flagged": "#EF4444",
    "Blocked": "#DC2626",
    "In Review": "#F59E0B",
    "Escalated": "#DC2626",
    "Open": "#EF4444",
    "Closed": "#10B981",
}

EXPENDITURE_BADGE_MAP = {
    "capex_heavy": ("CapEx Enterprise", "#8B5CF6"),
    "opex_heavy": ("OpEx Merchant", "#21D4C2"),
    "personal_consumption": ("Personal Account", "#3B82F6"),
}


# ---------------------------------------------------------------------------
# CSS Injection
# ---------------------------------------------------------------------------

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Root & Reset ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background: radial-gradient(circle at 15% 0%, #0D1C2A 0%, #070B10 55%);
}

.block-container {
    padding-top: 1.8rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1440px !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0A121C 0%, #070C12 100%) !important;
    border-right: 1px solid #1E2E3E;
}

section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {
    color: #D5E0EA !important;
}

/* ── Headers ──────────────────────────────────────────────────────────── */
h1, h2, h3, h4 {
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.025em;
}

h1 { color: #F1F5F9 !important; font-weight: 700; font-size: 1.75rem !important; }
h2 { color: #E2E8F0 !important; font-weight: 600; font-size: 1.3rem !important; }
h3 { color: #CBD5E1 !important; font-weight: 600; font-size: 1.05rem !important; }

/* ── Metric Cards ─────────────────────────────────────────────────────── */
.kpi-card {
    background: linear-gradient(145deg, #13212E 0%, #0D1620 100%);
    border: 1px solid #223342;
    border-radius: 10px;
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.28);
    transition: transform 0.15s ease, border-color 0.2s ease;
}
.kpi-card:hover {
    border-color: #21D4C266;
    transform: translateY(-1px);
}
.kpi-card .kpi-value {
    font-size: 2.0rem;
    font-weight: 700;
    color: #F1F5F9;
    line-height: 1.1;
    font-family: 'Inter', sans-serif;
    font-variant-numeric: tabular-nums;
}
.kpi-card .kpi-label {
    font-size: 0.7rem;
    font-weight: 600;
    color: #8A9CB0;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 6px;
}
.kpi-card .kpi-accent {
    position: absolute;
    top: 0; left: 0;
    width: 3.5px;
    height: 100%;
    border-radius: 10px 0 0 10px;
}
.kpi-card .kpi-delta {
    font-size: 0.74rem;
    margin-top: 6px;
    font-weight: 500;
}

/* ── Risk & Status Badges ─────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 5px;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-family: 'Inter', sans-serif;
}
.badge-critical { background: #3B0A0A; color: #FCA5A5; border: 1px solid #DC2626; }
.badge-high     { background: #331507; color: #FDBA74; border: 1px solid #EF4444; }
.badge-medium   { background: #2D220A; color: #FDE68A; border: 1px solid #F59E0B; }
.badge-low      { background: #07291B; color: #6EE7B7; border: 1px solid #10B981; }
.badge-settled  { background: #07291B; color: #6EE7B7; border: 1px solid #10B981; }
.badge-flagged  { background: #3B0A0A; color: #FCA5A5; border: 1px solid #EF4444; }
.badge-blocked  { background: #3B0A0A; color: #FCA5A5; border: 1px solid #DC2626; }
.badge-pending  { background: #2D220A; color: #FDE68A; border: 1px solid #F59E0B; }
.badge-active-ti { background: #082330; color: #67E8F9; border: 1px solid #21D4C2; }
.badge-expired-ti { background: #182026; color: #9CA3AF; border: 1px solid #374151; }

/* ── Evidence Timeline ────────────────────────────────────────────────── */
.timeline-event {
    display: flex;
    gap: 14px;
    padding: 14px 0;
    border-bottom: 1px solid #1E2D3B;
    position: relative;
}
.timeline-event:last-child { border-bottom: none; }
.timeline-dot {
    width: 12px; height: 12px;
    border-radius: 50%;
    margin-top: 4px;
    flex-shrink: 0;
    box-shadow: 0 0 9px currentColor;
}
.timeline-connector {
    position: absolute;
    left: 5px;
    top: 24px;
    bottom: -1px;
    width: 2px;
    background: #223342;
}
.timeline-content { flex: 1; }
.timeline-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.timeline-time { font-size: 0.72rem; color: #8A9CB0; font-family: 'JetBrains Mono', monospace; }
.timeline-type { font-size: 0.7rem; color: #21D4C2; font-weight: 600; letter-spacing: 0.05em; font-family: 'JetBrains Mono', monospace; }
.timeline-phase { font-size: 0.65rem; padding: 2px 7px; border-radius: 4px; font-weight: 600; }
.timeline-fact { font-size: 0.82rem; color: #E2E8F0; line-height: 1.45; margin-bottom: 4px; }
.timeline-interp { font-size: 0.77rem; color: #93C5FD; background: #0B1929; border-left: 2px solid #3B82F6; padding: 5px 10px; border-radius: 0 4px 4px 0; margin: 4px 0; }
.timeline-entity { font-size: 0.71rem; color: #8A9CB0; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }

/* ── Section panels ───────────────────────────────────────────────────── */
.panel {
    background: #0E1720;
    border: 1px solid #223342;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.panel-header {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8A9CB0;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #223342;
}

/* ── Score Display ─────────────────────────────────────────────────────  */
.score-card {
    background: linear-gradient(160deg, #13212E 0%, #0E1720 100%);
    border: 1px solid #223342;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22);
}
.score-value {
    font-size: 3.3rem;
    font-weight: 700;
    line-height: 1;
    font-variant-numeric: tabular-nums;
}
.score-method {
    font-size: 0.72rem;
    color: #CBD5E1;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 8px;
}

/* ── Demo Banner ──────────────────────────────────────────────────────── */
.demo-banner {
    background: linear-gradient(90deg, #0A2239 0%, #091B2E 100%);
    border: 1px solid #21D4C23A;
    border-radius: 7px;
    padding: 7px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-size: 0.73rem;
    color: #67E8F9;
    font-weight: 500;
    letter-spacing: 0.03em;
    margin-bottom: 14px;
}
.demo-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #10B981;
    box-shadow: 0 0 8px #10B981;
    display: inline-block;
    margin-right: 7px;
}

/* ── Dividers & Widgets ───────────────────────────────────────────────── */
hr { border-color: #1E2D3B !important; margin: 16px 0 !important; }

.stSelectbox label, .stMultiSelect label, .stSlider label, .stTextInput label, .stNumberInput label, .stTextArea label {
    color: #94A3B8 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.stButton > button {
    background: linear-gradient(135deg, #132230 0%, #0E1924 100%);
    border: 1px solid #283C4F;
    color: #E2E8F0;
    border-radius: 7px;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.45rem 1rem;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    border-color: #21D4C2;
    color: #21D4C2;
    background: #0B2236;
}

/* ── Scenario Cards ───────────────────────────────────────────────────── */
.scenario-card {
    background: linear-gradient(145deg, #111D28 0%, #0D161F 100%);
    border: 1px solid #223342;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.scenario-card:hover { border-color: #21D4C255; }
.scenario-card.attack { border-left: 3.5px solid #EF4444; }
.scenario-card.legitimate { border-left: 3.5px solid #10B981; }
.scenario-title { font-size: 0.86rem; font-weight: 600; color: #F1F5F9; margin-bottom: 4px; }
.scenario-headline { font-size: 0.76rem; color: #94A3B8; margin-bottom: 6px; line-height: 1.4; }
.scenario-lesson { font-size: 0.73rem; color: #67E8F9; line-height: 1.4; }
</style>
"""


def inject_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _indian_group(n: int) -> str:
    """Group an integer using the Indian numbering system (e.g., 12,34,567)."""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + s


def fmt_currency(amount: float, currency: str = "INR") -> str:
    amount = float(amount)
    if abs(amount) >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} Cr"
    whole = int(round(amount)) if amount % 1 == 0 else int(amount)
    if amount % 1 == 0 and abs(amount) >= 1_000:
        return f"₹{_indian_group(whole)}"
    paise = f"{abs(amount) % 1:.2f}"[1:]
    return f"₹{_indian_group(whole)}{paise}"


def fmt_score(score: int) -> str:
    return f"{score}/100"


def fmt_ts(ts: str) -> str:
    try:
        dt = pd.to_datetime(ts)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# Badge helpers
# ---------------------------------------------------------------------------

def risk_badge_html(level: str) -> str:
    css_class = f"badge badge-{level.lower()}"
    return f'<span class="{css_class}">{level}</span>'


def status_badge_html(status: str) -> str:
    mapping = {
        "Settled": "badge-settled",
        "COMPLETED": "badge-settled",
        "Completed": "badge-settled",
        "Pending Review": "badge-pending",
        "PENDING_VERIFICATION": "badge-pending",
        "Pending Verification": "badge-pending",
        "Flagged": "badge-flagged",
        "HELD_HIGH_RISK": "badge-flagged",
        "Held (High Risk)": "badge-flagged",
        "Blocked": "badge-blocked",
        "BLOCKED": "badge-blocked",
        "Open": "badge-flagged",
        "In Review": "badge-pending",
        "Escalated": "badge-blocked",
        "Closed": "badge-settled",
    }
    css = f"badge {mapping.get(status, 'badge-pending')}"
    return f'<span class="{css}">{status}</span>'


def ti_badge_html(status: str) -> str:
    if status == "ACTIVE":
        return '<span class="badge badge-active-ti">● ACTIVE</span>'
    return '<span class="badge badge-expired-ti">✕ EXPIRED</span>'


def expenditure_badge_html(exp_model: str) -> str:
    label, color = EXPENDITURE_BADGE_MAP.get(exp_model, (exp_model, "#8A9CB0"))
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'font-size:0.67rem;font-weight:600;background:{color}22;color:{color};'
        f'border:1px solid {color}55">{label}</span>'
    )


# ---------------------------------------------------------------------------
# KPI Card
# ---------------------------------------------------------------------------

def kpi_card(
    label: str,
    value: str,
    accent_color: str = "#21D4C2",
    delta_text: Optional[str] = None,
    delta_positive: bool = True,
) -> str:
    delta_color = "#10B981" if delta_positive else "#F59E0B"
    delta_html = f'<div class="kpi-delta" style="color:{delta_color}">{delta_text}</div>' if delta_text else ""
    return f"""
<div class="kpi-card">
  <div class="kpi-accent" style="background:{accent_color}"></div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-label">{label}</div>
  {delta_html}
</div>"""


def render_kpi_row(metrics: List[Dict[str, Any]]) -> None:
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            st.markdown(
                kpi_card(
                    label=m["label"],
                    value=m["value"],
                    accent_color=m.get("color", "#21D4C2"),
                    delta_text=m.get("delta"),
                    delta_positive=m.get("delta_positive", True),
                ),
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Demo Environment Banner & Financial Calibration Card
# ---------------------------------------------------------------------------

def render_demo_banner() -> None:
    st.markdown(
        '<div class="demo-banner">'
        '<div><span class="demo-dot"></span>'
        '<b>DIGITAL BANKING &amp; FORENSIC RISK PROTECTION</b> · '
        'Risk scores (0–100) are explainable rule-based indicators, not probabilities</div>'
        '<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.68rem;color:#21D4C2">TRACE-Fin Protection Active</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_two_line_customer_explainer(
    tx_status: str,
    risk_score: int,
    reasons: Optional[List[str]] = None,
) -> None:
    """Render a concise 2-line plain-language explainer when a customer's transfer is rated Medium or Higher."""
    if tx_status in ("COMPLETED", "Settled") and risk_score < 40:
        return

    reason_snippet = (
        reasons[0]
        if reasons
        else "This transfer differed from your usual sign-in location, device, or beneficiary pattern."
    )
    if tx_status in ("BLOCKED", "Blocked"):
        border_col = "#DC2626"
        bg_col = "#3B0A0A"
        line1 = (
            f"🛑 <b>Thank you for your response — the transaction is blocked (Score: {risk_score}/100)</b> "
            "and your account balance was <b>not</b> deducted."
        )
        line2 = (
            f"<b>Why &amp; Resolution:</b> {reason_snippet} "
            "This transfer has been permanently blocked with no administrator action required."
        )
    elif tx_status in ("COMPLETED", "Settled"):
        border_col = "#10B981"
        bg_col = "#07291B"
        line1 = (
            f"✅ <b>Transfer Verified &amp; Completed (Score: {risk_score}/100)</b> — "
            "Your confirmation was recorded and the transfer has been settled."
        )
        line2 = (
            f"<b>Security Context:</b> {reason_snippet}"
        )
    elif tx_status == "HELD_HIGH_RISK" or risk_score >= 75:
        border_col = "#EF4444"
        bg_col = "#2A1215"
        line1 = (
            f"⏸️ <b>Transfer Placed on High-Risk Security Hold (Score: {risk_score}/100)</b> — "
            "Your account balance has <b>not</b> been deducted."
        )
        line2 = (
            f"🔍 <b>Why &amp; Next Step:</b> {reason_snippet} "
            "Deny in <b>Security Alerts</b> to block immediately, or approve to forward to an administrator in the Risk Analysis Lab for release."
        )
    else:
        border_col = "#F59E0B"
        bg_col = "#281D0A"
        line1 = (
            f"⚠️ <b>Medium-Risk Verification Needed (Score: {risk_score}/100)</b> — "
            "Your balance has <b>not</b> been deducted while awaiting your response."
        )
        line2 = (
            f"🛡️ <b>Why &amp; Next Step:</b> {reason_snippet} "
            "Approve in <b>Security Alerts</b> to complete the transfer immediately (no administrator review needed), or deny to block it right away."
        )

    st.markdown(
        f"""
<div style="background:{bg_col};border:1px solid {border_col};border-left:4px solid {border_col};
border-radius:8px;padding:12px 16px;margin:10px 0;font-size:0.84rem;line-height:1.55;color:#F8FAFC">
  <div>{line1}</div>
  <div style="color:#CBD5E1;margin-top:4px">{line2}</div>
</div>""",
        unsafe_allow_html=True,
    )


def render_financial_calibration_card(tx: Dict[str, Any]) -> None:
    """Render an executive Financial & Business Profile Calibration card for a transaction's sender."""
    typical = float(tx.get("sender_typical_tx") or 100.0)
    max_tx = float(tx.get("sender_max_tx") or 1000.0)
    amt = float(tx.get("amount") or 0.0)
    mult = amt / typical if typical > 0 else 1.0
    mult_color = "#EF4444" if amt > max_tx * 1.35 else ("#F59E0B" if amt > max_tx else "#10B981")

    exp_model = tx.get("sender_expenditure_model", "personal_consumption")
    exp_badge = expenditure_badge_html(exp_model)
    acct_cat = str(tx.get("sender_account_category", "individual")).upper()

    st.markdown(
        f"""
<div style="background:linear-gradient(145deg,#111E2B 0%,#0D1620 100%);border:1px solid #223342;
border-radius:10px;padding:16px 20px;margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;
  border-bottom:1px solid #1E2D3B;padding-bottom:10px;margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="font-size:0.7rem;font-weight:700;color:#8A9CB0;text-transform:uppercase;letter-spacing:0.08em">
        🏦 Sender Economic &amp; Business Calibration
      </span>
      {exp_badge}
      <span style="font-size:0.67rem;color:#94A3B8;background:#182635;padding:2px 7px;border-radius:4px">
        {acct_cat} · {tx.get("sender_industry","—")}
      </span>
    </div>
    <div style="font-size:0.74rem;color:#8A9CB0">
      Operating Hours: <b style="color:#E2E8F0;font-family:monospace">{tx.get("sender_operating_hours","—")} UTC</b>
      &nbsp;·&nbsp; Home Geo: <b style="color:#21D4C2;font-family:monospace">{tx.get("sender_home_geo","—")}</b>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px">
    <div>
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Account Holder</div>
      <div style="font-size:0.86rem;font-weight:600;color:#F1F5F9">{tx.get("sender_name","—")}</div>
      <div style="font-size:0.71rem;color:#21D4C2;font-family:monospace">{tx.get("sender_id","")} · {tx.get("sender_profile","")}</div>
    </div>
    <div>
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Est. Net Worth / Band</div>
      <div style="font-size:0.9rem;font-weight:700;color:#E2E8F0">{fmt_currency(float(tx.get("sender_net_worth",0)))}</div>
      <div style="font-size:0.7rem;color:#8A9CB0">Band: {tx.get("sender_net_worth_band","—")}</div>
    </div>
    <div>
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Declared Monthly Turnover</div>
      <div style="font-size:0.9rem;font-weight:700;color:#E2E8F0">{fmt_currency(float(tx.get("sender_monthly_turnover",0)))}</div>
      <div style="font-size:0.7rem;color:#8A9CB0">Alert Threshold: {tx.get("user_alert_threshold",60)}/100</div>
    </div>
    <div>
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Typical / Max Single Tx</div>
      <div style="font-size:0.9rem;font-weight:700;color:#E2E8F0">{fmt_currency(typical)} <span style="color:#64748B">/</span> {fmt_currency(max_tx)}</div>
      <div style="font-size:0.7rem;color:#8A9CB0">Historical ceiling</div>
    </div>
    <div>
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Current Tx vs Typical</div>
      <div style="font-size:0.95rem;font-weight:700;color:{mult_color};font-family:monospace">{mult:.1f}× typical</div>
      <div style="font-size:0.7rem;color:{mult_color}">{"Exceeds Max Ceiling" if amt > max_tx else "Within Historical Max"}</div>
    </div>
    <div>
      <div style="font-size:0.65rem;color:#8A9CB0;text-transform:uppercase">Counterparty Category</div>
      <div style="font-size:0.84rem;font-weight:600;color:#E2E8F0">{tx.get("beneficiary_name","—")}</div>
      <div style="font-size:0.7rem;color:#67E8F9;font-family:monospace">{tx.get("beneficiary_category","—")} · {tx.get("beneficiary_industry","—")}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Score Cards
# ---------------------------------------------------------------------------

def render_score_card(method_name: str, score: int, level: str, description: str = "") -> None:
    color = RISK_COLOR_MAP.get(level, "#8A9CB0")
    st.markdown(
        f"""
<div class="score-card">
  <div class="score-value" style="color:{color}">{score}</div>
  <div style="margin-top:6px">{risk_badge_html(level)}</div>
  <div class="score-method">{method_name}</div>
  {f'<div style="font-size:0.74rem;color:#8A9CB0;margin-top:10px;line-height:1.45">{description}</div>' if description else ''}
</div>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Plotly chart theme helper
# ---------------------------------------------------------------------------

def plotly_layout_defaults(title: str = "", height: int = 350) -> Dict[str, Any]:
    return dict(
        title=dict(text=title, font=dict(size=13, color=COLORS["text_muted"], family="Inter")),
        height=height,
        paper_bgcolor=COLORS["plotly_bg"],
        plot_bgcolor=COLORS["plotly_bg"],
        font=dict(family="Inter", color=COLORS["plotly_text"], size=11),
        margin=dict(l=48, r=24, t=44, b=36),
        xaxis=dict(gridcolor=COLORS["plotly_grid"], showgrid=True, linecolor=COLORS["plotly_grid"]),
        yaxis=dict(gridcolor=COLORS["plotly_grid"], showgrid=True, linecolor=COLORS["plotly_grid"]),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=COLORS["plotly_grid"],
            font=dict(size=10, color=COLORS["text_muted"]),
        ),
        hoverlabel=dict(
            bgcolor="#13202B",
            bordercolor="#223342",
            font_size=12,
            font_family="Inter",
        ),
    )


def build_risk_distribution_chart(txs: List[Dict[str, Any]]) -> go.Figure:
    counts = Counter(t["method2_level"] for t in txs)
    levels = ["Low", "Medium", "High", "Critical"]
    colors = [RISK_COLOR_MAP[lv] for lv in levels]
    vals = [counts.get(lv, 0) for lv in levels]

    fig = go.Figure(
        go.Bar(
            x=levels,
            y=vals,
            marker_color=colors,
            marker_line_color=colors,
            marker_line_width=1,
            text=vals,
            textposition="outside",
            textfont=dict(color=COLORS["text_primary"], size=11),
            hovertemplate="<b>%{x} Risk</b><br>Transactions: %{y}<extra></extra>",
        )
    )
    layout = plotly_layout_defaults("Risk Level Distribution (M2 Contextual)", height=310)
    layout["yaxis"]["title"] = "Transaction Count"
    layout["xaxis"]["title"] = "Risk Band"
    layout["yaxis"]["range"] = [0, max(vals + [10]) * 1.18]
    fig.update_layout(**layout)
    return fig


def build_score_comparison_chart(scores: Dict[str, Any], threshold: int = 60) -> go.Figure:
    """Horizontal bar chart comparing three method scores for a single transaction."""
    methods = ["M1: Transaction-Only", "M2: Contextual Forensic", "M3: Contextual + TI"]
    values = [
        scores.get("method1", {}).get("score", 0),
        scores.get("method2", {}).get("score", 0),
        scores.get("method3", {}).get("score", 0),
    ]
    bar_colors = [
        RISK_COLOR_MAP.get(scores.get(f"method{i + 1}", {}).get("level", "Low"), "#8A9CB0")
        for i in range(3)
    ]

    fig = go.Figure(
        go.Bar(
            y=methods,
            x=values,
            orientation="h",
            marker_color=bar_colors,
            text=[f"{v}/100" for v in values],
            textposition="outside",
            textfont=dict(color=COLORS["text_primary"], size=12, family="Inter"),
            hovertemplate="<b>%{y}</b><br>Score: %{x}/100<extra></extra>",
        )
    )

    fig.add_vline(
        x=threshold,
        line_dash="dash",
        line_color="#F59E0B",
        annotation_text=f"User Alert Threshold ({threshold})",
        annotation_font_color="#F59E0B",
        annotation_font_size=10,
    )

    layout = plotly_layout_defaults("3-Method Heuristic Score Comparison", height=250)
    layout["xaxis"]["range"] = [0, 112]
    layout["xaxis"]["title"] = "Heuristic Risk Score (0–100)"
    layout["yaxis"]["title"] = ""
    layout["margin"]["l"] = 165
    fig.update_layout(**layout)
    return fig


def build_waterfall_chart(contributions: Dict[str, int]) -> go.Figure:
    labels = list(contributions.keys())
    values = list(contributions.values())

    fig = go.Figure(
        go.Waterfall(
            name="Score",
            orientation="v",
            measure=["relative"] * len(labels) + ["total"],
            x=labels + ["Uncapped Sum"],
            y=values + [None],
            connector=dict(line=dict(color="#223342", width=1)),
            decreasing=dict(marker_color="#10B981"),
            increasing=dict(marker_color="#EF4444"),
            totals=dict(marker_color="#21D4C2"),
            textposition="outside",
            text=[f"+{v}" if v > 0 else str(v) for v in values] + [f"{sum(values)}"],
            textfont=dict(family="Inter", size=10, color=COLORS["text_primary"]),
            hovertemplate="<b>%{x}</b><br>Points Delta: %{y:+d}<extra></extra>",
        )
    )

    layout = plotly_layout_defaults("Rule Contribution & Contextual Suppression Waterfall", height=320)
    layout["xaxis"]["tickangle"] = -25
    layout["xaxis"]["tickfont"] = dict(size=9)
    max_y = max([sum(v for v in values if v > 0), abs(sum(values)), 40])
    layout["yaxis"]["range"] = [min(0, min(values + [0]) - 15), max_y * 1.22]
    fig.update_layout(**layout)
    return fig


def build_activity_chart(data: List[Dict[str, Any]]) -> go.Figure:
    if not data:
        return go.Figure()
    df = pd.DataFrame(data)
    df["datetime"] = pd.to_datetime(df["datetime"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["datetime"],
            y=df["count"],
            mode="lines+markers",
            name="Daily Volume",
            line=dict(color="#21D4C2", width=2.2),
            marker=dict(size=5, color="#21D4C2"),
            fill="tozeroy",
            fillcolor="rgba(33, 212, 194, 0.09)",
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Transactions: %{y}<extra></extra>",
        )
    )

    layout = plotly_layout_defaults("Daily Transaction Activity", height=310)
    layout["yaxis"]["title"] = "Transactions"
    layout["xaxis"]["title"] = "Date (UTC)"
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# Kill-Chain Ribbon & Evidence Timeline
# ---------------------------------------------------------------------------

PHASE_COLORS = {
    "Recon / Brute-Force": "#DC2626",
    "Initial Access": "#EF4444",
    "Preparation / Persistence": "#F59E0B",
    "Exfiltration Execution": "#DC2626",
    "Normal Activity": "#10B981",
}

SEVERITY_DOT_COLORS = {
    "Critical": "#DC2626",
    "High": "#EF4444",
    "Medium": "#F59E0B",
    "Low": "#10B981",
}


def render_kill_chain_ribbon(events: List[Dict[str, Any]]) -> None:
    """Render a visual DFIR Kill-Chain stage indicator bar highlighting active phases in the timeline."""
    observed = {ev.get("phase", "") for ev in events}
    stages = [
        ("1. Recon / Brute-Force", "Recon / Brute-Force", "#DC2626"),
        ("2. Initial Access", "Initial Access", "#EF4444"),
        ("3. Preparation / Persistence", "Preparation / Persistence", "#F59E0B"),
        ("4. Exfiltration Execution", "Exfiltration Execution", "#DC2626"),
    ]

    pills_html = ""
    for title, key, active_color in stages:
        is_active = key in observed
        bg = f"{active_color}28" if is_active else "#0E1720"
        border = active_color if is_active else "#223342"
        txt_col = "#F8FAFC" if is_active else "#64748B"
        status_dot = f'<span style="color:{active_color};margin-right:5px">●</span>' if is_active else '<span style="color:#475569;margin-right:5px">○</span>'
        pills_html += (
            f'<div style="flex:1;min-width:150px;background:{bg};border:1px solid {border};'
            f'border-radius:7px;padding:8px 12px;text-align:center;font-size:0.73rem;font-weight:600;color:{txt_col}">'
            f'{status_dot}{title}</div>'
        )

    st.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">{pills_html}</div>',
        unsafe_allow_html=True,
    )


def render_timeline(events: List[Dict[str, Any]]) -> None:
    if not events:
        st.info("No evidence timeline records found for this transaction.")
        return

    render_kill_chain_ribbon(events)

    for idx, ev in enumerate(events):
        phase = ev.get("phase", "Normal Activity")
        severity = ev.get("severity", "Low")
        dot_color = SEVERITY_DOT_COLORS.get(severity, "#8A9CB0")
        phase_color = PHASE_COLORS.get(phase, "#8A9CB0")
        is_last = idx == len(events) - 1

        connector = "" if is_last else '<div class="timeline-connector"></div>'
        phase_html = (
            f'<span class="timeline-phase" style="background:{phase_color}22;color:{phase_color};'
            f'border:1px solid {phase_color}55">{phase}</span>'
        )

        recorded_fact = ev.get("recorded_fact") or ev.get("description", "")
        system_interp = ev.get("system_interpretation", "")
        interp_html = (
            f'<div class="timeline-interp"><b>Forensic Inference:</b> {system_interp}</div>'
            if system_interp
            else ""
        )

        st.markdown(
            f"""
<div class="timeline-event">
  <div style="position:relative;width:12px">
    <div class="timeline-dot" style="color:{dot_color};background:{dot_color}"></div>
    {connector}
  </div>
  <div class="timeline-content">
    <div class="timeline-header">
      <span class="timeline-time">{ev.get("timestamp","")}</span>
      <span class="timeline-type">{ev.get("event_type","")}</span>
      {phase_html}
      <span class="badge badge-{severity.lower()}">{severity}</span>
    </div>
    <div class="timeline-fact"><b>Recorded Telemetry:</b> {recorded_fact}</div>
    {interp_html}
    <div class="timeline-entity">Context: {ev.get("entity","—")} &nbsp;|&nbsp; Provenance: <span style="color:#21D4C2">{ev.get("source","—")}</span></div>
  </div>
</div>""",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Scenario Overview Cards
# ---------------------------------------------------------------------------

def render_scenario_card(scenario: Dict[str, Any]) -> None:
    card_type = "legitimate" if scenario["type"] == "Legitimate" else "attack"
    badge_color = "#10B981" if card_type == "legitimate" else "#EF4444"
    badge_text = "✓ LEGITIMATE ARCHETYPE" if card_type == "legitimate" else "⚠ ATTACK ARCHETYPE"
    count_val = scenario.get("count", "")
    count_pill = f'<span style="font-size:0.66rem;color:#94A3B8;margin-left:auto">{count_val} txs in DB</span>' if count_val else ""

    st.markdown(
        f"""
<div class="scenario-card {card_type}">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
    <span style="font-size:0.65rem;font-weight:700;color:{badge_color};letter-spacing:0.07em">{badge_text}</span>
    <span style="font-size:0.66rem;color:#64748B">{scenario["id"]}</span>
    <code style="font-size:0.68rem;color:#21D4C2;background:#082330;padding:1px 6px;border-radius:4px">Sample: {scenario["tx_id"]}</code>
    {count_pill}
  </div>
  <div class="scenario-title">{scenario["name"]}</div>
  <div class="scenario-headline">{scenario["headline"]}</div>
  <div class="scenario-lesson">💡 {scenario["key_lesson"]}</div>
</div>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Empty & Error states
# ---------------------------------------------------------------------------

def render_empty_state(message: str = "No records found matching the current filters.") -> None:
    st.markdown(
        f'<div style="text-align:center;padding:38px;color:#8A9CB0;font-size:0.88rem;'
        f'border:1px dashed #223342;border-radius:8px;background:#0B131C">{message}</div>',
        unsafe_allow_html=True,
    )


def render_error(message: str) -> None:
    st.markdown(
        f'<div style="padding:14px 18px;background:#3B0A0A;border:1px solid #DC2626;'
        f'border-radius:8px;color:#FCA5A5;font-size:0.84rem">{message}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# TRACE-Fin Wordmark / Logo
# ---------------------------------------------------------------------------

SIDEBAR_LOGO_HTML = """
<div style="padding:14px 14px 14px;border-bottom:1px solid #1E2E3E;margin-bottom:10px">
  <div style="display:flex;align-items:center;gap:11px">
    <div style="
      width:36px;height:36px;
      background:linear-gradient(135deg,#0A2239,#21D4C228);
      border:1.5px solid #21D4C288;
      border-radius:8px;
      display:flex;align-items:center;justify-content:center;
      flex-shrink:0;
      box-shadow:0 0 12px rgba(33,212,194,0.18)">
      <svg viewBox="0 0 24 24" width="19" height="19" fill="none"
           xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L4 6v6c0 5.5 3.4 9.7 8 11 4.6-1.3 8-5.5 8-11V6L12 2z"
              fill="#21D4C222" stroke="#21D4C2" stroke-width="1.6"/>
        <path d="M9 12l2 2 4-4" stroke="#21D4C2" stroke-width="1.6"
              stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div>
      <div style="font-size:1.08rem;font-weight:700;color:#F1F5F9;
                  letter-spacing:-0.02em;line-height:1.05">TRACE-Fin</div>
      <div style="font-size:0.62rem;color:#21D4C2;font-weight:600;
                  letter-spacing:0.05em;line-height:1.35;text-transform:uppercase">Digital Banking &amp; Forensics</div>
    </div>
  </div>
</div>
"""
