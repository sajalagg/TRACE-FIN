# TRACE-Fin --- Codex Project Guide

## 1. How to use this file

This file is the project brief and working agreement for Codex. Read it
before changing code.

**We are building TRACE-Fin together in small, understandable stages. Do
not build the entire application in one go.** The student should
understand the architecture, API flow, scoring logic, database, and
tests well enough to explain them in a classroom presentation.

At the start of each work session:

1.  Inspect the current repository and this guide.
2.  Tell the student what already exists and what is missing.
3.  Propose the smallest useful next step.
4.  Explain the planned change in plain language before implementing it.
5.  Implement only the agreed stage.
6.  Run relevant tests or checks.
7.  Summarize changed files, how to run the code, what the student
    should understand, and the next possible stage.

Do not silently make large architectural changes. Ask before introducing
a new framework, database, service, or major dependency. Prefer simple,
readable code over clever abstractions.

## 2. Project overview

**Project name:** TRACE-Fin\
**Expansion:** Transaction Risk Analysis, Correlation and Escalation for
Finance

**Working title:** *TRACE-Fin: Evidence-Aware Financial Transaction
Verification and Incident Response*

TRACE-Fin is an educational prototype that investigates suspicious
financial transactions by correlating transaction information with
surrounding security events. It uses explainable, rule-based risk
scoring, optional threat-intelligence enrichment, user-configurable
alert preferences, and a basic incident-response workflow.

The project is intended for a university classroom project and paper. It
is not a production banking system and must not connect to real bank
accounts or initiate, block, or transfer real money.

### Problem being explored

A transaction can look suspicious in isolation but be legitimate in
context. For example, a large payment could be normal for a particular
user, while a smaller payment shortly after repeated login failures,
from a new device, to a newly added beneficiary, may deserve
investigation.

The prototype asks:

> Does correlating transaction activity with authentication, device,
> beneficiary, and threat-intelligence context help prioritize
> suspicious transactions more usefully than transaction-only rules?

The project should demonstrate the workflow and evaluate it using
synthetic data. Do not claim that the system detects real-world fraud
accurately unless there is real, appropriately collected and validated
evidence.

## 3. Scope and safety boundaries

### In scope

-   Synthetic users and transactions.
-   Synthetic authentication, device, and beneficiary events.
-   A local, clearly labelled demonstration threat-intelligence dataset.
-   Explainable rule-based risk scores from 0 to 100.
-   Three comparable scoring approaches:
    1.  Transaction-only baseline.
    2.  Contextual forensic scoring.
    3.  Contextual scoring plus threat-intelligence matches.
-   Per-user alert threshold preferences.
-   Time-zone and quiet-hours preferences for non-urgent alerts.
-   A simulated verification request and response.
-   Creation of an incident when a user denies a transaction.
-   An evidence timeline and an incident register.
-   Evaluation metrics computed from labelled synthetic data.
-   Tests, setup instructions, and diagrams/documentation that help the
    student explain the API flow.

### Out of scope

-   Real bank, payment gateway, or identity-provider integrations.
-   Real money movement, account locking, or transaction blocking.
-   Real SMS, email, push, or WhatsApp notifications.
-   Claims of regulatory compliance or production readiness.
-   Live threat-intelligence API calls in the first version.
-   Machine learning in the first version.
-   Real personal, financial, or authentication data.

All demo data must be synthetic. Label threat-intelligence records as
**simulated/demo indicators**. Never imply that a sample IP address or
indicator is genuinely malicious unless the source has been verified and
documented.

## 4. Technology choices

Use a simple Python stack that works on macOS:

-   Python 3
-   Streamlit for the user interface
-   FastAPI for the backend API
-   SQLite for local persistence
-   Pandas for data handling and evaluation
-   Plotly for charts
-   Pytest for tests
-   Requests or HTTPX for the frontend-to-backend HTTP calls, choosing
    one and explaining why

Keep the frontend and backend separate:

-   **Streamlit** displays pages and collects user actions.
-   **FastAPI** exposes endpoints and coordinates application logic.
-   **Service modules** implement scoring, alert policy, verification,
    and incident creation.
