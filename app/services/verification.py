from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.core.database import get_connection
from app.schemas.api_schemas import (
    VerificationRequestCreateSchema,
    VerificationRequestSchema,
    VerificationRespondSchema,
)
from app.services.incidents import create_or_get_incident_for_denial


class VerificationConflictError(Exception):
    """Raised when a caller attempts to change a previously finalized verification response."""


def _row_to_verification_schema(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    created_new: bool = True,
) -> VerificationRequestSchema:
    """Convert a joined `verification_requests` + `transactions` + `users` row into a schema."""
    inc_row = conn.execute(
        """
        SELECT incident_id
        FROM incidents
        WHERE transaction_id = ?
        ORDER BY created_at_utc DESC
        LIMIT 1;
        """,
        (row["transaction_id"],),
    ).fetchone()
    linked_inc_id = str(inc_row["incident_id"]) if inc_row is not None else None

    return VerificationRequestSchema(
        request_id=row["request_id"],
        transaction_id=row["transaction_id"],
        user_id=row["user_id"],
        user_display_name=row["display_name"],
        amount=float(row["amount"]),
        currency=row["currency"],
        beneficiary_id=row["beneficiary_id"],
        beneficiary_name=row["beneficiary_name"],
        status=row["status"],
        created_at_utc=row["created_at_utc"],
        responded_at_utc=row["responded_at_utc"],
        user_response=row["user_response"],
        response_notes=row["response_notes"],
        linked_incident_id=linked_inc_id,
        created_new=created_new,
    )


def list_verification_requests(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[VerificationRequestSchema]:
    """List verification requests, optionally filtered by status or user_id."""
    clauses: List[str] = []
    params: List[object] = []

    if status:
        clauses.append("vr.status = ?")
        params.append(status)
    if user_id:
        clauses.append("vr.user_id = ?")
        params.append(user_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
        FROM verification_requests vr
        JOIN transactions t ON vr.transaction_id = t.transaction_id
        JOIN users u ON vr.user_id = u.user_id
        {where_sql}
        ORDER BY vr.created_at_utc DESC, vr.request_id DESC;
    """

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_verification_schema(conn, r, created_new=False) for r in rows]


def get_verification_request_by_id(
    request_id: str,
    db_path: Optional[Path] = None,
) -> Optional[VerificationRequestSchema]:
    """Retrieve a single verification request by ID, or `None` if not found."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
            FROM verification_requests vr
            JOIN transactions t ON vr.transaction_id = t.transaction_id
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.request_id = ?;
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_verification_schema(conn, row, created_new=False)


def create_verification_request(
    payload: VerificationRequestCreateSchema,
    db_path: Optional[Path] = None,
) -> Optional[VerificationRequestSchema]:
    """Create a pending verification request for `payload.transaction_id`.

    Idempotency / duplicate prevention: if a verification request already exists for
    this transaction, returns that existing request with `created_new = False`.
    Returns `None` if `transaction_id` does not exist.
    """
    tx_id = payload.transaction_id

    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            "SELECT transaction_id, user_id FROM transactions WHERE transaction_id = ?;",
            (tx_id,),
        ).fetchone()
        if tx_row is None:
            return None

        existing = conn.execute(
            """
            SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
            FROM verification_requests vr
            JOIN transactions t ON vr.transaction_id = t.transaction_id
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.transaction_id = ?
            ORDER BY vr.created_at_utc DESC
            LIMIT 1;
            """,
            (tx_id,),
        ).fetchone()
        if existing is not None:
            return _row_to_verification_schema(conn, existing, created_new=False)

        cnt_row = conn.execute("SELECT COUNT(*) AS cnt FROM verification_requests;").fetchone()
        next_num = int(cnt_row["cnt"]) + 1
        req_id = f"VER-{next_num:04d}"
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        conn.execute(
            """
            INSERT INTO verification_requests (
                request_id, transaction_id, user_id, status,
                created_at_utc, responded_at_utc, user_response, response_notes
            ) VALUES (?, ?, ?, 'pending', ?, NULL, NULL, NULL);
            """,
            (req_id, tx_id, tx_row["user_id"], now_utc),
        )
        conn.commit()

        new_row = conn.execute(
            """
            SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
            FROM verification_requests vr
            JOIN transactions t ON vr.transaction_id = t.transaction_id
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.request_id = ?;
            """,
            (req_id,),
        ).fetchone()
        return _row_to_verification_schema(conn, new_row, created_new=True)


def respond_to_verification_request(
    request_id: str,
    payload: VerificationRespondSchema,
    db_path: Optional[Path] = None,
) -> Optional[VerificationRequestSchema]:
    """Record a simulated user's response ('approved' or 'denied') to a verification request.

    - 'approved' -> marks status 'confirmed_legitimate' while preserving all underlying risk evidence.
    - 'denied' -> marks status 'denied_suspicious' and creates/links a forensic incident.
    - Repeated identical response -> returns current state idempotently (`created_new = False`).
    - Conflicting response on an already-answered request -> raises `VerificationConflictError`.
    """
    with get_connection(db_path) as conn:
        req_row = conn.execute(
            "SELECT * FROM verification_requests WHERE request_id = ?;",
            (request_id,),
        ).fetchone()
        if req_row is None:
            return None

        current_status = req_row["status"]
        current_response = req_row["user_response"]

        if current_status != "pending":
            if current_response == payload.user_response:
                # Idempotent repeat of the exact same response
                joined = conn.execute(
                    """
                    SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
                    FROM verification_requests vr
                    JOIN transactions t ON vr.transaction_id = t.transaction_id
                    JOIN users u ON vr.user_id = u.user_id
                    WHERE vr.request_id = ?;
                    """,
                    (request_id,),
                ).fetchone()
                return _row_to_verification_schema(conn, joined, created_new=False)

            raise VerificationConflictError(
                f"Verification request '{request_id}' has already been finalized with response "
                f"'{current_response}' (status='{current_status}') and cannot be changed to '{payload.user_response}'."
            )

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_status = (
            "confirmed_legitimate"
            if payload.user_response == "approved"
            else "denied_suspicious"
        )

        conn.execute(
            """
            UPDATE verification_requests
            SET status = ?,
                responded_at_utc = ?,
                user_response = ?,
                response_notes = ?
            WHERE request_id = ?;
            """,
            (
                new_status,
                now_utc,
                payload.user_response,
                payload.response_notes,
                request_id,
            ),
        )

        if payload.user_response == "denied":
            create_or_get_incident_for_denial(
                conn=conn,
                transaction_id=req_row["transaction_id"],
                verification_request_id=request_id,
                user_id=req_row["user_id"],
                denial_notes=payload.response_notes,
                db_path=db_path,
            )

        conn.commit()

        updated_row = conn.execute(
            """
            SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
            FROM verification_requests vr
            JOIN transactions t ON vr.transaction_id = t.transaction_id
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.request_id = ?;
            """,
            (request_id,),
        ).fetchone()
        return _row_to_verification_schema(conn, updated_row, created_new=False)
