from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from app.core.database import get_connection
from app.schemas.api_schemas import (
    AuthenticationEventSchema,
    BeneficiaryEventSchema,
    DeviceEventSchema,
    TransactionDetailResponseSchema,
    TransactionListResponseSchema,
    TransactionSummarySchema,
    UserProfileSchema,
)


def _row_to_user_profile(row: sqlite3.Row) -> UserProfileSchema:
    """Convert a SQLite `users` row into a `UserProfileSchema`."""
    return UserProfileSchema(
        user_id=row["user_id"],
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
        created_at_utc=row["created_at_utc"],
    )


def _row_to_tx_summary(row: sqlite3.Row) -> TransactionSummarySchema:
    """Convert a joined `transactions` + `users` row into a `TransactionSummarySchema`."""
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
    )


def list_users(
    expenditure_model: Optional[str] = None,
    profile_type: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[UserProfileSchema]:
    """Return synthetic user profiles, optionally filtered by expenditure model or profile type."""
    clauses: List[str] = []
    params: List[object] = []

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