-   **SQLite** stores synthetic data, preferences, verification records,
    and incidents.

Do not put all business logic in Streamlit page code or in API route
handlers. API routes should validate input, call the relevant service,
and return a response.

Use a simple project structure, adjusting only when there is a clear
reason:

``` text
trace-fin/
├── README.md
├── README.md
├── API_GUIDE.md
├── TRACE-Fin_PROJECT_GUIDE.md
├── requirements.txt
├── data/
│   └── README.md
├── scripts/
│   ├── seed_demo_data.py
│   └── run_evaluation.py
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── routes_auth.py
│   │   ├── routes_health.py
│   │   ├── routes_transactions.py
│   │   ├── routes_preferences.py
│   │   ├── routes_verification.py
│   │   ├── routes_incidents.py
│   │   └── routes_evaluation.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── policy.py
│   │   └── security.py
│   ├── models/
│   │   └── database_models.py
│   ├── schemas/
│   │   └── api_schemas.py
│   └── services/
│       ├── auth.py
│       ├── alert_policy.py
│       ├── evaluation.py
│       ├── evidence.py
│       ├── incidents.py
│       ├── scoring.py
│       ├── transactions.py
│       └── verification.py
└── frontend/
    ├── app.py
    ├── services/
    │   ├── config.py
    │   └── data_provider.py
    ├── ui/
    │   └── components.py
    └── pages/
        ├── 0_landing_auth.py
        ├── 1_overview_dashboard.py
        ├── 2_transaction_explorer.py
        ├── 3_risk_analysis_lab.py
        ├── 4_forensic_investigation.py
        ├── 5_threat_intelligence.py
        ├── 6_incident_register_evaluation.py
        ├── c1_customer_dashboard.py
        ├── c2_customer_beneficiaries.py
        ├── c3_customer_transfer.py
        ├── c4_customer_transactions.py
        ├── c5_customer_security_alerts.py
        └── c6_customer_profile_preferences.py
```

This is a suggested structure, not a requirement to create every file
immediately. Add files only as each stage needs them.

## 5. Working style: staged development

Build only one stage at a time. Do not proceed to the next stage until
the current stage runs and the student understands its main flow. At the
end of each stage, stop and ask whether to continue.

### Stage 0 --- Repository and plan

-   Inspect the repository.
-   Explain the proposed architecture and request flow.
-   Identify Python version and current environment.
-   Create or update `PROJECT_GUIDE.md` and a concise `README.md`.
-   Do not implement the full application.
-   Give the student a simple map of what will be built and in what
    order.

**Completion check:** the student understands what each major
folder/module is for.

### Stage 1 --- Minimal API skeleton

-   Create a minimal FastAPI application.
-   Add `GET /health`.
-   Add dependency/setup instructions.
-   Add a test for the health endpoint.
-   Run the backend locally and show a sample request and response.
-   Do not add the database, scoring, or UI yet.

**Teach:** what an API is, what an endpoint is, HTTP GET, JSON
responses, request/response, and how to start the server.

Example response:

``` json
{
  "status": "ok",
  "service": "TRACE-Fin"
}
```

**Completion check:** the student can start the server, call the
endpoint, and explain the response.

### Stage 2 --- SQLite and synthetic data

-   Define the minimum database schema needed for the first data flow.
-   Start with users and transactions; add related-event tables only
    when needed.
-   Create a reproducible seed script with a fixed random seed.
-   Generate approximately 500 synthetic transactions eventually, but
    begin with a small sample to validate the schema.
-   Include normal transactions, unusual-but-legitimate activity, and
    simulated suspicious/account-takeover scenarios.
-   Store ground-truth labels independently from scoring rules.
-   Make seeding safe to rerun: explain whether it resets demo data or
    avoids duplicates.
-   Add a database inspection/debugging method.

Suggested tables, to implement progressively:

