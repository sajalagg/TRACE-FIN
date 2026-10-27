from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from app.core.database import get_connection
from app.core.policy import TX_STATUS_COMPLETED, evaluate_transfer_policy
from app.core.security import hash_password
from app.schemas.api_schemas import (
    AuthenticationEventSchema,
    BeneficiaryEventCreateSchema,
    BeneficiaryEventSchema,
    DeviceEventSchema,
    TransactionCreateResponseSchema,
    TransactionCreateSchema,
    TransactionDetailResponseSchema,
    TransactionListResponseSchema,
    TransactionSummarySchema,
    UserCreateSchema,
    UserProfileSchema,
)
from app.services.alert_policy import evaluate_alert_decision, validate_timezone_iana
from app.services.scoring import compare_transaction_scores


def _row_to_user_profile(row: sqlite3.Row) -> UserProfileSchema:
    """Convert a SQLite `users` row into a `UserProfileSchema`."""
    keys = row.keys()
    return UserProfileSchema(
        user_id=row["user_id"],
        username=row["username"] if "username" in keys else None,
        role=row["role"] if "role" in keys and row["role"] else "customer",
        simulated_balance=float(row["simulated_balance"]) if "simulated_balance" in keys else 10000.0,
        display_name=row["display_name"],
        account_category=row["account_category"],
        profile_type=row["profile_type"],
        industry_sector=row["industry_sector"],
        expenditure_model=row["expenditure_model"],
        net_worth_band=row["net_worth_band"],
        estimated_net_worth=float(row["estimated_net_worth"]),
        declared_monthly_turnover=float(row["declared_monthly_turnover"]),
        typical_tx_amount=float(row["typical_tx_amount"]),
        typical_max_tx_amount=float(row["typical_max_tx_amount"]),
        expected_monthly_tx_count=int(row["expected_monthly_tx_count"]),
        operating_hours_utc=row["operating_hours_utc"],
        home_geo_location=row["home_geo_location"],
        home_ip_prefix=(
            row["home_ip_prefix"]
            if "home_ip_prefix" in keys and row["home_ip_prefix"]
            else "103.21.244."
        ),
        created_at_utc=row["created_at_utc"],
    )


def _row_to_tx_summary(row: sqlite3.Row) -> TransactionSummarySchema:
    """Convert a joined `transactions` + `users` row into a `TransactionSummarySchema`."""
    keys = row.keys()
    return TransactionSummarySchema(
        transaction_id=row["transaction_id"],
        user_id=row["user_id"],
        user_display_name=row["display_name"],
        user_profile_type=row["profile_type"],
        user_expenditure_model=row["expenditure_model"],
        amount=float(row["amount"]),
        currency=row["currency"],
        timestamp_utc=row["timestamp_utc"],
        beneficiary_id=row["beneficiary_id"],
        beneficiary_name=row["beneficiary_name"],
        beneficiary_category=row["beneficiary_category"],
        beneficiary_industry=row["beneficiary_industry"],
        device_id=row["device_id"],
        ip_address=row["ip_address"],
        geo_location=row["geo_location"],
        status=row["status"] if "status" in keys and row["status"] else "COMPLETED",
        decision_reason=(
            row["decision_reason"]
            if "decision_reason" in keys and row["decision_reason"]
            else "Approved under baseline simulation policy."
        ),
        notes=row["notes"] if "notes" in keys else None,
        balance_deducted=bool(row["balance_deducted"]) if "balance_deducted" in keys else True,
        session_id=row["session_id"] if "session_id" in keys else None,
    )


def list_users(
    expenditure_model: Optional[str] = None,
    profile_type: Optional[str] = None,
    role: str = "customer",
    db_path: Optional[Path] = None,
) -> List[UserProfileSchema]:
    """Return synthetic user profiles, optionally filtered by expenditure model or profile type."""
    clauses: List[str] = ["role = ?"]
    params: List[object] = [role]

    if expenditure_model:
        clauses.append("expenditure_model = ?")
        params.append(expenditure_model)
    if profile_type:
        clauses.append("profile_type = ?")
        params.append(profile_type)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM users {where_sql} ORDER BY user_id ASC;"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_user_profile(r) for r in rows]


