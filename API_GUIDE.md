# TRACE-Fin API Guide

This document explains every HTTP endpoint in the TRACE-Fin backend so you can understand and present how the Streamlit UI communicates with FastAPI.

Interactive OpenAPI/Swagger documentation is also automatically available at `http://127.0.0.1:8000/docs` whenever the FastAPI server is running.

---

## HTTP Client Choice: Why `httpx`?
We chose **HTTPX** (`httpx`) for frontend-to-backend HTTP requests because:
1. FastAPI's built-in `TestClient` uses `httpx` under the hood, meaning one library covers both our test suite and our Streamlit API client.
2. It provides a clean, `requests`-compatible API with strict default timeouts and connection pooling.

---

## Endpoints

### 1. Health Check — `GET /health`
- **Method & Path:** `GET /health`
- **What it does:** Confirms that the FastAPI backend server is online and responding to requests.
- **Parameters / Request Body:** None.
- **Service Called:** Handled directly by [`get_health`](app/api/routes_health.py).
- **Reads/Writes Data:** Neither (stateless check).
- **Plain-Language Explanation:** Before the Streamlit UI tries to load transactions or calculate risk scores, it calls `GET /health` to verify the API server is awake.

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/health
```

#### Example Success Response (`200 OK`)
```json
{
  "status": "ok",
  "service": "TRACE-Fin"
}
```

---

### 2. List User Profiles — `GET /users` & `GET /users/{user_id}`
- **Method & Path:** `GET /users` and `GET /users/{user_id}`
- **What it does:** Returns the synthetic users and their **Financial & Business Profiles** (industry sector, OpEx vs. CapEx expenditure model, net worth band, declared monthly turnover, typical max transaction amount, and operating hours).
- **Query Parameters (`GET /users`):**
  - `expenditure_model` *(optional)*: `'opex_heavy'`, `'capex_heavy'`, or `'personal_consumption'`.
  - `profile_type` *(optional)*: e.g., `'student'`, `'salaried_individual'`, `'sme_opex_merchant'`, `'enterprise_capex_firm'`, `'high_net_worth'`.
- **Path Parameters (`GET /users/{user_id}`):**
  - `user_id` *(required)*: e.g., `USR-010`.
- **Service Called:** [`list_users`](app/services/transactions.py) / [`get_user_by_id`](app/services/transactions.py).
- **Reads/Writes Data:** Reads from the `users` table in SQLite.
- **Plain-Language Explanation:** To judge whether a `$75,000` transfer is normal or suspicious, we first need to know *who* the sender is. These endpoints let the UI and investigator view each user's economic profile (for example, seeing that `USR-010` is a `capex_heavy` heavy-machinery manufacturer with `$6.8M` net worth and a `$110,000` typical max transaction).

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/users/USR-010
```

#### Example Success Response (`200 OK`)
```json
{
  "user_id": "USR-010",
  "display_name": "Apex Forge & Turbines Ltd (CapEx Manufacturing)",
  "account_category": "business",
  "profile_type": "enterprise_capex_firm",
  "industry_sector": "manufacturing_heavy_machinery",
  "expenditure_model": "capex_heavy",
  "net_worth_band": ">$5M",
  "estimated_net_worth": 6800000.0,
  "declared_monthly_turnover": 420000.0,
  "typical_tx_amount": 24000.0,
  "typical_max_tx_amount": 110000.0,
  "expected_monthly_tx_count": 14,
  "operating_hours_utc": "04:00-14:00",
  "home_geo_location": "IN-Pune",
  "created_at_utc": "2026-01-01T08:00:00Z"
}
```

#### Important Error Responses
- `404 Not Found`: `{"detail": "User 'USR-999' not found."}` when `user_id` does not exist.

---

### 3. List Synthetic Transactions — `GET /transactions`
- **Method & Path:** `GET /transactions`
- **What it does:** Returns a paginated list of synthetic transactions enriched with the sender's display name, profile type, and expenditure model.
- **Query Parameters:**
  - `limit` *(optional, default `50`, range `1–500`)*: Maximum number of records returned.
  - `offset` *(optional, default `0`, `>= 0`)*: Number of records skipped for pagination.
  - `user_id` *(optional)*: Filter by a specific user (e.g., `USR-001`).
  - `profile_type` *(optional)*: Filter by user profile type.
  - `expenditure_model` *(optional)*: Filter by `'opex_heavy'`, `'capex_heavy'`, or `'personal_consumption'`.
  - `beneficiary_category` *(optional)*: Filter by counterparty category (e.g., `'verified_b2b_vendor'`, `'personal_peer'`).