-   `users`: synthetic user ID, display label, `account_category` (`individual` vs `business`), `profile_type` (e.g., `student`, `salaried_individual`, `freelancer`, `sme_opex_merchant`, `enterprise_capex_firm`, `high_net_worth`), `industry_sector` (e.g., `retail_ecommerce`, `saas_it_services`, `hospitality`, `manufacturing_heavy_machinery`, `construction_infra`, `education`, `personal_finance`), `expenditure_model` (`opex_heavy`, `capex_heavy`, `personal_consumption`), `net_worth_band` & `estimated_net_worth`, `declared_monthly_turnover`, `typical_tx_amount`, `typical_max_tx_amount`, `expected_monthly_tx_count`, and `operating_hours_utc` (e.g., `08:00-19:00` for business accounts).
-   `transactions`: ID, user ID, amount, currency, timestamp,
    beneficiary ID, `beneficiary_category` (`verified_b2b_vendor`, `employee_payroll`, `utility_tax`, `personal_peer`, `financial_brokerage`), `beneficiary_industry` (e.g., `heavy_machinery_equipment`, `raw_materials_steel_cement`, `cloud_saas_hosting`, `wholesale_fmcg_inventory`, `luxury_retail_jewelry`, `digital_assets_brokerage`, `general_consumer`), device ID, IP address, `geo_location` (e.g., `IN-Mumbai`, `GB-London`, `SG-Singapore`, `US-NewYork`, `NL-Amsterdam`), ground-truth label, and
    scenario label (covering 8 ablation-ready archetypes: `normal_routine`, `legitimate_capex_high_value`, `legitimate_opex_payroll_cycle`, `legitimate_travel_new_ip`, `low_and_slow_ato`, `b2b_vendor_bec_tamper`, `structured_smurfing_drain`, and `threat_intel_active_or_stale_ip`).
-   `authentication_events`: user ID, timestamp, event type, IP, `geo_location`, device,
    success/failure.
-   `device_events`: user ID, timestamp, device ID, event type,
    known/new indicator.
-   `beneficiary_events`: user ID, beneficiary ID, timestamp, event
    type (`beneficiary_added`, `beneficiary_bank_updated`, `beneficiary_verified`).
-   `threat_intelligence`: indicator, indicator type, source label,
    confidence/quality label (`high`, `medium`, `low`), first-seen/last-seen times,
    expiry/freshness metadata (`expires_at_utc`), and demo-source flag.
-   `user_preferences`: threshold, time zone, quiet-hours settings.
-   `verification_requests`: transaction ID, status, creation time,
    response time, response.
-   `incidents`: incident ID, related transaction, status, severity,
    reason, timestamps.
-   `incident_evidence`: incident ID, evidence type, linked record ID or explanation.

Avoid one giant table that duplicates all information. Prefer linked
records and explicit timestamps.

**Teach:** primary keys, foreign keys, why events are separate records,
seeding, and why test labels must not be calculated from the scoring
rules.

**Completion check:** the student can seed and inspect the database and
explain how a transaction is linked to related events.

### Stage 3 --- Read-only transaction API

-   Add a paginated or limited endpoint to list synthetic transactions.
-   Add an endpoint to retrieve one transaction and its related context.
-   Validate IDs and return clear 404 responses when a record does not
    exist.
-   Use response schemas so the API response shape is explicit.
-   Add tests for success and not-found cases.
-   Do not implement scoring yet.

Suggested endpoints:

-   `GET /transactions`
-   `GET /transactions/{transaction_id}`

**Teach:** path parameters, query parameters, response schemas, status
codes, and how Streamlit will consume the API.

**Completion check:** call both endpoints and explain where each
returned field came from.

### Stage 4 --- Explainable rule-based scoring

Implement three scoring approaches that can be compared on the same
transactions:

1.  **Transaction-only baseline (`baseline`):** single-transaction amount
    relative to generic historical pattern, basic transaction frequency,
    and unusual hour of day.