def get_user_by_id(
    user_id: str,
    db_path: Optional[Path] = None,
) -> Optional[UserProfileSchema]:
    """Retrieve a single user profile by `user_id`, or `None` if not found."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_user_profile(row)


def list_transactions(
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[str] = None,
    profile_type: Optional[str] = None,
    expenditure_model: Optional[str] = None,
    beneficiary_category: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> TransactionListResponseSchema:
    """List synthetic transactions with pagination and optional profile/counterparty filters."""
    clauses: List[str] = []
    params: List[object] = []

    if user_id:
        clauses.append("t.user_id = ?")
        params.append(user_id)
    if profile_type:
        clauses.append("u.profile_type = ?")
        params.append(profile_type)
    if expenditure_model:
        clauses.append("u.expenditure_model = ?")
        params.append(expenditure_model)
    if beneficiary_category:
        clauses.append("t.beneficiary_category = ?")
        params.append(beneficiary_category)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    count_query = f"""
        SELECT COUNT(*) AS cnt
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        {where_sql};
    """

    items_query = f"""
        SELECT t.*, u.display_name, u.profile_type, u.expenditure_model
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        {where_sql}
        ORDER BY t.timestamp_utc DESC, t.transaction_id ASC
        LIMIT ? OFFSET ?;
    """

    with get_connection(db_path) as conn:
        total_row = conn.execute(count_query, params).fetchone()
        total_matching = int(total_row["cnt"]) if total_row else 0

        item_rows = conn.execute(items_query, [*params, limit, offset]).fetchall()

    return TransactionListResponseSchema(
        total_matching=total_matching,
        limit=limit,
        offset=offset,
        items=[_row_to_tx_summary(r) for r in item_rows],
    )


def get_transaction_detail(
    transaction_id: str,
    db_path: Optional[Path] = None,
) -> Optional[TransactionDetailResponseSchema]:
    """Retrieve one transaction along with its sender profile and linked context events.

    Returns `None` if `transaction_id` does not exist.
    """
    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            """
            SELECT t.*, u.display_name, u.profile_type, u.expenditure_model
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.transaction_id = ?;
            """,
            (transaction_id,),
        ).fetchone()

        if tx_row is None:
            return None

        user_id = tx_row["user_id"]
        tx_time = tx_row["timestamp_utc"]

        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()

        # Retrieve up to 10 most recent authentication events at or before the transaction timestamp
        auth_rows = conn.execute(
            """
            SELECT *
            FROM authentication_events
            WHERE user_id = ? AND timestamp_utc <= ?
            ORDER BY timestamp_utc DESC, event_id DESC
            LIMIT 10;
            """,
            (user_id, tx_time),
        ).fetchall()

        # Retrieve device events for this user at or before the transaction timestamp
        device_rows = conn.execute(
            """
            SELECT *
            FROM device_events
            WHERE user_id = ? AND timestamp_utc <= ?
            ORDER BY timestamp_utc ASC, event_id ASC;
            """,
            (user_id, tx_time),
        ).fetchall()

        # Retrieve beneficiary events for this user at or before the transaction timestamp
        ben_rows = conn.execute(
            """
            SELECT *
            FROM beneficiary_events
            WHERE user_id = ? AND timestamp_utc <= ?
            ORDER BY timestamp_utc ASC, event_id ASC;
            """,
            (user_id, tx_time),
        ).fetchall()

    auth_events = [
        AuthenticationEventSchema(
            event_id=r["event_id"],
            user_id=r["user_id"],
            timestamp_utc=r["timestamp_utc"],
            event_type=r["event_type"],
            ip_address=r["ip_address"],
            geo_location=r["geo_location"],
            device_id=r["device_id"],
            is_success=bool(r["is_success"]),
        )
        for r in reversed(auth_rows)
    ]

    device_events = [
        DeviceEventSchema(
            event_id=r["event_id"],
            user_id=r["user_id"],
            timestamp_utc=r["timestamp_utc"],
            device_id=r["device_id"],
            device_label=r["device_label"],
            event_type=r["event_type"],
            known_status=r["known_status"],
        )
        for r in device_rows
    ]

    beneficiary_events = [
        BeneficiaryEventSchema(
            event_id=r["event_id"],
            user_id=r["user_id"],
            beneficiary_id=r["beneficiary_id"],
            beneficiary_name=r["beneficiary_name"],
            beneficiary_category=r["beneficiary_category"],
            beneficiary_industry=r["beneficiary_industry"],
            timestamp_utc=r["timestamp_utc"],
            event_type=r["event_type"],
            notes=r["notes"],
        )
        for r in ben_rows
    ]

    return TransactionDetailResponseSchema(
        transaction=_row_to_tx_summary(tx_row),
        user_profile=_row_to_user_profile(user_row),
        recent_authentication_events=auth_events,
        device_events=device_events,
        beneficiary_events=beneficiary_events,
    )


def create_user_profile(
    payload: UserCreateSchema,
    db_path: Optional[Path] = None,
) -> UserProfileSchema:
    """Create a new custom user profile, default alert preferences, and baseline registered device."""
    validate_timezone_iana(payload.timezone_iana)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        if payload.user_id:
            existing = conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?;",
                (payload.user_id,),
            ).fetchone()
            if existing is not None:
                raise ValueError(f"User ID '{payload.user_id}' already exists.")
            user_id = payload.user_id
        else:
            cnt = int(
                conn.execute(
                    "SELECT COUNT(*) AS cnt FROM users WHERE user_id LIKE 'USR-%';"
                ).fetchone()["cnt"]
            )
            user_id = f"USR-{cnt + 1:03d}"
            while conn.execute("SELECT 1 FROM users WHERE user_id = ?;", (user_id,)).fetchone():
                cnt += 1
                user_id = f"USR-{cnt + 1:03d}"

        username_val = (payload.username or user_id.lower()).strip().lower()
        existing_uname = conn.execute(
            "SELECT user_id FROM users WHERE LOWER(username) = ?;",
            (username_val,),
        ).fetchone()
        if existing_uname is not None:
            raise ValueError(f"Username '{username_val}' is already registered.")

        pw_hash = hash_password(payload.password or "DemoUser@123")
        if payload.simulated_balance != 25000.0:
            sim_bal = round(float(payload.simulated_balance), 2)
        else:
            sim_bal = round(max(25000.0, float(payload.declared_monthly_turnover) * 1.5), 2)

        conn.execute(
            """
            INSERT INTO users (
                user_id, username, password_hash, role, simulated_balance,
                display_name, account_category, profile_type,
                industry_sector, expenditure_model, net_worth_band,
                estimated_net_worth, declared_monthly_turnover,
                typical_tx_amount, typical_max_tx_amount,
                expected_monthly_tx_count, operating_hours_utc,
                home_geo_location, home_ip_prefix, created_at_utc
            ) VALUES (?, ?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '103.21.244.', ?);
            """,
            (
                user_id,
                username_val,
                pw_hash,
                sim_bal,
                payload.display_name,
                payload.account_category,
                payload.profile_type,
                payload.industry_sector,
                payload.expenditure_model,
                payload.net_worth_band,
                payload.estimated_net_worth,
                payload.declared_monthly_turnover,
                payload.typical_tx_amount,
                payload.typical_max_tx_amount,
                payload.expected_monthly_tx_count,
                payload.operating_hours_utc,
                payload.home_geo_location,
                now_utc,
            ),
        )

        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, risk_threshold, critical_bypass_threshold,
                timezone_iana, quiet_hours_enabled, quiet_hours_start,
                quiet_hours_end, updated_at_utc
            ) VALUES (?, ?, 85, ?, 1, '22:00', '07:00', ?);
            """,
            (user_id, payload.risk_threshold, payload.timezone_iana, now_utc),
        )

        # Register a default known device so normal transactions for this user have a baseline device
        dev_cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM device_events;").fetchone()["cnt"])
        dev_ev_id = f"DEV-EVT-{dev_cnt + 1:04d}"
        default_dev_id = f"DEV-{user_id}-PRIMARY"
        conn.execute(
            """
            INSERT INTO device_events (
                event_id, user_id, timestamp_utc, device_id,
                device_label, event_type, known_status
            ) VALUES (?, ?, ?, ?, 'Primary Registered Device', 'device_registered', 'known');
            """,
            (dev_ev_id, user_id, "2026-01-01T08:00:00Z", default_dev_id),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,)).fetchone()
    return _row_to_user_profile(row)


