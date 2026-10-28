# TRACE-Fin Frontend (Digital Banking & Executive SOC Console)
## Transaction Risk Analysis, Correlation, and Escalation for Finance

**Evidence-Aware Financial Transaction Verification and Incident Response**

> **Notice:** TRACE-Fin is an educational and research prototype. All transaction records, identities, financial amounts, authentication events, threat indicators, and evaluation results are **entirely synthetic** and stored in the local `data/trace_fin.db` SQLite database.

---

## Architecture (100% Live FastAPI + SQLite)

The frontend is connected exclusively to the live **FastAPI + SQLite** backend (`http://127.0.0.1:8000`):

```
frontend/
├── app.py                                   # Role-based navigation shell (Unauthenticated, Customer, Admin)
├── .streamlit/
│   └── config.toml                          # Executive dark navy + cyan theme
├── services/
│   ├── config.py                            # API_BASE_URL (default: http://127.0.0.1:8000)
│   └── data_provider.py                     # Pooled HTTP client (httpx) for all FastAPI endpoints
├── ui/
│   └── components.py                        # Reusable badges, cards, financial calibration banner, Plotly charts
└── pages/
    ├── 0_landing_auth.py                    # Public landing page, session network selector & customer onboarding
    ├── 1_overview_dashboard.py              # Admin SOC KPIs, activity chart, held transfer priority queues
    ├── 2_transaction_explorer.py            # Deep ledger search, expense-type filters & calibration inspection
    ├── 3_risk_analysis_lab.py               # 3-method comparison, live rule breakdown, counterfactuals & admin decision release
    ├── 4_forensic_investigation.py          # Kill-chain timeline for all transactions, forensic escalation & resolution
    ├── 5_threat_intelligence.py             # SQLite TI registry, freshness gating (active vs expired=0 pts)
    ├── 6_incident_register_evaluation.py    # Scoring model benchmark (M1 vs M2 vs M3) & live 3-engine transaction inspection
    ├── c1_customer_dashboard.py             # Customer digital banking summary, recent activity & security alerts
    ├── c2_customer_beneficiaries.py         # Saved beneficiaries management & BEC bank change testing
    ├── c3_customer_transfer.py              # Transfer money with balance check & network context injection
    ├── c4_customer_transactions.py          # Customer ledger with 2-line plain-language risk explainers
    ├── c5_customer_security_alerts.py       # Step-up verification (Approve / Deny) & login session history
    └── c6_customer_profile_preferences.py   # Sensitivity thresholds, IANA timezone, quiet hours & system settings
```

---

## Running Backend & Frontend Together

From the project root:

```bash
# Terminal 1: Seed SQLite database (with 500 transactions) & start FastAPI
.venv/bin/python -m scripts.seed_demo_data
.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2: Launch the Streamlit application
.venv/bin/streamlit run frontend/app.py
```

- **FastAPI Swagger UI:** `http://127.0.0.1:8000/docs`
- **Streamlit Web Application:** `http://localhost:8501`