2.  **Contextual forensic scoring (`contextual`):** baseline plus
    profile-aware, counterparty-aware, and forensic security context:
    -   **User Financial & Business Profile Calibration:** evaluates
        transaction value against `estimated_net_worth`,
        `declared_monthly_turnover`, `typical_max_tx_amount`, and
        `expenditure_model` (`opex_heavy` vs `capex_heavy` vs
        `personal_consumption`). Large single transfers are expected for
        `capex_heavy` firms when backed by net worth and a matching
        supplier, whereas a massive single-lump-sum transfer on an
        `opex_heavy` business or `student` profile triggers a profile
        anomaly rule.
    -   **Counterparty Supply-Chain Affinity, Vendor BEC & Relationship
        Maturity (Idea 1):**
        -   *Industry Supply-Chain Affinity:* checks whether sender
            `industry_sector` / `expenditure_model` aligns with
            `beneficiary_category` and `beneficiary_industry` (e.g.,
            `construction_infra` paying `heavy_machinery_equipment` =
            normal CapEx; paying `luxury_retail_jewelry` or
            `personal_peer` = purpose mismatch).
        -   *Vendor Bank-Account Modification / BEC Detection:* flags
            high-value payments shortly after a
            `beneficiary_bank_updated` event on an existing supplier.
        -   *Relationship Maturity & Mule Convergence:* flags high-value
            first-time transfers (`0` prior history with beneficiary)
            and cross-user convergence (2+ unrelated users transferring
            to the same newly added beneficiary within 48 hours).
    -   **Structuring / "Smurfing" Detection (Idea 2):** computes rolling
        24-hour cumulative outflow across multiple transactions to detect
        attackers splitting transfers just below `typical_max_tx_amount`.
    -   **Cash-Flow Calendar & Business Operating Window Awareness
        (Idea 3):** accounts for month-end/month-start (`25th–5th`)
        payroll/vendor settlement cycles for `opex_heavy` businesses and
        flags off-hours corporate wires outside `operating_hours_utc`.
    -   **Forensic Security & Impossible Travel Context (Idea 4):**
        repeated failed logins, unseen device, unseen IP, and
        **Impossible Geo-Velocity** (e.g., login in `IN-Mumbai` followed
        by a transfer from `NL-Amsterdam` 20 minutes later).
3.  **Contextual plus threat intelligence (`contextual_ti`):** contextual
    scoring plus a match against the local demo threat-intelligence
    indicators, weighted by indicator `confidence_level` (`high`,
    `medium`, `low`) and checked against `expires_at_utc` (expired/stale
    indicators add 0 points and record an informational note).

Also provide:
-   **Counterfactual Explanations (Idea 5):** a deterministic plain-English summary returned with the score explaining which specific contextual factors pushed the score over the threshold and what the score would have been under normal conditions (e.g., known device + established supply-chain vendor).
-   **Side-by-Side Comparison Endpoint (`GET /transactions/{transaction_id}/risk/compare`):** returns all three scores, the delta rules added at each step, and the counterfactual summary.

Requirements:

-   Return a score from 0 to 100.
-   Return a list of triggered rules, each with a readable explanation
    and its contribution.
-   Cap the final score at 100.
-   Document every rule and weight in one place.
-   Use sensible, deterministic rules; do not use random values in
    scoring.
-   Avoid counting the same underlying event multiple times without a
    clear rationale.
-   Make missing evidence explicit rather than treating missing data as
    proof of safety.
-   Distinguish score from probability. A score of 80 means a high
    rule-based score, **not** an 80% probability of fraud.
-   Keep the three approaches independently callable so their results
    can be compared fairly.
-   Add unit tests for individual rules, score boundaries, missing
    context, and the final output schema.

Possible endpoint:

-   `GET /transactions/{transaction_id}/risk?method=baseline`
-   or `POST /risk/score` if there is a clear reason to submit a scoring
    request body.

Choose one API design, explain the trade-off, and document it. Do not
create both versions unnecessarily.

**Teach:** how a service is called by an endpoint, rule weights,
evidence explanations, deterministic testing, and why a heuristic score
is not a calibrated probability.

**Completion check:** the student can manually trace why a sample
transaction received its score.

### Stage 5 --- Evidence timeline and investigation view

-   Retrieve the transaction and relevant authentication, device, and
    beneficiary events.
-   Sort events by timestamp and present a unified timeline.
-   Keep the original event type, timestamp, `geo_location`, and source record reference
    visible.
-   Tag timeline entries with their **Forensic Kill-Chain Phase** (`RECON_BRUTE_FORCE`, `INITIAL_ACCESS`, `PREPARATION_PERSISTENCE`, `EXFILTRATION_EXECUTION`, or `NORMAL_ACTIVITY`) while clearly distinguishing recorded facts from system interpretations.
-   Add an investigation API response or endpoint if needed.
-   Add tests for ordering, kill-chain tagging, missing event categories, and empty
    timelines.