def list_user_beneficiaries(
    user_id: str,
    db_path: Optional[Path] = None,
) -> Optional[List[BeneficiaryEventSchema]]:
    """Return all beneficiary events for `user_id`, or `None` if user does not exist."""
    with get_connection(db_path) as conn:
        u_row = conn.execute("SELECT user_id FROM users WHERE user_id = ?;", (user_id,)).fetchone()
        if u_row is None:
            return None
        rows = conn.execute(
            """
            SELECT * FROM beneficiary_events
            WHERE user_id = ?
            ORDER BY timestamp_utc DESC, event_id DESC;
            """,
            (user_id,),
        ).fetchall()

    return [
        BeneficiaryEventSchema(
            event_id=r["event_id"],
            user_id=r["user_id"],
            beneficiary_id=r["beneficiary_id"],
            beneficiary_name=r["beneficiary_name"],
            beneficiary_category=r["beneficiary_category"],
            beneficiary_industry=r["beneficiary_industry"],
            timestamp_utc=r["timestamp_utc"],
            event_type=r["event_type"],
            notes=r["notes"],
        )
        for r in rows
    ]


def create_beneficiary_event(
    payload: BeneficiaryEventCreateSchema,
    db_path: Optional[Path] = None,
) -> Optional[BeneficiaryEventSchema]:
    """Create a beneficiary event ('beneficiary_added', 'beneficiary_verified', or 'beneficiary_bank_updated')."""
    ts_str = payload.timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Validate timestamp format
    try:
        datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(
            f"Invalid timestamp_utc '{ts_str}'. Expected 'YYYY-MM-DDTHH:MM:SSZ'."
        ) from exc

    with get_connection(db_path) as conn:
        u_row = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?;",
            (payload.user_id,),
        ).fetchone()
        if u_row is None:
            return None

        ev_cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM beneficiary_events;").fetchone()["cnt"])
        event_id = f"BEN-EVT-{ev_cnt + 1:04d}"
        ben_id = payload.beneficiary_id or f"BEN-CUSTOM-{ev_cnt + 1:03d}"

        conn.execute(
            """
            INSERT INTO beneficiary_events (
                event_id, user_id, beneficiary_id, beneficiary_name,
                beneficiary_category, beneficiary_industry,
                timestamp_utc, event_type, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event_id,
                payload.user_id,
                ben_id,
                payload.beneficiary_name,
                payload.beneficiary_category,
                payload.beneficiary_industry,
                ts_str,
                payload.event_type,
                payload.notes,
            ),
        )

        # Keep `beneficiaries` table synchronized with beneficiary events
        acct_ref = f"SYNTH-REF-{ben_id}"
        is_ver = 1 if payload.event_type == "beneficiary_verified" else 0
        conn.execute(
            """
            INSERT INTO beneficiaries (
                beneficiary_id, user_id, display_name, account_reference,
                beneficiary_category, beneficiary_industry, status,
                is_verified, created_at_utc, updated_at_utc, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
            ON CONFLICT(user_id, beneficiary_id) DO UPDATE SET
                display_name = excluded.display_name,
                beneficiary_category = excluded.beneficiary_category,
                beneficiary_industry = excluded.beneficiary_industry,
                is_verified = CASE WHEN excluded.is_verified = 1 THEN 1 ELSE beneficiaries.is_verified END,
                updated_at_utc = excluded.updated_at_utc,
                notes = COALESCE(excluded.notes, beneficiaries.notes);
            """,
            (
                ben_id,
                payload.user_id,
                payload.beneficiary_name,
                acct_ref,
                payload.beneficiary_category,
                payload.beneficiary_industry,
                is_ver,
                ts_str,
                ts_str,
                payload.notes,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM beneficiary_events WHERE event_id = ?;",
            (event_id,),
        ).fetchone()

    return BeneficiaryEventSchema(
        event_id=row["event_id"],
        user_id=row["user_id"],
        beneficiary_id=row["beneficiary_id"],
        beneficiary_name=row["beneficiary_name"],
        beneficiary_category=row["beneficiary_category"],
        beneficiary_industry=row["beneficiary_industry"],
        timestamp_utc=row["timestamp_utc"],
        event_type=row["event_type"],
        notes=row["notes"],
    )


def create_live_transaction(
    payload: TransactionCreateSchema,
    db_path: Optional[Path] = None,
) -> Optional[TransactionCreateResponseSchema]:
    """Create a live transaction (plus optional forensic precursor events) and return immediate risk scores."""
    ts_str = payload.timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        tx_dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(
            f"Invalid timestamp_utc '{ts_str}'. Expected 'YYYY-MM-DDTHH:MM:SSZ'."
        ) from exc

    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (payload.user_id,),
        ).fetchone()
        if user_row is None:
            return None

        uid = payload.user_id
        user_keys = user_row.keys()
        current_balance = (
            float(user_row["simulated_balance"])
            if "simulated_balance" in user_keys and user_row["simulated_balance"] is not None
            else 25000.0
        )
        req_amount = round(float(payload.amount), 2)
        if req_amount > current_balance:
            raise ValueError(
                f"Insufficient simulated balance: requested ${req_amount:,.2f} exceeds available balance ${current_balance:,.2f}."
            )

        home_geo = user_row["home_geo_location"]
        tx_geo = payload.geo_location or home_geo

        sess_row = conn.execute(
            """
            SELECT session_id FROM user_sessions
            WHERE user_id = ? AND is_revoked = 0
            ORDER BY created_at_utc DESC LIMIT 1;
            """,
            (uid,),
        ).fetchone()
        linked_session_id = str(sess_row["session_id"]) if sess_row is not None else None

        # Determine device_id
        known_dev_row = conn.execute(
            """
            SELECT device_id FROM device_events
            WHERE user_id = ? AND known_status = 'known'
            ORDER BY timestamp_utc ASC LIMIT 1;
            """,
            (uid,),
        ).fetchone()
        default_known_dev = (
            str(known_dev_row["device_id"]) if known_dev_row else f"DEV-{uid}-PRIMARY"
        )

        tx_cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM transactions;").fetchone()["cnt"])
        tx_id = f"TX-{tx_cnt + 1:04d}"
        while conn.execute("SELECT 1 FROM transactions WHERE transaction_id = ?;", (tx_id,)).fetchone():
            tx_cnt += 1
            tx_id = f"TX-{tx_cnt + 1:04d}"

        if payload.simulate_unseen_device:
            dev_id = payload.device_id or f"DEV-UNSEEN-{tx_cnt + 1:03d}"
            dev_ev_cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM device_events;").fetchone()["cnt"])
            conn.execute(
                """
                INSERT INTO device_events (
                    event_id, user_id, timestamp_utc, device_id,
                    device_label, event_type, known_status
                ) VALUES (?, ?, ?, ?, 'Unrecognized Live Demo Device', 'new_device_detected', 'new');
                """,
                (
                    f"DEV-EVT-{dev_ev_cnt + 1:04d}",
                    uid,
                    _fmt(tx_dt - timedelta(minutes=5)),
                    dev_id,
                ),
            )
        else:
            dev_id = payload.device_id or default_known_dev

        auth_cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM authentication_events;").fetchone()["cnt"])

        # 1. Optional Impossible Travel precursor (login at home 18 mins before foreign transaction)
        if payload.simulate_impossible_travel_from_home:
            auth_cnt += 1
            conn.execute(
                """
                INSERT INTO authentication_events (
                    event_id, user_id, timestamp_utc, event_type,
                    ip_address, geo_location, device_id, is_success
                ) VALUES (?, ?, ?, 'login_success', '103.21.244.10', ?, ?, 1);
                """,
                (
                    f"AUTH-EVT-{auth_cnt:04d}",
                    uid,
                    _fmt(tx_dt - timedelta(minutes=18)),
                    home_geo,
                    default_known_dev,
                ),
            )

        # 2. Optional Failed Logins precursor
        for f_i in range(payload.simulate_failed_logins):
            auth_cnt += 1
            conn.execute(
                """
                INSERT INTO authentication_events (
                    event_id, user_id, timestamp_utc, event_type,
                    ip_address, geo_location, device_id, is_success
                ) VALUES (?, ?, ?, 'login_failure', ?, ?, ?, 0);
                """,
                (
                    f"AUTH-EVT-{auth_cnt:04d}",
                    uid,
                    _fmt(tx_dt - timedelta(minutes=10 + f_i)),
                    payload.ip_address,
                    tx_geo,
                    dev_id,
                ),
            )

        # 3. Record successful session login 6 minutes prior to transaction (unless a real login session already logged this within 60m)
        recent_login_exists = conn.execute(
            """
            SELECT 1 FROM authentication_events
            WHERE user_id = ?
              AND event_type = 'login_success'
              AND ip_address = ?
              AND device_id = ?
              AND timestamp_utc >= ?
              AND timestamp_utc <= ?
            LIMIT 1;
            """,
            (
                uid,
                payload.ip_address,
                dev_id,
                _fmt(tx_dt - timedelta(minutes=60)),
                ts_str,
            ),
        ).fetchone()

        if recent_login_exists is None or payload.simulate_impossible_travel_from_home or payload.simulate_failed_logins > 0:
            auth_cnt += 1
            conn.execute(
                """
                INSERT INTO authentication_events (
                    event_id, user_id, timestamp_utc, event_type,
                    ip_address, geo_location, device_id, is_success
                ) VALUES (?, ?, ?, 'login_success', ?, ?, ?, 1);
                """,
                (
                    f"AUTH-EVT-{auth_cnt:04d}",
                    uid,
                    _fmt(tx_dt - timedelta(minutes=6)),
                    payload.ip_address,
                    tx_geo,
                    dev_id,
                ),
            )

        # 4. Optional Rapid New Beneficiary or Vendor BEC Bank Modification
        ben_ev_cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM beneficiary_events;").fetchone()["cnt"])
        if payload.simulate_rapid_new_beneficiary:
            ben_ev_cnt += 1
            conn.execute(
                """
                INSERT INTO beneficiary_events (
                    event_id, user_id, beneficiary_id, beneficiary_name,
                    beneficiary_category, beneficiary_industry,
                    timestamp_utc, event_type, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'beneficiary_added', 'Added 4 mins prior to live demo transaction.');
                """,
                (
                    f"BEN-EVT-{ben_ev_cnt:04d}",
                    uid,
                    payload.beneficiary_id,
                    payload.beneficiary_name,
                    payload.beneficiary_category,
                    payload.beneficiary_industry,
                    _fmt(tx_dt - timedelta(minutes=4)),
                ),
            )

        if payload.simulate_vendor_bec_bank_update:
            ben_ev_cnt += 1
            conn.execute(
                """
                INSERT INTO beneficiary_events (
                    event_id, user_id, beneficiary_id, beneficiary_name,
                    beneficiary_category, beneficiary_industry,
                    timestamp_utc, event_type, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'beneficiary_bank_updated', 'Bank account/IBAN modified 12 mins prior to live demo wire.');
                """,
                (
                    f"BEN-EVT-{ben_ev_cnt:04d}",
                    uid,
                    payload.beneficiary_id,
                    payload.beneficiary_name,
                    payload.beneficiary_category,
                    payload.beneficiary_industry,
                    _fmt(tx_dt - timedelta(minutes=12)),
                ),
            )

        is_susp_flag = (
            1
            if (
                payload.simulate_failed_logins > 0
                or payload.simulate_unseen_device
                or payload.simulate_impossible_travel_from_home
                or payload.simulate_rapid_new_beneficiary
                or payload.simulate_vendor_bec_bank_update
            )
            else 0
        )

        conn.execute(
            """
            INSERT INTO transactions (
                transaction_id, user_id, amount, currency, timestamp_utc,
                beneficiary_id, beneficiary_name, beneficiary_category,
                beneficiary_industry, device_id, ip_address, geo_location,
                is_suspicious, scenario_label, status, decision_reason,
                balance_deducted, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'live_custom_demo', 'COMPLETED', 'Pending policy evaluation.', 0, ?);
            """,
            (
                tx_id,
                uid,
                req_amount,
                payload.currency,
                ts_str,
                payload.beneficiary_id,
                payload.beneficiary_name,
                payload.beneficiary_category,
                payload.beneficiary_industry,
                dev_id,
                payload.ip_address,
                tx_geo,
                is_susp_flag,
                linked_session_id,
            ),
        )
        conn.commit()

    comparison = compare_transaction_scores(transaction_id=tx_id, db_path=db_path)
    alert_dec = evaluate_alert_decision(
        transaction_id=tx_id,
        method="contextual_ti",
        db_path=db_path,
    )
    assert comparison is not None and alert_dec is not None

    policy = evaluate_transfer_policy(
        risk_score=comparison.contextual_ti.risk_score,
        user_alert_threshold=comparison.user_alert_threshold,
    )

    with get_connection(db_path) as conn:
        if policy.resulting_status == TX_STATUS_COMPLETED:
            conn.execute(
                """
                UPDATE users
                SET simulated_balance = ROUND(MAX(0.0, simulated_balance - ?), 2)
                WHERE user_id = ?;
                """,
                (req_amount, uid),
            )
            conn.execute(
                """
                UPDATE transactions
                SET status = ?,
                    decision_reason = ?,
                    balance_deducted = 1
                WHERE transaction_id = ?;
                """,
                (policy.resulting_status, policy.plain_language_summary, tx_id),
            )
        else:
            conn.execute(
                """
                UPDATE transactions
                SET status = ?,
                    decision_reason = ?,
                    balance_deducted = 0
                WHERE transaction_id = ?;
                """,
                (policy.resulting_status, policy.plain_language_summary, tx_id),
            )
            existing_ver = conn.execute(
                "SELECT request_id FROM verification_requests WHERE transaction_id = ?;",
                (tx_id,),
            ).fetchone()
            if existing_ver is None:
                ver_cnt = int(
                    conn.execute("SELECT COUNT(*) AS cnt FROM verification_requests;").fetchone()["cnt"]
                )
                req_id = f"VER-{ver_cnt + 1:04d}"
                while conn.execute(
                    "SELECT 1 FROM verification_requests WHERE request_id = ?;",
                    (req_id,),
                ).fetchone():
                    ver_cnt += 1
                    req_id = f"VER-{ver_cnt + 1:04d}"
                conn.execute(
                    """
                    INSERT INTO verification_requests (
                        request_id, transaction_id, user_id, status,
                        created_at_utc, responded_at_utc, user_response,
                        response_notes, requires_admin_release
                    ) VALUES (?, ?, ?, 'pending', ?, NULL, NULL, NULL, ?);
                    """,
                    (
                        req_id,
                        tx_id,
                        uid,
                        ts_str,
                        1 if policy.requires_admin_release else 0,
                    ),
                )
        conn.commit()

        joined_tx = conn.execute(
            """
            SELECT t.*, u.display_name, u.profile_type, u.expenditure_model
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.transaction_id = ?;
            """,
            (tx_id,),
        ).fetchone()

    tx_summary = _row_to_tx_summary(joined_tx)

    return TransactionCreateResponseSchema(
        transaction=tx_summary,
        risk_comparison=comparison,
        alert_policy_decision=alert_dec,
    )

