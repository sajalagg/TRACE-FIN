# TRACE-Fin

**Transaction Risk Analysis, Correlation and Escalation for Finance**  
*Simulated Digital Banking Portal & Explainable Forensic Risk Protection Console*

> **Disclaimer:** TRACE-Fin is an educational and research prototype built for classroom demonstration and evaluation. All customer accounts, balances, transactions, login sessions, security events, and threat-intelligence indicators in this repository are **100% synthetic**. This system does not connect to real financial institutions or move/block real money.

---

## Overview

TRACE-Fin demonstrates how a **user-centred simulated digital banking application** correlates financial transfers with surrounding session & network intelligence (login session IP/location, device provenance, authentication history, beneficiary modifications, and simulated threat-intelligence indicators) to prioritize suspicious activity more accurately than transaction-only rules.

### Dual Role-Based Experience
1. **Customer Digital Banking Portal (`role="customer"`):**
   - **Onboarding with Baseline Home IP & Location (`POST /auth/register`):** Captures the customer's baseline Home Location (`home_geo_location`), Home IP Address (`home_ip_prefix`), and Primary Trusted Device at account creation.
   - **Sign-In Session Network Selector (`POST /auth/login`):** Allows choosing a simulated login network context (*Normal Home Broadband*, *Legitimate Travel / Hotel Wi-Fi or VPN*, *Unfamiliar Location + Unseen Device + Failed Logins*, *Flagged Threat-Intel Proxy IP*, or *Custom IP/Location*).
   - **6 Customer Banking Views:**
     1. **Dashboard** (`c1_customer_dashboard.py`) — Simulated balance, active session security summary, recent transfers, and pending security alerts.
     2. **Beneficiaries** (`c2_customer_beneficiaries.py`) — Add/verify recipients or simulate a Vendor BEC bank-detail change.
     3. **Transfer Money** (`c3_customer_transfer.py`) — Send simulated transfers with strict balance checking (`amount <= simulated_balance`) and optional risk scenario toggles.
     4. **Transactions** (`c4_customer_transactions.py`) — Personal transfer ledger with a **2-line plain-language security explainer** whenever a transfer is rated Medium risk (`40–74`) or higher.
     5. **Security Alerts** (`c5_customer_security_alerts.py`) — Step-up customer confirmation (`"✅ I made this transaction"` / `"🛑 I did not make this transaction"`) and recent sign-in history.
     6. **Profile & Preferences** (`c6_customer_profile_preferences.py`) — Alert sensitivity, IANA time zone, quiet hours, and system sync settings.

2. **Admin SOC & Forensic Investigation Console (`role="admin"`):**
   - **Admin Dashboard** (`1_overview_dashboard.py`) — System-wide KPIs, scenario archetypes, and operational queue.
   - **Risk Analysis Lab** (`3_risk_analysis_lab.py`) — Side-by-side **3-Method Risk Comparison** (`M1` Baseline vs `M2` Contextual vs `M3` Contextual + Threat Intel), **Session & Network Intelligence Inspector** (explicitly separating *Observed Telemetry*, *Simulated Input*, and *Inferred Context*), and the **Admin Investigation & Transfer Release Panel** (`POST /transactions/{id}/admin-decision`).
   - **Forensic Timeline & Verify** (`4_forensic_investigation.py`) — Chronological Kill-Chain timeline separating *Recorded Database Facts* from *Forensic Inferences*.
   - **Transaction Investigations** (`2_transaction_explorer.py`) — Filterable ledger across all accounts and risk bands.
   - **Threat Intelligence** (`5_threat_intelligence.py`) — Active vs. expired indicator feed inspection.
   - **Incidents & Evaluation** (`6_incident_register_evaluation.py`) — Tamper-evident **SHA-256 Incident Register** and reproducible evaluation metrics (`Precision`, `Recall`, `F1`, `FPR`).

---

## Central Transfer Policy & Balance Lifecycle

Every simulated transfer (`POST /transactions`) is evaluated against the customer's available `simulated_balance` and the 3-method Contextual + Threat-Intel score (`0–100`):

