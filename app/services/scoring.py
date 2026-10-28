from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.database import get_connection
from app.schemas.api_schemas import (
    RiskComparisonResponseSchema,
    RiskScoreResponseSchema,
    RuleDefinitionSchema,
    TriggeredRuleSchema,
)

VALID_SCORING_METHODS = ("baseline", "contextual", "contextual_ti")

SCORE_INTERPRETATION_TEXT = (
    "Rule-based heuristic priority score (0-100 scale, capped at 100). "
    "A score of 80 indicates strong rule-based forensic suspicion, NOT an 80% statistical probability of fraud."
)

# Central documented catalog of all rules and weights (Stage 4 requirement)
RULE_CATALOG: List[RuleDefinitionSchema] = [
    RuleDefinitionSchema(
        rule_id="BASELINE_ABS_AMOUNT_SPIKE",
        rule_name="Transaction-Only Raw Rupee Threshold",
        applies_to_methods=["baseline"],
        category="baseline",
        max_points=40,
        description=(
            "Flags transactions that exceed static raw rupee thresholds (₹2,500 / ₹15,000) "
            "without considering whether the user is an OpEx/CapEx business or high-net-worth profile."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="BASELINE_USER_MEAN_DEVIATION",
        rule_name="Transaction-Only Historical Mean Multiplier",
        applies_to_methods=["baseline"],
        category="baseline",
        max_points=30,
        description=(
            "Flags transactions that exceed 2.0x the user's simple historical average transaction amount, "
            "ignoring CapEx equipment cycles or month-end payroll settlements."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="BASELINE_HOURLY_VELOCITY",
        rule_name="Transaction-Only 60-Minute Velocity",
        applies_to_methods=["baseline"],
        category="baseline",
        max_points=25,
        description="Flags 2 or more transactions by the same user within a 60-minute window.",
    ),
    RuleDefinitionSchema(
        rule_id="BASELINE_UNUSUAL_UTC_HOUR",
        rule_name="Transaction-Only Late-Night UTC Window",
        applies_to_methods=["baseline"],
        category="baseline",
        max_points=15,
        description="Flags transactions occurring between 00:00 and 04:59 UTC or late evening 20:00-23:59 UTC.",
    ),
    RuleDefinitionSchema(
        rule_id="PROFILE_VALUE_ANOMALY",
        rule_name="Profile-Calibrated Value & Net-Worth Anomaly",
        applies_to_methods=["contextual", "contextual_ti"],
        category="profile",
        max_points=35,
        description=(
            "Evaluates transaction amount against the user's declared typical_max_tx_amount, "
            "estimated_net_worth, expenditure_model (opex_heavy vs capex_heavy), and month-end payroll calendar."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="VENDOR_BEC_BANK_MODIFIED",
        rule_name="Vendor Bank-Detail Modification (BEC Pattern)",
        applies_to_methods=["contextual", "contextual_ti"],
        category="counterparty",
        max_points=65,
        description=(
            "Flags transfers to an existing beneficiary whose bank routing/account details were updated "
            "(beneficiary_bank_updated) within 120 minutes prior to disbursement."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="RAPID_NEW_BENEFICIARY",
        rule_name="Newly Added Beneficiary Rapid Transfer",
        applies_to_methods=["contextual", "contextual_ti"],
        category="counterparty",
        max_points=25,
        description="Flags transfers sent within 60 minutes of adding a new beneficiary (beneficiary_added).",
    ),
    RuleDefinitionSchema(
        rule_id="SUPPLY_CHAIN_PURPOSE_MISMATCH",
        rule_name="Sender-to-Counterparty Industry/Purpose Mismatch",
        applies_to_methods=["contextual", "contextual_ti"],
        category="counterparty",
        max_points=15,
        description=(
            "Flags transfers where the beneficiary industry/category conflicts with the sender's "
            "industry_sector and expenditure_model (e.g., corporate CapEx/OpEx account paying luxury retail or unverified digital brokerage)."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="CROSS_USER_MULE_CONVERGENCE",
        rule_name="Cross-Account Money-Mule Convergence",
        applies_to_methods=["contextual", "contextual_ti"],
        category="counterparty",
        max_points=25,
        description="Flags beneficiaries receiving transfers or additions from 2 or more unrelated users within 48 hours.",
    ),
    RuleDefinitionSchema(
        rule_id="STRUCTURING_CUMULATIVE_DRAIN",
        rule_name="Rolling 24h Structuring / Smurfing Velocity",
        applies_to_methods=["contextual", "contextual_ti"],
        category="structuring",
        max_points=30,
        description=(
            "Detects cumulative 24-hour outflow exceeding 1.4x typical_max_tx_amount across multiple split transfers, "
            "or transfers sized in the structuring band (75%-98% of max limit) to a newly added unverified beneficiary."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="OFF_HOURS_ACTIVITY",
        rule_name="Outside Declared User/Business Operating Hours",
        applies_to_methods=["contextual", "contextual_ti"],
        category="temporal",
        max_points=10,
        description="Flags transactions initiated outside the user's declared operating_hours_utc window.",
    ),
    RuleDefinitionSchema(
        rule_id="REPEATED_FAILED_LOGINS",
        rule_name="Preceding Authentication Failures",
        applies_to_methods=["contextual", "contextual_ti"],
        category="forensic_auth_device",
        max_points=20,
        description="Flags 1 or more failed login or MFA attempts within 60 minutes prior to the transaction.",
    ),
    RuleDefinitionSchema(
        rule_id="UNSEEN_DEVICE_USED",
        rule_name="Unregistered / First-Seen Device",
        applies_to_methods=["contextual", "contextual_ti"],
        category="forensic_auth_device",
        max_points=20,
        description="Flags transactions initiated from a device marked as 'new' or absent from baseline registered devices.",
    ),
    RuleDefinitionSchema(
        rule_id="IMPOSSIBLE_TRAVEL_GEO_VELOCITY",
        rule_name="Impossible Travel Geo-Velocity Hop",
        applies_to_methods=["contextual", "contextual_ti"],
        category="forensic_auth_device",
        max_points=25,
        description="Flags a geographic location change across authentication/transaction events within 120 minutes.",
    ),
    RuleDefinitionSchema(
        rule_id="FOREIGN_GEO_KNOWN_DEVICE",
        rule_name="Foreign Location on Registered Device (Plausible Travel)",
        applies_to_methods=["contextual", "contextual_ti"],
        category="forensic_auth_device",
        max_points=10,
        description="Low-weight note when a user transacts outside home_geo_location on a known device without impossible travel.",
    ),
    RuleDefinitionSchema(
        rule_id="MISSING_AUTH_TELEMETRY",
        rule_name="Missing Authentication Telemetry",
        applies_to_methods=["contextual", "contextual_ti"],
        category="telemetry",
        max_points=10,
        description="Explicitly records missing authentication history rather than assuming missing evidence is safe.",
    ),
    RuleDefinitionSchema(
        rule_id="THREAT_INTEL_ACTIVE_MATCH",
        rule_name="Active Simulated Threat-Intelligence Match",
        applies_to_methods=["contextual_ti"],
        category="threat_intel",
        max_points=30,
        description=(
            "Matches transaction IP or beneficiary against active (non-expired) simulated threat-intelligence "
            "indicators, weighted by confidence level (high=30, medium=20, low=10)."
        ),
    ),
    RuleDefinitionSchema(
        rule_id="THREAT_INTEL_EXPIRED_INDICATOR",
        rule_name="Expired / Stale Threat-Intelligence Match (Informational)",
        applies_to_methods=["contextual_ti"],
        category="threat_intel",
        max_points=0,
        description="Records when an indicator matches the demo feed but expired prior to the transaction timestamp (0 points added).",
    ),
]


# Expected counterparty industries per sender industry sector (Idea 1A: Supply-Chain Affinity)
EXPECTED_SUPPLY_CHAIN_INDUSTRIES: Dict[str, Tuple[str, ...]] = {
    "manufacturing_heavy_machinery": (
        "raw_materials_steel_cement",
        "heavy_machinery_equipment",
        "logistics_freight",
        "utilities_municipal",
        "payroll_settlement",
    ),
    "construction_infra": (
        "raw_materials_steel_cement",
        "heavy_machinery_equipment",
        "construction_subcontractor",
        "logistics_freight",
        "utilities_municipal",
        "payroll_settlement",
    ),
    "energy_utilities": (
        "heavy_machinery_equipment",
        "construction_subcontractor",
        "utilities_municipal",
        "payroll_settlement",
    ),
    "retail_ecommerce": (
        "wholesale_fmcg_inventory",
        "logistics_freight",
        "payroll_settlement",
        "utilities_municipal",
        "cloud_saas_hosting",
    ),
    "saas_it_services": (
        "cloud_saas_hosting",
        "payroll_settlement",
        "utilities_municipal",
    ),
    "hospitality": (
        "wholesale_fmcg_inventory",
        "utilities_municipal",
        "payroll_settlement",
    ),
    "private_wealth": (
        "wealth_management",
        "luxury_travel_hospitality",
        "property_management",
        "general_consumer",
        "utilities_municipal",
    ),
    "education": ("utilities_municipal", "general_consumer"),
    "personal_finance": ("utilities_municipal", "general_consumer"),
    "independent_consulting": ("utilities_municipal", "general_consumer", "cloud_saas_hosting"),
}


def get_rule_catalog() -> List[RuleDefinitionSchema]:
    """Return the complete documented rule catalog."""
    return RULE_CATALOG


def _parse_utc(ts_str: str) -> datetime:
    """Parse an ISO-8601 UTC string (`YYYY-MM-DDTHH:MM:SSZ`) into a naive UTC datetime."""
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")


def _fmt_utc(dt: datetime) -> str:
    """Format a naive UTC datetime into `YYYY-MM-DDTHH:MM:SSZ`."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _score_to_band(score: int) -> str:
    """Map a 0-100 risk score to a human-readable severity band."""
    if score >= 85:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _is_hour_in_operating_window(hour: int, window_str: str) -> bool:
    """Return True if `hour` (0-23 UTC) is within `HH:MM-HH:MM`."""
    start_s, end_s = window_str.split("-")
    start_h = int(start_s.split(":")[0])
    end_h = int(end_s.split(":")[0])
    if start_h <= end_h:
        return start_h <= hour <= end_h
    return hour >= start_h or hour <= end_h


def _evaluate_baseline_rules(
    conn: sqlite3.Connection,
    tx_row: sqlite3.Row,
) -> List[TriggeredRuleSchema]:
    """Evaluate Method 1 (`baseline`): transaction-only heuristics without profile or forensic context."""
    triggered: List[TriggeredRuleSchema] = []
    tx_id = tx_row["transaction_id"]
    user_id = tx_row["user_id"]
    amount = float(tx_row["amount"])
    tx_time_str = tx_row["timestamp_utc"]
    tx_dt = _parse_utc(tx_time_str)

    # 1. Static raw rupee threshold (ignores OpEx/CapEx business profile and net worth)
    if amount >= 15000.0:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="BASELINE_ABS_AMOUNT_SPIKE",
                rule_name="Transaction-Only Raw Rupee Threshold",
                category="baseline",
                points_awarded=40,
                max_points=40,
                explanation=(
                    f"Transaction amount (₹{amount:,.2f}) exceeds the static high-value threshold (₹15,000.00). "
                    f"Baseline rules do not account for CapEx/OpEx business profiles."
                ),
                evidence_refs=[tx_id],
            )
        )
    elif amount >= 2500.0:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="BASELINE_ABS_AMOUNT_SPIKE",
                rule_name="Transaction-Only Raw Rupee Threshold",
                category="baseline",
                points_awarded=30,
                max_points=40,
                explanation=(
                    f"Transaction amount (₹{amount:,.2f}) exceeds the static medium threshold (₹2,500.00)."
                ),
                evidence_refs=[tx_id],
            )
        )

    # 2. Simple historical mean deviation (ignores CapEx lumpiness or month-end payroll runs)
    hist_row = conn.execute(
        """
        SELECT AVG(amount) AS avg_amt, COUNT(*) AS cnt
        FROM transactions
        WHERE user_id = ? AND timestamp_utc < ?;
        """,
        (user_id, tx_time_str),
    ).fetchone()
    hist_avg = float(hist_row["avg_amt"]) if hist_row and hist_row["avg_amt"] is not None else amount
    ratio_to_avg = amount / max(hist_avg, 1.0)

    if ratio_to_avg >= 1.8:
        pts = 30 if ratio_to_avg >= 2.2 else 25
        triggered.append(
            TriggeredRuleSchema(
                rule_id="BASELINE_USER_MEAN_DEVIATION",
                rule_name="Transaction-Only Historical Mean Multiplier",
                category="baseline",
                points_awarded=pts,
                max_points=30,
                explanation=(
                    f"Transaction amount (₹{amount:,.2f}) is {ratio_to_avg:.1f}x the user's prior "
                    f"average transaction (₹{hist_avg:,.2f})."
                ),
                evidence_refs=[tx_id],
            )
        )

    # 2. 60-minute transaction frequency
    win_start = _fmt_utc(tx_dt - timedelta(minutes=60))
    vel_rows = conn.execute(
        """
        SELECT transaction_id
        FROM transactions
        WHERE user_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
        ORDER BY timestamp_utc ASC;
        """,
        (user_id, win_start, tx_time_str),
    ).fetchall()
    if len(vel_rows) >= 2:
        pts = 25 if len(vel_rows) >= 3 else 15
        triggered.append(
            TriggeredRuleSchema(
                rule_id="BASELINE_HOURLY_VELOCITY",
                rule_name="Transaction-Only 60-Minute Velocity",
                category="baseline",
                points_awarded=pts,
                max_points=25,
                explanation=f"{len(vel_rows)} transactions recorded for {user_id} within 60 minutes.",
                evidence_refs=[r["transaction_id"] for r in vel_rows],
            )
        )

    # 3. Late-night / evening UTC timing
    if 0 <= tx_dt.hour <= 4:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="BASELINE_UNUSUAL_UTC_HOUR",
                rule_name="Transaction-Only Late-Night UTC Window",
                category="baseline",
                points_awarded=15,
                max_points=15,
                explanation=f"Transaction occurred at {tx_dt.strftime('%H:%M')} UTC (00:00-04:59 UTC window).",
                evidence_refs=[tx_id],
            )
        )
    elif tx_dt.hour >= 19:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="BASELINE_UNUSUAL_UTC_HOUR",
                rule_name="Transaction-Only Late-Night UTC Window",
                category="baseline",
                points_awarded=10,
                max_points=15,
                explanation=f"Transaction occurred at {tx_dt.strftime('%H:%M')} UTC (evening UTC window).",
                evidence_refs=[tx_id],
            )
        )

    return triggered


def _evaluate_contextual_rules(
    conn: sqlite3.Connection,
    tx_row: sqlite3.Row,
    user_row: sqlite3.Row,
) -> List[TriggeredRuleSchema]:
    """Evaluate Method 2 (`contextual`): profile-calibrated, counterparty/BEC, structuring, and forensic rules."""
    triggered: List[TriggeredRuleSchema] = []

    tx_id = tx_row["transaction_id"]
    user_id = tx_row["user_id"]
    amount = float(tx_row["amount"])
    tx_time_str = tx_row["timestamp_utc"]
    tx_dt = _parse_utc(tx_time_str)
    ben_id = tx_row["beneficiary_id"]
    ben_cat = tx_row["beneficiary_category"]
    ben_ind = tx_row["beneficiary_industry"]
    dev_id = tx_row["device_id"]
    tx_geo = tx_row["geo_location"]

    profile_type = user_row["profile_type"]
    sector = user_row["industry_sector"]
    exp_model = user_row["expenditure_model"]
    net_worth = float(user_row["estimated_net_worth"])
    max_tx = float(user_row["typical_max_tx_amount"])
    op_hours = user_row["operating_hours_utc"]
    home_geo = user_row["home_geo_location"]

    # --- Pre-fetch forensic context up to `tx_time_str` ---
    win_60m = _fmt_utc(tx_dt - timedelta(minutes=60))
    win_120m = _fmt_utc(tx_dt - timedelta(minutes=120))
    win_24h = _fmt_utc(tx_dt - timedelta(hours=24))
    win_48h = _fmt_utc(tx_dt - timedelta(hours=48))

    # Auth events in last 60m & all prior auth events
    prior_auth_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM authentication_events WHERE user_id = ? AND timestamp_utc <= ?;",
        (user_id, tx_time_str),
    ).fetchone()["cnt"]

    failed_auth_rows = conn.execute(
        """
        SELECT event_id, timestamp_utc, ip_address, geo_location
        FROM authentication_events
        WHERE user_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ? AND is_success = 0
        ORDER BY timestamp_utc ASC;
        """,
        (user_id, win_60m, tx_time_str),
    ).fetchall()

    # Device status check
    dev_rows = conn.execute(
        """
        SELECT event_id, known_status, event_type
        FROM device_events
        WHERE user_id = ? AND device_id = ? AND timestamp_utc <= ?
        ORDER BY timestamp_utc DESC;
        """,
        (user_id, dev_id, tx_time_str),
    ).fetchall()
    is_unseen_device = (len(dev_rows) == 0) or (dev_rows[0]["known_status"] == "new")

    # Beneficiary events check (for BEC bank updates and rapid new additions)
    ben_events_120m = conn.execute(
        """
        SELECT event_id, event_type, timestamp_utc, notes
        FROM beneficiary_events
        WHERE user_id = ? AND beneficiary_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
        ORDER BY timestamp_utc DESC;
        """,
        (user_id, ben_id, win_120m, tx_time_str),
    ).fetchall()

    bec_events = [b for b in ben_events_120m if b["event_type"] == "beneficiary_bank_updated"]
    rapid_add_events = [
        b
        for b in ben_events_120m
        if b["event_type"] == "beneficiary_added" and b["timestamp_utc"] >= win_60m
    ]

    # --- 1. Counterparty Supply-Chain Affinity, Vendor BEC & Mule Convergence (Idea 1) ---
    if bec_events:
        bec_ev = bec_events[0]
        pts = 65 if amount >= 0.5 * max_tx else 45
        triggered.append(
            TriggeredRuleSchema(
                rule_id="VENDOR_BEC_BANK_MODIFIED",
                rule_name="Vendor Bank-Detail Modification (BEC Pattern)",
                category="counterparty",
                points_awarded=pts,
                max_points=65,
                explanation=(
                    f"Existing counterparty '{tx_row['beneficiary_name']}' ({ben_id}) had its bank account/routing "
                    f"modified at {bec_ev['timestamp_utc']} shortly before this ₹{amount:,.2f} disbursement."
                ),
                evidence_refs=[bec_ev["event_id"], tx_id],
            )
        )

    if rapid_add_events:
        add_ev = rapid_add_events[0]
        triggered.append(
            TriggeredRuleSchema(
                rule_id="RAPID_NEW_BENEFICIARY",
                rule_name="Newly Added Beneficiary Rapid Transfer",
                category="counterparty",
                points_awarded=25,
                max_points=25,
                explanation=(
                    f"Beneficiary '{tx_row['beneficiary_name']}' ({ben_id}) was newly added at "
                    f"{add_ev['timestamp_utc']} (<60 mins before transfer)."
                ),
                evidence_refs=[add_ev["event_id"], tx_id],
            )
        )

    expected_inds = EXPECTED_SUPPLY_CHAIN_INDUSTRIES.get(sector, ("general_consumer", "utilities_municipal"))
    if ben_ind not in expected_inds:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="SUPPLY_CHAIN_PURPOSE_MISMATCH",
                rule_name="Sender-to-Counterparty Industry/Purpose Mismatch",
                category="counterparty",
                points_awarded=15,
                max_points=15,
                explanation=(
                    f"Counterparty industry '{ben_ind}' ({ben_cat}) is outside the expected supply-chain/spending "
                    f"profile for sender sector '{sector}' ({exp_model})."
                ),
                evidence_refs=[tx_id],
            )
        )

    # Cross-user money-mule convergence: 2+ distinct users interacting with the same beneficiary within 48h
    if ben_cat not in ("utility_tax", "employee_payroll"):
        mule_rows = conn.execute(
            """
            SELECT DISTINCT user_id, transaction_id
            FROM transactions
            WHERE beneficiary_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ?;
            """,
            (ben_id, win_48h, tx_time_str),
        ).fetchall()
        distinct_mule_users = {r["user_id"] for r in mule_rows}
        # Also check beneficiary_events across users in 48h
        mule_ben_rows = conn.execute(
            """
            SELECT DISTINCT user_id, event_id
            FROM beneficiary_events
            WHERE beneficiary_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ?;
            """,
            (ben_id, win_48h, tx_time_str),
        ).fetchall()
        distinct_mule_users |= {r["user_id"] for r in mule_ben_rows}

        if len(distinct_mule_users) >= 2:
            refs = [r[" event_id"] if " event_id" in r.keys() else r["event_id"] for r in mule_ben_rows[:3]]
            triggered.append(
                TriggeredRuleSchema(
                    rule_id="CROSS_USER_MULE_CONVERGENCE",
                    rule_name="Cross-Account Money-Mule Convergence",
                    category="counterparty",
                    points_awarded=25,
                    max_points=25,
                    explanation=(
                        f"Beneficiary {ben_id} ('{tx_row['beneficiary_name']}') was added or paid by "
                        f"{len(distinct_mule_users)} unrelated users ({', '.join(sorted(distinct_mule_users))}) within 48 hours."
                    ),
                    evidence_refs=[*refs, tx_id],
                )
            )

    # --- 2. Profile & Expenditure Calibration (User Financial & Business Profile) ---
    max_ratio = amount / max_tx
    nw_ratio = amount / net_worth
    is_month_end_payroll = (
        exp_model == "opex_heavy"
        and (tx_dt.day >= 25 or tx_dt.day <= 5)
        and ben_cat in ("employee_payroll", "verified_b2b_vendor")
    )
    is_legit_capex_vendor = (
        exp_model == "capex_heavy"
        and ben_cat == "verified_b2b_vendor"
        and ben_ind in expected_inds
        and not bec_events
    )

    if max_ratio > 1.0 or nw_ratio >= 0.25:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="PROFILE_VALUE_ANOMALY",
                rule_name="Profile-Calibrated Value & Net-Worth Anomaly",
                category="profile",
                points_awarded=35,
                max_points=35,
                explanation=(
                    f"Amount (₹{amount:,.2f}) is {max_ratio:.2f}x the user's declared max transaction (₹{max_tx:,.2f}) "
                    f"and {nw_ratio * 100:.1f}% of estimated net worth (₹{net_worth:,.0f}) for profile '{profile_type}' ({exp_model})."
                ),
                evidence_refs=[user_id, tx_id],
            )
        )
    elif (
        max_ratio >= 0.55
        and not is_month_end_payroll
        and not is_legit_capex_vendor
        and (is_unseen_device or rapid_add_events or failed_auth_rows)
    ):
        triggered.append(
            TriggeredRuleSchema(
                rule_id="PROFILE_VALUE_ANOMALY",
                rule_name="Profile-Calibrated Value & Net-Worth Anomaly",
                category="profile",
                points_awarded=15,
                max_points=35,
                explanation=(
                    f"Amount (₹{amount:,.2f}) represents {max_ratio * 100:.0f}% of declared single-tx limit (₹{max_tx:,.2f}) "
                    f"for '{profile_type}' ({exp_model}) under anomalous session/counterparty context."
                ),
                evidence_refs=[user_id, tx_id],
            )
        )

    # --- 3. Structuring / "Smurfing" Detection (Idea 2) ---
    tx_24h_rows = conn.execute(
        """
        SELECT transaction_id, amount, timestamp_utc
        FROM transactions
        WHERE user_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
        ORDER BY timestamp_utc ASC;
        """,
        (user_id, win_24h, tx_time_str),
    ).fetchall()
    cum_24h_amount = sum(float(r["amount"]) for r in tx_24h_rows)
    cum_ratio = cum_24h_amount / max_tx

    if (
        len(tx_24h_rows) >= 2
        and cum_ratio >= 1.4
        and not is_month_end_payroll
        and not is_legit_capex_vendor
    ):
        pts = 30 if (cum_ratio >= 2.0 or len(tx_24h_rows) >= 3) else 25
        triggered.append(
            TriggeredRuleSchema(
                rule_id="STRUCTURING_CUMULATIVE_DRAIN",
                rule_name="Rolling 24h Structuring / Smurfing Velocity",
                category="structuring",
                points_awarded=pts,
                max_points=30,
                explanation=(
                    f"{len(tx_24h_rows)} transfers in 24h totaling ₹{cum_24h_amount:,.2f} "
                    f"({cum_ratio:.2f}x the user's ₹{max_tx:,.2f} single-transaction limit) indicate structured splitting."
                ),
                evidence_refs=[r["transaction_id"] for r in tx_24h_rows],
            )
        )
    elif 0.75 <= max_ratio < 0.98 and rapid_add_events and is_unseen_device:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="STRUCTURING_CUMULATIVE_DRAIN",
                rule_name="Rolling 24h Structuring / Smurfing Velocity",
                category="structuring",
                points_awarded=20,
                max_points=30,
                explanation=(
                    f"Transfer amount (₹{amount:,.2f}) is sized just below the ₹{max_tx:,.2f} profile limit "
                    f"({max_ratio * 100:.0f}%) to a newly added beneficiary from an unseen device."
                ),
                evidence_refs=[tx_id],
            )
        )

    # --- 4. Cash-Flow Calendar & Operating Hours Awareness (Idea 3) ---
    if not _is_hour_in_operating_window(tx_dt.hour, op_hours):
        triggered.append(
            TriggeredRuleSchema(
                rule_id="OFF_HOURS_ACTIVITY",
                rule_name="Outside Declared User/Business Operating Hours",
                category="temporal",
                points_awarded=10,
                max_points=10,
                explanation=(
                    f"Transaction at {tx_dt.strftime('%H:%M')} UTC is outside declared operating window "
                    f"({op_hours} UTC) for '{profile_type}'."
                ),
                evidence_refs=[user_id, tx_id],
            )
        )

    # --- 5. Session & Geo-Velocity Forensics (Idea 4) ---
    if failed_auth_rows:
        f_cnt = len(failed_auth_rows)
        pts = 20 if f_cnt >= 2 else 12
        triggered.append(
            TriggeredRuleSchema(
                rule_id="REPEATED_FAILED_LOGINS",
                rule_name="Preceding Authentication Failures",
                category="forensic_auth_device",
                points_awarded=pts,
                max_points=20,
                explanation=f"{f_cnt} failed login attempt(s) recorded within 60 minutes prior to transaction.",
                evidence_refs=[r["event_id"] for r in failed_auth_rows],
            )
        )

    if is_unseen_device:
        dev_refs = [r["event_id"] for r in dev_rows] if dev_rows else [tx_id]
        triggered.append(
            TriggeredRuleSchema(
                rule_id="UNSEEN_DEVICE_USED",
                rule_name="Unregistered / First-Seen Device",
                category="forensic_auth_device",
                points_awarded=20,
                max_points=20,
                explanation=f"Transaction initiated from unseen/newly detected device '{dev_id}'.",
                evidence_refs=dev_refs,
            )
        )

    # Check Impossible Travel Geo-Velocity within last 120 minutes
    recent_geo_rows = conn.execute(
        """
        SELECT event_id, timestamp_utc, geo_location
        FROM authentication_events
        WHERE user_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ? AND is_success = 1
        ORDER BY timestamp_utc ASC;
        """,
        (user_id, win_120m, tx_time_str),
    ).fetchall()
    distinct_recent_geos = []
    for r in recent_geo_rows:
        if r["geo_location"] not in distinct_recent_geos:
            distinct_recent_geos.append(r["geo_location"])
    if tx_geo not in distinct_recent_geos:
        distinct_recent_geos.append(tx_geo)

    if len(distinct_recent_geos) >= 2:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="IMPOSSIBLE_TRAVEL_GEO_VELOCITY",
                rule_name="Impossible Travel Geo-Velocity Hop",
                category="forensic_auth_device",
                points_awarded=25,
                max_points=25,
                explanation=(
                    f"User session hopped across geographic regions ({' -> '.join(distinct_recent_geos)}) "
                    f"within 120 minutes prior to transaction."
                ),
                evidence_refs=[*[r["event_id"] for r in recent_geo_rows], tx_id],
            )
        )
    elif tx_geo != home_geo and not is_unseen_device:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="FOREIGN_GEO_KNOWN_DEVICE",
                rule_name="Foreign Location on Registered Device (Plausible Travel)",
                category="forensic_auth_device",
                points_awarded=10,
                max_points=10,
                explanation=(
                    f"Transaction originated from '{tx_geo}' (home region '{home_geo}') using a known "
                    f"registered device '{dev_id}' with no impossible-travel velocity conflict."
                ),
                evidence_refs=[tx_id],
            )
        )

    # --- 6. Missing Telemetry Check ---
    if prior_auth_count == 0:
        triggered.append(
            TriggeredRuleSchema(
                rule_id="MISSING_AUTH_TELEMETRY",
                rule_name="Missing Authentication Telemetry",
                category="telemetry",
                points_awarded=10,
                max_points=10,
                explanation=(
                    "No authentication events exist prior to this transaction timestamp; "
                    "missing telemetry is recorded explicitly rather than assumed safe."
                ),
                evidence_refs=[tx_id],
            )
        )

    return triggered


def _evaluate_threat_intel_rules(
    conn: sqlite3.Connection,
    tx_row: sqlite3.Row,
) -> List[TriggeredRuleSchema]:
    """Evaluate Method 3 (`contextual_ti`) threat-intelligence enrichment rules with expiry checks."""
    triggered: List[TriggeredRuleSchema] = []
    tx_id = tx_row["transaction_id"]
    tx_time_str = tx_row["timestamp_utc"]
    ip_addr = tx_row["ip_address"]
    ben_id = tx_row["beneficiary_id"]

    ti_rows = conn.execute(
        """
        SELECT *
        FROM threat_intelligence
        WHERE indicator IN (?, ?)
        ORDER BY indicator_type ASC;
        """,
        (ip_addr, ben_id),
    ).fetchall()

    confidence_weights = {"high": 30, "medium": 20, "low": 10}

    for ti in ti_rows:
        indicator = ti["indicator"]
        ind_type = ti["indicator_type"]
        conf = ti["confidence_level"]
        expires_at = ti["expires_at_utc"]
        source = ti["source_label"]

        if expires_at >= tx_time_str:
            pts = confidence_weights.get(conf, 10)
            triggered.append(
                TriggeredRuleSchema(
                    rule_id="THREAT_INTEL_ACTIVE_MATCH",
                    rule_name="Active Simulated Threat-Intelligence Match",
                    category="threat_intel",
                    points_awarded=pts,
                    max_points=30,
                    explanation=(
                        f"Active simulated indicator match on {ind_type} '{indicator}' "
                        f"(source={source}, confidence={conf}, expires={expires_at})."
                    ),
                    evidence_refs=[indicator, tx_id],
                )
            )
        else:
            triggered.append(
                TriggeredRuleSchema(
                    rule_id="THREAT_INTEL_EXPIRED_INDICATOR",
                    rule_name="Expired / Stale Threat-Intelligence Match (Informational)",
                    category="threat_intel",
                    points_awarded=0,
                    max_points=0,
                    explanation=(
                        f"Simulated indicator '{indicator}' ({source}) matched local feed but EXPIRED at "
                        f"{expires_at} prior to transaction timestamp {tx_time_str} (0 points added)."
                    ),
                    evidence_refs=[indicator, tx_id],
                )
            )

    return triggered


def _build_counterfactual_summary(
    tx_row: sqlite3.Row,
    user_row: sqlite3.Row,
    method: str,
    final_score: int,
    threshold: int,
    triggered_rules: List[TriggeredRuleSchema],
) -> str:
    """Generate a deterministic Counterfactual Explanation (Idea 5)."""
    amount = float(tx_row["amount"])
    profile_type = user_row["profile_type"]
    exp_model = user_row["expenditure_model"]
    max_tx = float(user_row["typical_max_tx_amount"])

    positive_rules = [r for r in triggered_rules if r.points_awarded > 0]

    if final_score < threshold:
        if not positive_rules:
            return (
                f"Score ({final_score}/100) is well below the user's alert threshold ({threshold}). "
                f"Amount (₹{amount:,.2f}) fits the '{profile_type}' ({exp_model}, max ₹{max_tx:,.0f}) profile "
                f"on a known device and established supply-chain counterparty."
            )
        top_rule = max(positive_rules, key=lambda r: r.points_awarded)
        return (
            f"Score ({final_score}/100) remains below the user's alert threshold ({threshold}) despite "
            f"'{top_rule.rule_name}' (+{top_rule.points_awarded} pts), because surrounding profile and session context matched baseline expectations."
        )

    # When score >= threshold, compute which top rules pushed it across the threshold
    sorted_rules = sorted(positive_rules, key=lambda r: r.points_awarded, reverse=True)
    needed_reduction = (final_score - threshold) + 1
    removed_pts = 0
    pivotal_names: List[str] = []
    for r in sorted_rules:
        pivotal_names.append(f"{r.rule_name} (+{r.points_awarded})")
        removed_pts += r.points_awarded
        if removed_pts >= needed_reduction:
            break

    hypothetical_score = max(0, final_score - removed_pts)
    return (
        f"Score ({final_score}/100) crossed the user's alert threshold ({threshold}) primarily due to "
        f"{', '.join(pivotal_names)}. Counterfactual: Had this ₹{amount:,.2f} transfer occurred without "
        f"those factors (e.g., on a registered device to an established, unmodified '{exp_model}' counterparty), "
        f"the {method} score would have been {hypothetical_score}/100 (No Alert)."
    )


def _build_score_response(
    transaction_id: str,
    user_id: str,
    method: str,
    tx_row: sqlite3.Row,
    user_row: sqlite3.Row,
    threshold: int,
    rules: List[TriggeredRuleSchema],
) -> RiskScoreResponseSchema:
    raw_sum = sum(r.points_awarded for r in rules)
    capped_score = min(100, max(0, raw_sum))
    counterfactual = _build_counterfactual_summary(
        tx_row=tx_row,
        user_row=user_row,
        method=method,
        final_score=capped_score,
        threshold=threshold,
        triggered_rules=rules,
    )
    return RiskScoreResponseSchema(
        transaction_id=transaction_id,
        user_id=user_id,
        method=method,
        raw_points_sum=raw_sum,
        risk_score=capped_score,
        risk_band=_score_to_band(capped_score),
        user_alert_threshold=threshold,
        exceeds_user_threshold=(capped_score >= threshold),
        score_interpretation=SCORE_INTERPRETATION_TEXT,
        triggered_rules=rules,
        counterfactual_summary=counterfactual,
    )


def score_transaction(
    transaction_id: str,
    method: str = "contextual",
    db_path: Optional[Path] = None,
) -> Optional[RiskScoreResponseSchema]:
    """Calculate an explainable 0-100 risk score for `transaction_id` using `method`.

    Returns `None` if `transaction_id` does not exist.
    Raises `ValueError` if `method` is not one of `baseline`, `contextual`, or `contextual_ti`.
    """
    if method not in VALID_SCORING_METHODS:
        raise ValueError(
            f"Invalid scoring method '{method}'. Expected one of {VALID_SCORING_METHODS}."
        )

    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?;",
            (transaction_id,),
        ).fetchone()
        if tx_row is None:
            return None

        user_id = tx_row["user_id"]
        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        if user_row is None:
            return None
        pref_row = conn.execute(
            "SELECT risk_threshold FROM user_preferences WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        threshold = int(pref_row["risk_threshold"]) if pref_row else 60

        if method == "baseline":
            rules = _evaluate_baseline_rules(conn, tx_row)
        elif method == "contextual":
            rules = _evaluate_contextual_rules(conn, tx_row, user_row)
        else:
            rules = _evaluate_contextual_rules(conn, tx_row, user_row) + _evaluate_threat_intel_rules(
                conn, tx_row
            )

    return _build_score_response(
        transaction_id=transaction_id,
        user_id=user_id,
        method=method,
        tx_row=tx_row,
        user_row=user_row,
        threshold=threshold,
        rules=rules,
    )


def compare_transaction_scores(
    transaction_id: str,
    db_path: Optional[Path] = None,
) -> Optional[RiskComparisonResponseSchema]:
    """Run all three scoring methods on `transaction_id` in a single pass and return a side-by-side diff."""
    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?;",
            (transaction_id,),
        ).fetchone()
        if tx_row is None:
            return None

        user_id = tx_row["user_id"]
        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        if user_row is None:
            return None
        pref_row = conn.execute(
            "SELECT risk_threshold FROM user_preferences WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        threshold = int(pref_row["risk_threshold"]) if pref_row else 60

        base_rules = _evaluate_baseline_rules(conn, tx_row)
        ctx_rules = _evaluate_contextual_rules(conn, tx_row, user_row)
        ti_only_rules = _evaluate_threat_intel_rules(conn, tx_row)
        ti_rules = ctx_rules + ti_only_rules

    base_res = _build_score_response(
        transaction_id, user_id, "baseline", tx_row, user_row, threshold, base_rules
    )
    ctx_res = _build_score_response(
        transaction_id, user_id, "contextual", tx_row, user_row, threshold, ctx_rules
    )
    ti_res = _build_score_response(
        transaction_id, user_id, "contextual_ti", tx_row, user_row, threshold, ti_rules
    )

    delta_ctx = ctx_res.risk_score - base_res.risk_score
    delta_ti = ti_res.risk_score - ctx_res.risk_score

    if delta_ctx < 0:
        narrative = (
            f"Contextual scoring LOWERED the score by {abs(delta_ctx)} points "
            f"({base_res.risk_score} -> {ctx_res.risk_score}) because the transaction fits "
            f"'{user_row['display_name']}' ({user_row['expenditure_model']}) and its established supply-chain profile, "
            f"preventing a baseline false positive."
        )
    elif delta_ctx > 0 or delta_ti > 0:
        narrative = (
            f"Contextual & Threat-Intel enrichment RAISED the score from {base_res.risk_score} (Baseline) "
            f"to {ctx_res.risk_score} (Contextual) and {ti_res.risk_score} (Contextual+TI) by correlating "
            f"profile, counterparty/BEC, structuring, and session forensics."
        )
    else:
        narrative = (
            f"All three scoring methods agreed on a score of {ti_res.risk_score}/100 for this routine transaction."
        )

    return RiskComparisonResponseSchema(
        transaction_id=transaction_id,
        user_id=user_id,
        user_display_name=user_row["display_name"],
        user_profile_type=user_row["profile_type"],
        user_expenditure_model=user_row["expenditure_model"],
        amount=float(tx_row["amount"]),
        user_alert_threshold=threshold,
        baseline=base_res,
        contextual=ctx_res,
        contextual_ti=ti_res,
        delta_contextual_vs_baseline=delta_ctx,
        delta_ti_vs_contextual=delta_ti,
        context_added_rules=ctx_rules,
        ti_added_rules=ti_only_rules,
        comparison_narrative=narrative,
    )