**Teach:** event correlation, timestamps, data provenance, and the
difference between evidence and inference.

**Completion check:** the student can point to the source records
supporting each timeline entry.

### Stage 6 --- User alert preferences

Allow each synthetic user to configure:

-   Risk-score threshold (for example, 20--90).
-   IANA time zone (for example, `Asia/Kolkata`, `Europe/London`,
    `America/New_York`, `America/Los_Angeles`, `Asia/Singapore`,
    `Asia/Dubai`).
-   Optional quiet-hours start/end times.

Policy requirements:

-   Compare the rule-based score to the user's threshold; do not label
    the threshold a probability or "confidence percentage."
-   Record or display the decision even when no alert is produced.
-   Quiet hours affect non-urgent alert delivery in the simulation; they
    must not erase evidence or prevent an incident from being recorded.
-   Define a clear demo policy for urgent/critical events. For example,
    critical events can bypass quiet hours for immediate review, while
    lower-severity notifications are deferred or shown as queued.
    Document that this is a demonstration policy, not a real bank
    security policy.
-   Correctly handle quiet hours that cross midnight and convert using
    the user's chosen time zone.
-   Make default preferences explicit.
-   Test threshold boundaries, time-zone conversion, overnight quiet
    hours, and critical-event behavior.

Do not implement real notification delivery. The UI may show "alert
now," "queued until quiet hours end," or "no alert under current
threshold."

**Teach:** policy decisions, local time vs UTC, IANA time zones, and why
alert preferences must not modify the underlying risk score.

**Completion check:** changing a threshold changes alert decisions, not
the score itself.

### Stage 7 --- Verification workflow

-   Show a simulated verification request for a flagged transaction.
-   Allow the synthetic user to respond "I made this transaction" or "I
    did not make this transaction."
-   Store the response and timestamps.
-   A denial should create an incident and link relevant evidence.
-   An approval should record the response but must not delete the risk
    evidence.
-   Prevent duplicate active incidents for the same transaction and
    verification event.
-   Handle invalid IDs and repeated responses clearly.
-   Add tests for approval, denial, duplicate requests, and repeated
    submissions.

Suggested endpoints:

-   `POST /verification-requests`
-   `POST /verification-requests/{request_id}/respond`

Use simple request/response schemas and document the exact JSON
expected.

**Teach:** POST requests, request bodies, state transitions,
idempotency/duplicate prevention, and how one API call triggers a
service that writes to multiple tables.

**Completion check:** the student can trace the full flow from a
transaction investigation to a stored verification response.

### Stage 8 --- Incident register

-   List incidents and filter by status/severity.
-   Show incident details, related transaction, user financial/business profile, risk explanations,
    timeline, verification response, and linked evidence.
-   Allow a simple status update such as `open`, `investigating`, and
    `closed`.
-   Store recommended next steps as suggestions, not automated
    real-world actions.
-   Preserve the original evidence references.
-   Add tests for incident creation, retrieval, and status changes.

Suggested endpoints:

-   `GET /incidents`
-   `GET /incidents/{incident_id}`
-   `PATCH /incidents/{incident_id}` for a narrowly defined status
    update

**Teach:** incident lifecycle, evidence linkage, tamper-evident forensic snapshots, and why recommendations
are not the same as actions.

**Completion check:** a denied transaction can be investigated from the
incident register without losing its supporting context.

### Stage 9 --- Streamlit UI

Build the UI only after the underlying API and services work.

Pages:

1.  **Dashboard:** totals, flagged transactions, open incidents, and
    recent activity.
2.  **Investigate Transaction:** searchable transaction list, **User Financial & Business Profile card** (showing industry, OpEx/CapEx model, net worth, and turnover envelope), **Side-by-Side 3-Method Risk Comparison Waterfall Chart**, rule explanations, and evidence timeline.
3.  **Verification Centre:** pending requests and simulated user
    response.