- **Service Called:** [`list_transactions`](app/services/transactions.py).
- **Reads/Writes Data:** Reads from `transactions` joined with `users`.
- **Plain-Language Explanation:** Instead of loading thousands of records at once, the UI asks for a "page" of transactions (for example, 20 at a time) and can filter by business model (`opex_heavy` vs `capex_heavy`) or user ID. Notice that ground-truth evaluation labels (`is_suspicious` and `scenario_label`) are intentionally **excluded** from this operational API response to prevent data leakage.

#### Example Request
```bash
curl -X GET "http://127.0.0.1:8000/transactions?user_id=USR-001&limit=2&offset=0"
```

#### Example Success Response (`200 OK`)
```json
{
  "total_matching": 39,
  "limit": 2,
  "offset": 0,
  "items": [
    {
      "transaction_id": "TX-0181",
      "user_id": "USR-001",
      "user_display_name": "Aarav Sharma (University Student)",
      "user_profile_type": "student",
      "user_expenditure_model": "personal_consumption",
      "amount": 25.49,
      "currency": "USD",
      "timestamp_utc": "2026-03-25T15:30:00Z",
      "beneficiary_id": "BEN-001-01",
      "beneficiary_name": "Metro City Electricity & Broadband",
      "beneficiary_category": "utility_tax",
      "beneficiary_industry": "utilities_municipal",
      "device_id": "DEV-001-PRIMARY",
      "ip_address": "103.21.244.36",
      "geo_location": "IN-Mumbai"
    }
  ]
}
```

#### Important Error Responses
- `422 Unprocessable Entity`: Returned automatically by FastAPI if `limit < 1`, `limit > 500`, or `offset < 0`.

---

### 4. Retrieve One Transaction & Surrounding Context — `GET /transactions/{transaction_id}`
- **Method & Path:** `GET /transactions/{transaction_id}`
- **What it does:** Retrieves a single transaction, the sender's complete `user_profile`, and all linked `recent_authentication_events`, `device_events`, and `beneficiary_events` leading up to the transaction timestamp.
- **Path Parameters:**
  - `transaction_id` *(required)*: e.g., `TX-0391`.
