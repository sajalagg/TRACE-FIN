# TRACE-Fin Frontend (Executive SOC Dashboard)
## Transaction Risk Analysis, Correlation, and Escalation for Finance

**Evidence-Aware Financial Transaction Verification and Incident Response**

> **Academic Notice:** TRACE-Fin is a research prototype for a Digital Forensics and Incident Response (DFIR) project. All transaction records, identities, financial amounts, authentication events, threat indicators, and evaluation results are **entirely synthetic** and stored in the local `data/trace_fin.db` SQLite database.

---

## Architecture (100% Live FastAPI + SQLite)

The frontend is connected exclusively to the live **FastAPI + SQLite** backend (`http://127.0.0.1:8000`) with Mock Mode completely removed:

```
frontend/
├── app.py                                   # Main entrypoint (7-page navigation + live health check)
├── requirements.txt
├── .streamlit/
│   └── config.toml                          # Executive dark navy + cyan SOC theme
├── services/
│   ├── config.py                            # API_BASE_URL (default: http://127.0.0.1:8000)
│   └── data_provider.py                     # Live HTTP client (httpx) for all FastAPI endpoints
├── ui/
│   └── components.py                        # Reusable cards, financial calibration banner, kill-chain ribbon, Plotly charts
└── pages/
    ├── 1_overview_dashboard.py              # Live SQLite KPIs, activity chart, Needs Your Attention queue
    ├── 2_transaction_explorer.py            # Search, Expense-Type filter, Financial Calibration Card, CSV export
    ├── 3_risk_analysis_lab.py               # 3-Method comparison, rule matrix, waterfall, counterfactuals, Alert Policy Simulator
    ├── 4_forensic_investigation.py          # Kill-Chain progress ribbon, timeline for all 500+ txs, live verification & SHA-256 incident creation
    ├── 5_threat_intelligence.py             # SQLite TI registry, freshness gating (active vs expired=0 pts), linked transactions
    └── 6_incident_register_evaluation.py    # Persistent SQLite Incident Register, SHA-256 tamper verification, Stage 10 Evaluation
```

---

## Running Backend & Frontend Together

From the project root (`/Users/apple/Desktop/TRACE-FIN`):

```bash
# Terminal 1: Seed SQLite database (with 500 transactions + 3 initial SHA-256 incidents) & start FastAPI
.venv/bin/python -m scripts.seed_demo_data
.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2: Launch the Streamlit Executive SOC Dashboard
.venv/bin/streamlit run frontend/app.py
```

- **FastAPI Swagger UI:** `http://127.0.0.1:8000/docs`
- **Streamlit Frontend UI:** `http://localhost:8501`