| Risk Score Band | Resulting Status | Simulated Balance Deducted? | Workflow & Resolution Path |
| :--- | :--- | :--- | :--- |
| **Low (`0–39`)** | `COMPLETED` | **Yes (Immediately)** | Settles immediately. Note: a new IP, VPN, or unfamiliar location **alone** on a known device and trusted beneficiary scores Low (`10/100`) and is **not** blocked. |
| **Medium (`40–74`)** | `PENDING_VERIFICATION` | **No (Paused)** | Shows a 2-line customer explainer and creates a step-up alert. If the customer confirms in **Security Alerts**, status becomes `COMPLETED` and `simulated_balance` is deducted once. |
| **High / Critical (`75–100`)** | `HELD_HIGH_RISK` | **No (On Hold)** | Shows a 2-line customer explainer and requires **Administrator investigation in the Risk Analysis Lab**. After confirming with the account owner, the Admin can **Approve & Complete** (deducting `simulated_balance` once) or **Block & Escalate** (opening a SHA-256 incident). |
| **Denied / Admin Block** | `BLOCKED` | **No (Untouched)** | Transfer is permanently blocked and a tamper-evident **SHA-256 Forensic Incident (`INC-XXXX`)** is created. |

---

## Demo Sign-In Credentials

| Role | Username / User ID | Password | Profile Archetype |
| :--- | :--- | :--- | :--- |
| **Customer** | `aarav.sharma` (or `USR-001`) | `DemoUser@123` | Individual Student / Personal Consumption (`IN-Mumbai`) |
| **Customer** | `maya.lin` (or `USR-002`) | `DemoUser@123` | Graduate Researcher (`SG-Singapore`) |
| **Customer** | `USR-003` … `USR-012` | `DemoUser@123` | Seeded Freelancer, SME OpEx, Enterprise CapEx, and HNW Profiles |
| **Administrator (SOC)** | `admin` (or `ADMIN-001`) | `AdminTrace@123` | Full SOC, Forensic Timeline & Risk Analysis Lab Release Console |

*(You can also register a brand-new customer account with custom Home IP & Location on the **Create Demo Account** tab of the landing page.)*

---

## Quickstart

```bash
# 1. Activate the virtual environment
source .venv/bin/activate

# 2. (Optional) Re-seed the deterministic synthetic database (12 customers, 1 admin, 500 transactions)
.venv/bin/python -m scripts.seed_demo_data

# 3. Start the backend server (Terminal 1)
.venv/bin/uvicorn app.main:app --reload --port 8000

# 4. Launch the TRACE-Fin web application (Terminal 2)
.venv/bin/streamlit run frontend/app.py
```

Once running:
- **TRACE-Fin Web Application:** `http://localhost:8501`
- **Interactive API Documentation:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/health`

---

## Project Structure
- [app/main.py](file:///Users/apple/Desktop/TRACE-FIN/app/main.py) & [app/api/](file:///Users/apple/Desktop/TRACE-FIN/app/api) — FastAPI REST API routes (`routes_auth.py`, `routes_transactions.py`, `routes_verification.py`, `routes_incidents.py`, `routes_preferences.py`, `routes_evaluation.py`) and ownership guards (`deps.py`)
- [app/core/](file:///Users/apple/Desktop/TRACE-FIN/app/core) — Central transfer policy (`policy.py`), `PBKDF2-HMAC-SHA256` password/token security (`security.py`), and database initialization (`database.py`)
- [app/services/](file:///Users/apple/Desktop/TRACE-FIN/app/services) — Authentication & Session Network Intelligence (`auth.py`), 3-method risk scoring (`scoring.py`), transactions (`transactions.py`), verification & Admin release (`verification.py`), forensic incidents (`incidents.py`), and evaluation (`evaluation.py`)
- [frontend/app.py](file:///Users/apple/Desktop/TRACE-FIN/frontend/app.py) & [frontend/pages/](file:///Users/apple/Desktop/TRACE-FIN/frontend/pages) — Public landing page (`0_landing_auth.py`), 6 Customer Digital Banking pages (`c1_..c6_*.py`), and 6 Admin SOC pages (`1_..6_*.py`)
- [scripts/](file:///Users/apple/Desktop/TRACE-FIN/scripts) — Deterministic dataset seeder (`seed_demo_data.py`) and CLI evaluation exporter (`run_evaluation.py`)
- [data/](file:///Users/apple/Desktop/TRACE-FIN/data) — Local SQLite storage (`trace_fin.db`) and evaluation export outputs