4.  **Incident Register:** list, filters, incident detail, status, and **SHA-256 Evidence Integrity Verification badge**.
5.  **Alert Preferences:** threshold, time zone, quiet hours, and an **Interactive "What-If" Policy Simulator** showing how threshold and local time changes affect delivery (`alert_now`, `queued_for_quiet_hours`, `bypass_quiet_hours_critical`, `below_threshold`) without changing the underlying risk score.
6.  **Evaluation:** metric cards and charts comparing the three scoring
    approaches; per-scenario & business-profile breakdown table; alert-volume/recall trade-off by threshold.

Use clear language suitable for a university demo. Display a persistent
disclaimer that all records are synthetic. Show which scoring method is
selected. Avoid fake live-status indicators or invented real-time data.

**Teach:** how the UI calls the API, how errors are displayed, and why
UI code should not directly modify the database.

**Completion check:** a user can complete the demo flow through the UI.

### Stage 10 --- Evaluation and reproducible results

Use the same held-out synthetic transactions and independent
ground-truth labels for all three scoring approaches.

Report at least:

-   Precision
-   Recall
-   F1 score
-   False-positive rate
-   Number/percentage of transactions flagged
-   Account-takeover scenario detection rate, if scenario labels support
    it
-   Alert volume and recall at different user thresholds

Requirements:

-   Define what counts as a positive prediction and how a threshold
    converts score to a label.
-   Define the confusion matrix terms.
-   Do not hardcode metric values in the UI or paper.
-   Do not invent or manually adjust results to make the method look
    better.
-   Make evaluation repeatable with a documented command or script.
-   Avoid data leakage: ground-truth labels and scenario names must not
    be scoring inputs.
-   Clearly state that results are from synthetic data and do not
    establish real-world fraud-detection performance.
-   Explain trade-offs: a lower alert threshold may improve recall but
    create more alerts; a higher threshold may reduce alert volume while
    missing more suspicious cases.

**Teach:** metric interpretation, false positives/negatives,
reproducibility, and limitations of synthetic evaluation.

**Completion check:** the charts and paper tables are generated from
actual runs of the evaluation code.

### Stage 11 --- Polish and paper support

Only after the working system and evaluation exist:

-   Run the complete test suite.
-   Check setup instructions on a clean environment.
-   Add architecture and API-flow diagrams.
-   Export evaluation metrics to CSV or JSON.
-   Prepare a short demo script.
-   Draft the paper's results section from actual metrics.
-   Document limitations, assumptions, and future work.
-   Do not claim novelty without a literature review.
-   Do not invent references, experimental results, or user studies.

## 6. API flow the student should understand

The intended high-level flow is:

``` text
Streamlit UI
    |
    | HTTP request (JSON)
    v
FastAPI endpoint
    |
    | validates parameters/body
    v
Service layer
    |
    | reads/writes through database functions
    v
SQLite database
    |
    | result returned to service
    v
FastAPI response (JSON)
    |
    v
Streamlit displays result
```

For example, investigating a transaction should roughly follow:

1.  The user selects a transaction in Streamlit.
2.  Streamlit calls `GET /transactions/{id}`.
3.  FastAPI validates the ID and asks the transaction/evidence service
    for the record and related events.
4.  The service retrieves the transaction and linked context from
    SQLite.
5.  FastAPI returns structured JSON.
6.  Streamlit displays the transaction and timeline.
7.  When the user asks for a risk score, the UI calls the scoring
    endpoint.
8.  The scoring service evaluates rules and returns the score plus
    explanations.
9.  The UI displays both the score and its contributing evidence.

A denial workflow should roughly follow:

1.  The user submits a simulated "I did not make this transaction"
    response.
2.  Streamlit sends a POST request containing the response.
3.  FastAPI validates the request and calls the verification service.
4.  The service stores the response and asks the incident service to
    create or retrieve the appropriate incident.
5.  The incident service links the transaction and supporting evidence
    and prevents duplicates.
6.  FastAPI returns the stored verification result and incident
    reference.
7.  Streamlit displays the outcome and a link to the incident.

Keep these steps aligned with the actual implementation. Update this
guide if the code's final design differs.

## 7. API documentation requirements

Use FastAPI's generated OpenAPI/Swagger page at `/docs` during
development.