- **Service Called:** [`get_transaction_detail`](app/services/transactions.py).
- **Reads/Writes Data:** Reads from `transactions`, `users`, `authentication_events`, `device_events`, and `beneficiary_events`.
- **Plain-Language Explanation:** When an analyst clicks a transaction to investigate it, this endpoint fetches the complete forensic context in one JSON payload: the payment details, the sender's net-worth/OpEx/CapEx profile, recent login successes/failures, device registrations, and beneficiary history.

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/transactions/TX-0391
```

#### Example Success Response (`200 OK`, abbreviated)
```json
{
  "transaction": {
    "transaction_id": "TX-0391",
    "user_id": "USR-001",
    "user_display_name": "Aarav Sharma (University Student)",
    "user_profile_type": "student",
    "user_expenditure_model": "personal_consumption",
    "amount": 157.55,
    "currency": "USD",
    "timestamp_utc": "2026-03-19T19:30:00Z",
    "beneficiary_id": "BEN-ATO-NEW-001",
    "beneficiary_name": "Unverified Instant Wallet #1",
    "beneficiary_category": "personal_peer",
    "beneficiary_industry": "digital_assets_brokerage",
    "device_id": "DEV-UNSEEN-ATO-001",
    "ip_address": "185.220.101.55",
    "geo_location": "NL-Amsterdam"
  },
  "user_profile": {
    "user_id": "USR-001",
    "profile_type": "student",
    "expenditure_model": "personal_consumption",
    "net_worth_band": "<$10K",
    "estimated_net_worth": 4500.0,
    "typical_max_tx_amount": 250.0,
    "home_geo_location": "IN-Mumbai"
  },
  "recent_authentication_events": [
    {
      "event_id": "AUTH-EVT-0391",
      "timestamp_utc": "2026-03-19T19:12:00Z",
      "event_type": "login_success",
      "ip_address": "103.21.244.25",
      "geo_location": "IN-Mumbai",
      "device_id": "DEV-001-PRIMARY",
      "is_success": true
    },
    {
      "event_id": "AUTH-EVT-0392",
      "timestamp_utc": "2026-03-19T19:18:00Z",
      "event_type": "login_failure",
      "ip_address": "185.220.101.55",
      "geo_location": "NL-Amsterdam",
      "device_id": "DEV-UNSEEN-ATO-001",
      "is_success": false
    }
  ],
  "device_events": [...],
  "beneficiary_events": [...]
}
```

#### Important Error Responses
- `404 Not Found`: `{"detail": "Transaction 'TX-999999' not found."}` when the transaction ID does not exist.

---

### 5. Documented Rule Catalog — `GET /risk/rules`
- **Method & Path:** `GET /risk/rules`
- **What it does:** Returns the complete catalog of risk-scoring rules, which scoring methods they apply to (`baseline`, `contextual`, `contextual_ti`), their forensic category, and their maximum point weight.
- **Service Called:** [`get_rule_catalog`](app/services/scoring.py).
- **Reads/Writes Data:** Stateless read from [`RULE_CATALOG`](app/services/scoring.py).
- **Plain-Language Explanation:** Rather than hiding rule weights inside code, this endpoint exposes the entire rulebook so the UI and evaluators can inspect every rule's exact point contribution.

---

### 6. Score a Transaction — `GET /transactions/{transaction_id}/risk`
- **Method & Path:** `GET /transactions/{transaction_id}/risk?method=contextual`
- **Why `GET` instead of `POST`:** Scoring is a pure, idempotent, read-only evaluation over stored historical records (it does not modify the database), making `GET` with a `method` query parameter RESTful, directly testable in a browser, and consistent with `GET /transactions/{transaction_id}`.
- **Path Parameters:**
  - `transaction_id` *(required)*: e.g., `TX-0391`.
- **Query Parameters:**
  - `method` *(optional, default `'contextual'`)*: One of `'baseline'`, `'contextual'`, or `'contextual_ti'`.
- **Service Called:** [`score_transaction`](app/services/scoring.py).
- **Reads/Writes Data:** Reads from `transactions`, `users`, `user_preferences`, `authentication_events`, `device_events`, `beneficiary_events`, and `threat_intelligence`.
- **Plain-Language Explanation:** Runs the selected scoring engine (`0–100` scale, capped at `100`) and returns:
  - `risk_score` and `raw_points_sum`
  - `triggered_rules`: Every rule that fired, its exact point contribution, a plain-English explanation, and `evidence_refs` (the primary keys of the supporting database records)
  - `counterfactual_summary`: A deterministic explanation of which rules pushed the score over the user's alert threshold and what the score would have been under normal conditions.

#### Example Request
```bash
curl -X GET "http://127.0.0.1:8000/transactions/TX-0391/risk?method=contextual"
```

#### Example Success Response (`200 OK`)
```json
{
  "transaction_id": "TX-0391",
  "user_id": "USR-001",
  "method": "contextual",
  "raw_points_sum": 135,
  "risk_score": 100,
  "risk_band": "critical",
  "user_alert_threshold": 55,
  "exceeds_user_threshold": true,
  "score_interpretation": "Rule-based heuristic priority score (0-100 scale, capped at 100). A score of 80 indicates strong rule-based forensic suspicion, NOT an 80% statistical probability of fraud.",
  "triggered_rules": [
    {
      "rule_id": "RAPID_NEW_BENEFICIARY",
      "rule_name": "Newly Added Beneficiary Rapid Transfer",
      "category": "counterparty",
      "points_awarded": 25,
      "max_points": 25,
      "explanation": "Beneficiary 'Unverified Instant Wallet #1' (BEN-ATO-NEW-001) was newly added at 2026-03-19T19:26:00Z (<60 mins before transfer).",
      "evidence_refs": ["BEN-EVT-0061", "TX-0391"]
    },
    {
      "rule_id": "IMPOSSIBLE_TRAVEL_GEO_VELOCITY",
      "rule_name": "Impossible Travel Geo-Velocity Hop",
      "category": "forensic_auth_device",
      "points_awarded": 25,
      "max_points": 25,
      "explanation": "User session hopped across geographic regions (IN-Mumbai -> NL-Amsterdam) within 120 minutes prior to transaction.",
      "evidence_refs": ["AUTH-EVT-0391", "AUTH-EVT-0395", "TX-0391"]
    }
  ],
  "counterfactual_summary": "Score (100/100) crossed the user's alert threshold (55) primarily due to Newly Added Beneficiary Rapid Transfer (+25), Impossible Travel Geo-Velocity Hop (+25). Counterfactual: Had this $157.55 transfer occurred without those factors (e.g., on a registered device to an established, unmodified 'personal_consumption' counterparty), the contextual score would have been 50/100 (No Alert)."
}
```

#### Important Error Responses
- `404 Not Found`: Unknown `transaction_id`.
- `422 Unprocessable Entity`: Invalid `method` parameter.

---

### 7. Side-by-Side 3-Method Comparison — `GET /transactions/{transaction_id}/risk/compare`
- **Method & Path:** `GET /transactions/{transaction_id}/risk/compare`
- **What it does:** Evaluates `baseline`, `contextual`, and `contextual_ti` on the same transaction simultaneously and returns all three results, score deltas (`delta_contextual_vs_baseline`, `delta_ti_vs_contextual`), and a `comparison_narrative`.
- **Service Called:** [`compare_transaction_scores`](app/services/scoring.py).
- **Plain-Language Explanation:** Powers the **Side-by-Side Waterfall / Diff View** on the Streamlit investigation page so you can show in one click how `contextual` eliminates false positives on legitimate CapEx/OpEx business transfers and catches stealthy ATO/BEC/Threat-Intel attacks that `baseline` misses.

---

### 8. Unified Forensic Evidence Timeline — `GET /transactions/{transaction_id}/timeline`
- **Method & Path:** `GET /transactions/{transaction_id}/timeline`
- **What it does:** Reconstructs a chronological, timestamp-sorted forensic timeline combining `device_events`, `authentication_events`, `beneficiary_events`, matched `threat_intelligence` indicators, prior 24h `transactions` (for structuring context), and the target transaction itself.
- **Path Parameters:**
  - `transaction_id` *(required)*: e.g., `TX-0391`.
- **Service Called:** [`build_transaction_timeline`](app/services/evidence.py).
- **Reads/Writes Data:** Reads from `transactions`, `users`, `authentication_events`, `device_events`, `beneficiary_events`, and `threat_intelligence`.
- **Plain-Language Explanation:** When investigating an incident, events are stored in separate database tables. This endpoint merges them into one chronological story (`sequence_no = 1..N`), keeps the exact `source_table` and `source_record_id` visible for provenance, separates **recorded facts** (`recorded_fact`) from **system interpretations** (`system_interpretation`), and tags each event with its **Forensic Kill-Chain Phase** (`RECON_BRUTE_FORCE`, `INITIAL_ACCESS`, `PREPARATION_PERSISTENCE`, `EXFILTRATION_EXECUTION`, or `NORMAL_ACTIVITY`).

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/transactions/TX-0391/timeline
```

