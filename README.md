# TRACE-Fin

**Transaction Risk Analysis, Correlation and Escalation for Finance**  
*Evidence-Aware Financial Transaction Verification and Incident Response*

> **Disclaimer:** TRACE-Fin is an educational and research prototype built for classroom demonstration and evaluation. All users, transactions, security events, and threat-intelligence indicators in this repository are **100% synthetic**. This system does not connect to real financial institutions or move/block real money.

---

## Overview

TRACE-Fin investigates whether correlating financial transactions with surrounding security context (authentication events, device history, beneficiary changes, and simulated threat-intelligence indicators) helps prioritize suspicious activity more effectively than transaction-only rules.

### Core Capabilities
1. **User Financial & Business Profile Calibration:** Each synthetic user has an account category (`individual` vs `business`), industry sector, expenditure model (`opex_heavy`, `capex_heavy`, `personal_consumption`), net worth, declared monthly turnover, typical max transaction envelope, and operating hours.
2. **Counterparty Supply-Chain Affinity, Vendor BEC & Mule Detection:** Evaluates sender-to-beneficiary industry affinity, flags recent vendor bank-detail changes (`beneficiary_bank_updated` / Business Email Compromise), checks relationship maturity, and detects cross-user money-mule convergence.
3. **Structuring ("Smurfing") & Cash-Flow Calendar Awareness:** Tracks rolling 24-hour cumulative outflow to catch split transfers below single-tx limits, while accounting for normal month-end (`25th–5th`) OpEx/payroll cycles.
4. **Three Explainable Risk-Scoring Modes (0–100 scale) + Counterfactuals:**
   - **Baseline (`baseline`):** Transaction-only rules (amount, basic frequency, hour of day).
   - **Contextual (`contextual`):** Baseline + Profile calibration, Counterparty/BEC checks, Structuring velocity, Cash-flow calendar, Failed logins, New device/IP, and Impossible Travel geo-velocity.
   - **Contextual + Threat Intel (`contextual_ti`):** Contextual + matches against local demo threat-intelligence indicators (weighted by confidence and checked for expiry).
   - Includes a **Side-by-Side 3-Method Waterfall Comparison** and deterministic **Counterfactual Explanations** (*"What would have lowered this score?"*).
5. **Kill-Chain Forensic Evidence Timeline:** Unified, timestamp-ordered view of a transaction and its linked authentication, device, and beneficiary records tagged by forensic kill-chain phase.
6. **User Alert Policy & What-If Simulator:** Per-user risk-score thresholds, IANA time zones, overnight quiet-hours handling, critical-event bypass, and a live policy simulator.
7. **Verification & Tamper-Evident Incident Workflow:** Simulated user confirmation/denial flow that automatically opens an evidence-linked incident with a canonical JSON snapshot and **SHA-256 integrity digest** (`evidence_sha256`).
8. **Reproducible Evaluation:** Precision, recall, F1, false-positive rate, per-scenario & business-profile ablation tables, and alert-volume trade-offs across thresholds on held-out synthetic scenarios.

---

## Architecture & Request Flow

```text
Streamlit UI  --->  FastAPI REST API  --->  Service Layer  --->  SQLite Database
 (Frontend)          (Validation/HTTP)       (Scoring/Policy)     (Synthetic Data)
```

### Planned Project Structure
- `app/main.py` & `app/api/` — FastAPI application and route handlers
- `app/core/` — Configuration and SQLite database connection helpers
- `app/models/` & `app/schemas/` — Database structure and Pydantic request/response schemas
- `app/services/` — Deterministic scoring, evidence correlation, alert policy, verification, and incidents
- `app/ui/` — Streamlit dashboard and interactive pages
- `scripts/` — Reproducible synthetic dataset generator (`seed_demo_data.py`)
- `tests/` — Pytest test suite covering endpoints and service logic

---

## Quickstart (Current Stage: Stage 2)

```bash
# 1. Activate the virtual environment
source .venv/bin/activate

# 2. Seed and inspect the deterministic synthetic SQLite database (500 transactions)
python -m scripts.seed_demo_data

# 3. Run the automated test suite
pytest -v

# 4. Start the FastAPI backend
uvicorn app.main:app --reload
```

Once running, test the health endpoint at `http://127.0.0.1:8000/health` or open interactive Swagger docs at `http://127.0.0.1:8000/docs`. See [API_GUIDE.md](API_GUIDE.md) for endpoint details.

---

## Development Roadmap
We are building TRACE-Fin incrementally:
- **Stage 0:** Repository inspection, architecture plan, and documentation ✅
- **Stage 1:** Minimal FastAPI skeleton (`GET /health`) + test ✅
- **Stage 2:** SQLite schema (User Financial/Business Profiles, BEC, Structuring, Geo-Velocity) & reproducible synthetic data seeding ✅
- **Stage 3:** Read-only transaction & user profile API (`GET /users`, `GET /transactions`, `GET /transactions/{id}`) ✅
- **Stage 4:** Explainable rule-based scoring engine (3 comparable methods + counterfactuals + side-by-side comparison) ✅
- **Stage 5:** Unified forensic evidence timeline with Kill-Chain phase tagging ✅ *(Current)*
- **Stage 6:** User alert preferences (thresholds, time zones, quiet hours, What-If policy simulator)
- **Stage 7:** Simulated transaction verification workflow
- **Stage 8:** Incident register and lifecycle management
- **Stage 9:** Streamlit user interface
- **Stage 10:** Reproducible evaluation metrics and threshold curves
- **Stage 11:** Final polish, diagrams, and paper tables

See [TRACE-Fin_PROJECT_GUIDE.md](TRACE-Fin_PROJECT_GUIDE.md) for the complete stage-by-step specification.