For every endpoint, document:

-   HTTP method and path.
-   What the endpoint does.
-   Required path/query parameters.
-   Request body, if any.
-   Example request.
-   Example success response.
-   Important error responses.
-   Which service is called.
-   Whether it reads or writes data.
-   One plain-language explanation suitable for the student.

Maintain an `API_GUIDE.md` as endpoints are added. Do not wait until the
end to explain the API.

For every new endpoint, show the student a concrete request and
response. Explain JSON fields rather than only showing code.

## 8. Code quality and teaching requirements

-   Use type hints and Pydantic schemas where appropriate.
-   Use clear names and short functions.
-   Add comments for non-obvious decisions, not for every line.
-   Keep business logic testable without running Streamlit.
-   Use parameterized database queries or a safe ORM approach.
-   Do not store passwords, API keys, or secrets in source control.
-   Add `.gitignore` for virtual environments, database files where
    appropriate, caches, and secrets.
-   Handle errors explicitly; do not hide exceptions with broad
    `except: pass`.
-   Use UTC timestamps for stored event times, with explicit timezone
    conversion for display and quiet-hours evaluation.
-   Keep scoring deterministic.
-   Do not make external network requests in the core demo.
-   Do not add dependencies unless they serve a clear purpose.
-   Do not rewrite working code just to make it look more sophisticated.
-   If a requirement is ambiguous, ask a concise question or state the
    smallest reasonable assumption before coding.
-   When the student asks "why," explain the underlying concept, not
    just the implementation.

## 9. Testing expectations

At each stage:

1.  Add tests for the new behavior.
2.  Run the relevant tests.
3.  Show the exact command used.
4.  Explain what the tests verify.
5.  Fix failures before calling the stage complete.

At minimum, eventually test:

-   Health endpoint.
-   Database seeding and retrieval.
-   Missing transaction/incident IDs.
-   Scoring rules and score bounds.
-   Evidence timeline ordering.
-   Alert thresholds and quiet hours.
-   Verification approval and denial.
-   Incident creation and duplicate prevention.
-   API validation errors.
-   Evaluation metrics against a small known example.

Do not claim tests passed unless they were actually run.

## 10. Research and presentation guardrails

This is a classroom research prototype, not a validated banking product.

The paper can compare transaction-only, contextual, and
threat-intelligence-enriched rules. It can also show how personalized
thresholds alter the alert-volume/recall trade-off.

Be precise with language:

-   Say "rule-based risk score," not "fraud probability."
-   Say "simulated threat-intelligence indicators," not "live threat
    intelligence," unless live, verified sources are actually
    integrated.
-   Say "synthetic evaluation," not "real-world validation."
-   Do not claim that personalized thresholds reduce alert fatigue
    unless that effect has been studied with users. It is safe to say
    the feature is designed to let users control alert sensitivity and
    quiet hours.
-   Do not claim that an alert or incident automatically stops a bank
    transaction.
-   Report real results produced by the code, including results that are
    disappointing.
-   Keep limitations visible: synthetic data, hand-designed rules,
    limited scenarios, no live bank integration, and no user study.

## 11. Definition of done

The first complete classroom-ready version is done when:

-   The app starts using documented commands.
-   Demo data can be seeded reproducibly.
-   The API and UI work together.
-   A transaction can be investigated and its evidence timeline viewed.
-   The three scoring approaches return explainable scores.
-   User thresholds and quiet hours affect alert decisions as
    documented.
-   A simulated verification denial creates a linked incident.
-   Incidents can be reviewed and updated.
-   Evaluation metrics and charts are computed from code, not hardcoded.
-   Tests pass and the exact test command is documented.
-   The student can explain the API flow, the scoring rules, the
    database relationships, the evaluation, and the limitations.

## 12. What Codex should do first

**Start with Stage 0 only.** Inspect the repository and report:

1.  What files and code already exist.
2.  Whether a Python environment or dependencies are already configured.
3.  A concise architecture explanation.
4.  The first small implementation step you recommend.
5.  The exact commands the student will use to run and test that step.

Do not implement every stage in the first response. Wait for the
student's confirmation before starting Stage 1.
