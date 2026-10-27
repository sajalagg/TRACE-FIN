from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.database import get_connection
from app.schemas.api_schemas import (
    TimelineEntrySchema,
    TransactionTimelineResponseSchema,
)

CORE_EVIDENCE_CATEGORIES = ("authentication", "device", "beneficiary", "transaction")

# Tie-breaker sort priority when two events share the exact same timestamp_utc
_CATEGORY_SORT_ORDER: Dict[str, int] = {
    "threat_intelligence": 1,
    "device": 2,
    "authentication": 3,
    "beneficiary": 4,
    "transaction": 5,
}


def _parse_utc(ts_str: str) -> datetime:
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")


def _fmt_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_transaction_timeline(
    transaction_id: str,
    db_path: Optional[Path] = None,
) -> Optional[TransactionTimelineResponseSchema]:
    """Build a unified, chronologically sorted forensic evidence timeline for `transaction_id`.

    Returns `None` if `transaction_id` does not exist.
    """
    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            """
            SELECT t.*, u.display_name, u.profile_type, u.expenditure_model,
                   u.home_geo_location, u.typical_max_tx_amount
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.transaction_id = ?;
            """,
            (transaction_id,),
        ).fetchone()

        if tx_row is None:
            return None

        user_id = tx_row["user_id"]
        tx_time_str = tx_row["timestamp_utc"]
        tx_dt = _parse_utc(tx_time_str)
        tx_dev_id = tx_row["device_id"]
        tx_ben_id = tx_row["beneficiary_id"]
        tx_ip = tx_row["ip_address"]
        tx_geo = tx_row["geo_location"]
        home_geo = tx_row["home_geo_location"]
        max_tx = float(tx_row["typical_max_tx_amount"])

        win_60m = _fmt_utc(tx_dt - timedelta(minutes=60))
        win_120m = _fmt_utc(tx_dt - timedelta(minutes=120))
        win_24h = _fmt_utc(tx_dt - timedelta(hours=24))
        win_7d = _fmt_utc(tx_dt - timedelta(days=7))

        # 1. Fetch relevant device events (for the transaction's device + any recent device events)
        dev_rows = conn.execute(
            """
            SELECT *
            FROM device_events
            WHERE user_id = ?
              AND timestamp_utc <= ?
              AND (device_id = ? OR timestamp_utc >= ?)
            ORDER BY timestamp_utc ASC, event_id ASC;
            """,
            (user_id, tx_time_str, tx_dev_id, win_7d),
        ).fetchall()

        known_devices = {
            r["device_id"] for r in dev_rows if r["known_status"] == "known"
        }

        # 2. Fetch relevant beneficiary events (onboarding record for target beneficiary + recent 24h changes)
        ben_rows = conn.execute(
            """
            SELECT *
            FROM beneficiary_events
            WHERE user_id = ?
              AND timestamp_utc <= ?
              AND (
                  (beneficiary_id = ? AND event_type = 'beneficiary_added')
                  OR timestamp_utc >= ?
              )
            ORDER BY timestamp_utc ASC, event_id ASC;
            """,
            (user_id, tx_time_str, tx_ben_id, win_24h),
        ).fetchall()

        # 3. Fetch authentication events in the last 24h (or up to 5 most recent if none in 24h)
        auth_rows = conn.execute(
            """
            SELECT *
            FROM authentication_events
            WHERE user_id = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
            ORDER BY timestamp_utc ASC, event_id ASC;
            """,
            (user_id, win_24h, tx_time_str),
        ).fetchall()
        if not auth_rows:
            auth_rows = list(
                reversed(
                    conn.execute(
                        """
                        SELECT *
                        FROM authentication_events
                        WHERE user_id = ? AND timestamp_utc <= ?
                        ORDER BY timestamp_utc DESC, event_id DESC
                        LIMIT 5;
                        """,
                        (user_id, tx_time_str),
                    ).fetchall()
                )
            )

        # 4. Fetch prior transactions in the last 24h (to surface structuring / velocity context)
        prior_tx_rows = conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE user_id = ?
              AND timestamp_utc >= ?
              AND timestamp_utc <= ?
              AND transaction_id != ?
            ORDER BY timestamp_utc ASC, transaction_id ASC;
            """,
            (user_id, win_24h, tx_time_str, transaction_id),
        ).fetchall()

        # 5. Fetch matching simulated threat-intelligence records
        ti_rows = conn.execute(
            """
            SELECT *
            FROM threat_intelligence
            WHERE indicator IN (?, ?)
            ORDER BY indicator ASC;
            """,
            (tx_ip, tx_ben_id),
        ).fetchall()

    raw_items: List[Tuple[str, int, str, TimelineEntrySchema]] = []

    # --- Convert Device Events ---
    for d in dev_rows:
        is_new = d["known_status"] == "new"
        phase = "INITIAL_ACCESS" if is_new else "NORMAL_ACTIVITY"
        interp = (
            f"Unregistered device '{d['device_id']}' detected prior to transaction; indicates potential new-device session."
            if is_new
            else f"Device '{d['device_id']}' was previously registered as a trusted baseline device."
        )
        entry = TimelineEntrySchema(
            sequence_no=0,
            timestamp_utc=d["timestamp_utc"],
            event_category="device",
            event_type=d["event_type"],
            source_table="device_events",
            source_record_id=d["event_id"],
            geo_location=None,
            ip_address=None,
            device_id=d["device_id"],
            recorded_fact=(
                f"Device record {d['event_id']}: device_id='{d['device_id']}' ({d['device_label']}), "
                f"event_type='{d['event_type']}', known_status='{d['known_status']}'."
            ),
            kill_chain_phase=phase,
            system_interpretation=interp,
        )
        raw_items.append((d["timestamp_utc"], _CATEGORY_SORT_ORDER["device"], d["event_id"], entry))

    # --- Convert Beneficiary Events ---
    for b in ben_rows:
        ts_b = b["timestamp_utc"]
        ev_type = b["event_type"]
        if ev_type == "beneficiary_bank_updated" and ts_b >= win_120m:
            phase = "PREPARATION_PERSISTENCE"
            interp = (
                f"Counterparty '{b['beneficiary_name']}' ({b['beneficiary_id']}) had its bank routing/account "
                f"modified within 120 minutes before transfer (Business Email Compromise / vendor tamper indicator)."
            )
        elif ev_type == "beneficiary_added" and ts_b >= win_60m:
            phase = "PREPARATION_PERSISTENCE"
            interp = (
                f"Counterparty '{b['beneficiary_name']}' ({b['beneficiary_id']}) was newly added within 60 minutes "
                f"prior to funds transfer."
            )
        else:
            phase = "NORMAL_ACTIVITY"
            interp = (
                f"Counterparty '{b['beneficiary_name']}' ({b['beneficiary_id']}) was onboarded during routine history."
            )

        entry = TimelineEntrySchema(
            sequence_no=0,
            timestamp_utc=ts_b,
            event_category="beneficiary",
            event_type=ev_type,
            source_table="beneficiary_events",
            source_record_id=b["event_id"],
            geo_location=None,
            ip_address=None,
            device_id=None,
            recorded_fact=(
                f"Beneficiary record {b['event_id']}: beneficiary_id='{b['beneficiary_id']}' "
                f"('{b['beneficiary_name']}', category='{b['beneficiary_category']}', "
                f"industry='{b['beneficiary_industry']}'), event_type='{ev_type}'."
            ),
            kill_chain_phase=phase,
            system_interpretation=interp,
        )
        raw_items.append((ts_b, _CATEGORY_SORT_ORDER["beneficiary"], b["event_id"], entry))

    # --- Convert Authentication Events ---
    recent_success_geos: List[str] = []
    for a in auth_rows:
        ts_a = a["timestamp_utc"]
        is_ok = bool(a["is_success"])
        a_geo = a["geo_location"]
        a_dev = a["device_id"]

        if is_ok and ts_a >= win_120m and a_geo not in recent_success_geos:
            recent_success_geos.append(a_geo)

        if not is_ok:
            phase = "RECON_BRUTE_FORCE"
            interp = (
                f"Failed authentication attempt ('{a['event_type']}') from IP {a['ip_address']} ({a_geo}); "
                f"consistent with credential stuffing or password guessing."
            )
        elif (a_dev not in known_devices) or (len(recent_success_geos) >= 2 and a_geo != home_geo):
            phase = "INITIAL_ACCESS"
            interp = (
                f"Successful login from anomalous session context (device='{a_dev}', geo='{a_geo}', "
                f"home='{home_geo}')."
            )
        else:
            phase = "NORMAL_ACTIVITY"
            interp = f"Successful login from expected device '{a_dev}' in '{a_geo}'."

        entry = TimelineEntrySchema(
            sequence_no=0,
            timestamp_utc=ts_a,
            event_category="authentication",
            event_type=a["event_type"],
            source_table="authentication_events",
            source_record_id=a["event_id"],
            geo_location=a_geo,
            ip_address=a["ip_address"],
            device_id=a_dev,
            recorded_fact=(
                f"Auth record {a['event_id']}: event_type='{a['event_type']}', is_success={is_ok}, "
                f"ip='{a['ip_address']}', geo='{a_geo}', device_id='{a_dev}'."
            ),
            kill_chain_phase=phase,
            system_interpretation=interp,
        )
        raw_items.append((ts_a, _CATEGORY_SORT_ORDER["authentication"], a["event_id"], entry))

    # --- Convert Threat-Intelligence Records (if matched) ---
    for ti in ti_rows:
        ind = ti["indicator"]
        is_active = ti["expires_at_utc"] >= tx_time_str
        phase = "INITIAL_ACCESS" if is_active else "NORMAL_ACTIVITY"
        interp = (
            f"Simulated threat-intelligence indicator '{ind}' ({ti['source_label']}) is ACTIVE at transaction time "
            f"(confidence={ti['confidence_level']}, expires={ti['expires_at_utc']})."
            if is_active
            else f"Simulated threat-intelligence indicator '{ind}' EXPIRED at {ti['expires_at_utc']} prior to transaction "
            f"({tx_time_str}); treated as stale historical telemetry."
        )
        entry = TimelineEntrySchema(
            sequence_no=0,
            timestamp_utc=ti["last_seen_utc"],
            event_category="threat_intelligence",
            event_type="demo_threat_intel_observation",
            source_table="threat_intelligence",
            source_record_id=ind,
            geo_location=None,
            ip_address=ind if ti["indicator_type"] == "ip_address" else None,
            device_id=None,
            recorded_fact=(
                f"Demo Threat-Intel record '{ind}': type='{ti['indicator_type']}', "
                f"category='{ti['threat_category']}', confidence='{ti['confidence_level']}', "
                f"last_seen='{ti['last_seen_utc']}', expires='{ti['expires_at_utc']}'."
            ),
            kill_chain_phase=phase,
            system_interpretation=interp,
        )
        raw_items.append((ti["last_seen_utc"], _CATEGORY_SORT_ORDER["threat_intelligence"], ind, entry))

    # --- Convert Prior 24h Transactions (for structuring context) ---
    total_24h_amount = float(tx_row["amount"]) + sum(float(p["amount"]) for p in prior_tx_rows)
    is_structuring_window = len(prior_tx_rows) >= 1 and (total_24h_amount / max_tx) >= 1.4

    for p in prior_tx_rows:
        p_id = p["transaction_id"]
        p_amt = float(p["amount"])
        phase = "EXFILTRATION_EXECUTION" if is_structuring_window else "NORMAL_ACTIVITY"
        interp = (
            f"Preceding transfer (₹{p_amt:,.2f} to {p['beneficiary_id']}) within 24h window contributing to "
            f"₹{total_24h_amount:,.2f} cumulative outflow."
            if is_structuring_window
            else f"Prior routine transaction (₹{p_amt:,.2f}) within 24h window."
        )
        entry = TimelineEntrySchema(
            sequence_no=0,
            timestamp_utc=p["timestamp_utc"],
            event_category="transaction",
            event_type="prior_transaction_in_24h",
            source_table="transactions",
            source_record_id=p_id,
            geo_location=p["geo_location"],
            ip_address=p["ip_address"],
            device_id=p["device_id"],
            recorded_fact=(
                f"Prior Transaction {p_id}: amount=₹{p_amt:,.2f} {p['currency']} to "
                f"{p['beneficiary_id']} ('{p['beneficiary_name']}') from device '{p['device_id']}'."
            ),
            kill_chain_phase=phase,
            system_interpretation=interp,
        )
        raw_items.append((p["timestamp_utc"], _CATEGORY_SORT_ORDER["transaction"], p_id, entry))

    # --- Convert Target Transaction ---
    has_attack_precursors = any(
        item[3].kill_chain_phase in ("RECON_BRUTE_FORCE", "INITIAL_ACCESS", "PREPARATION_PERSISTENCE")
        for item in raw_items
    )
    tx_amt = float(tx_row["amount"])
    if has_attack_precursors or is_structuring_window or tx_amt > max_tx:
        tx_phase = "EXFILTRATION_EXECUTION"
        tx_interp = (
            f"Target transaction (₹{tx_amt:,.2f} to '{tx_row['beneficiary_name']}') executed following "
            f"anomalous precursor events or profile-limit breach."
        )
    else:
        tx_phase = "NORMAL_ACTIVITY"
        tx_interp = (
            f"Target transaction (₹{tx_amt:,.2f} to '{tx_row['beneficiary_name']}') aligns with "
            f"'{tx_row['expenditure_model']}' profile and baseline session history."
        )

    target_entry = TimelineEntrySchema(
        sequence_no=0,
        timestamp_utc=tx_time_str,
        event_category="transaction",
        event_type="target_transaction_initiated",
        source_table="transactions",
        source_record_id=transaction_id,
        geo_location=tx_geo,
        ip_address=tx_ip,
        device_id=tx_dev_id,
        recorded_fact=(
            f"Target Transaction {transaction_id}: amount=₹{tx_amt:,.2f} {tx_row['currency']} to "
            f"beneficiary '{tx_ben_id}' ('{tx_row['beneficiary_name']}', category='{tx_row['beneficiary_category']}', "
            f"industry='{tx_row['beneficiary_industry']}') from device '{tx_dev_id}', IP '{tx_ip}' ({tx_geo})."
        ),
        kill_chain_phase=tx_phase,
        system_interpretation=tx_interp,
    )
    raw_items.append((tx_time_str, _CATEGORY_SORT_ORDER["transaction"] + 1, transaction_id, target_entry))

    # Sort chronologically by timestamp_utc, then category priority, then record ID
    raw_items.sort(key=lambda item: (item[0], item[1], item[2]))

    sorted_timeline: List[TimelineEntrySchema] = []
    observed_phases: List[str] = []
    present_cats_set = set()

    for idx, (_, _, _, entry) in enumerate(raw_items, start=1):
        entry.sequence_no = idx
        sorted_timeline.append(entry)
        present_cats_set.add(entry.event_category)
        if entry.kill_chain_phase not in observed_phases:
            observed_phases.append(entry.kill_chain_phase)

    present_categories = [c for c in CORE_EVIDENCE_CATEGORIES if c in present_cats_set]
    if "threat_intelligence" in present_cats_set:
        present_categories.append("threat_intelligence")
    missing_categories = [c for c in CORE_EVIDENCE_CATEGORIES if c not in present_cats_set]

    return TransactionTimelineResponseSchema(
        transaction_id=transaction_id,
        user_id=user_id,
        user_display_name=tx_row["display_name"],
        user_profile_type=tx_row["profile_type"],
        user_expenditure_model=tx_row["expenditure_model"],
        target_timestamp_utc=tx_time_str,
        total_events=len(sorted_timeline),
        present_categories=present_categories,
        missing_categories=missing_categories,
        kill_chain_phases_observed=observed_phases,
        timeline=sorted_timeline,
    )