#### Example Success Response (`200 OK`, abbreviated)
```json
{
  "transaction_id": "TX-0391",
  "user_id": "USR-001",
  "user_display_name": "Aarav Sharma (University Student)",
  "user_profile_type": "student",
  "user_expenditure_model": "personal_consumption",
  "target_timestamp_utc": "2026-03-19T19:30:00Z",
  "total_events": 8,
  "present_categories": ["authentication", "device", "beneficiary", "transaction"],
  "missing_categories": [],
  "kill_chain_phases_observed": [
    "NORMAL_ACTIVITY",
    "RECON_BRUTE_FORCE",
    "INITIAL_ACCESS",
    "PREPARATION_PERSISTENCE",
    "EXFILTRATION_EXECUTION"
  ],
  "timeline": [
    {
      "sequence_no": 2,
      "timestamp_utc": "2026-03-19T19:18:00Z",
      "event_category": "authentication",
      "event_type": "login_failure",
      "source_table": "authentication_events",
      "source_record_id": "AUTH-EVT-0392",
      "geo_location": "NL-Amsterdam",
      "ip_address": "185.220.101.55",
      "device_id": "DEV-UNSEEN-ATO-001",
      "recorded_fact": "Auth record AUTH-EVT-0392: event_type='login_failure', is_success=False, ip='185.220.101.55', geo='NL-Amsterdam', device_id='DEV-UNSEEN-ATO-001'.",
      "kill_chain_phase": "RECON_BRUTE_FORCE",
      "system_interpretation": "Failed authentication attempt ('login_failure') from IP 185.220.101.55 (NL-Amsterdam); consistent with credential stuffing or password guessing."
    }
  ]
}
```


