from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.core.database import get_connection
from app.schemas.api_schemas import (
    AdminDecisionResponseSchema,
    AdminTransactionDecisionSchema,
    VerificationRequestCreateSchema,
    VerificationRequestSchema,
    VerificationRespondSchema,
)
from app.services.incidents import create_or_get_incident_for_denial
from app.services.transactions import _row_to_tx_summary, _row_to_user_profile


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

    keys = row.keys()
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
        requires_admin_release=bool(row["requires_admin_release"]) if "requires_admin_release" in keys else False,
        admin_decision=row["admin_decision"] if "admin_decision" in keys else None,
        admin_id=row["admin_id"] if "admin_id" in keys else None,
        admin_notes=row["admin_notes"] if "admin_notes" in keys else None,
        admin_decided_at_utc=row["admin_decided_at_utc"] if "admin_decided_at_utc" in keys else None,
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
        req_keys = req_row.keys()
        needs_admin = bool(req_row["requires_admin_release"]) if "requires_admin_release" in req_keys else False

        if payload.user_response == "approved":
            new_status = "awaiting_admin_release" if needs_admin else "confirmed_legitimate"
        else:
            new_status = "denied_suspicious"

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
            conn.execute(
                """
                UPDATE verification_requests
                SET requires_admin_release = 0
                WHERE request_id = ?;
                """,
                (request_id,),
            )
            conn.execute(
                """
                UPDATE transactions
                SET status = 'BLOCKED',
                    balance_deducted = 0,
                    decision_reason = 'Thank you for your response — the transaction is blocked and your simulated balance was not deducted.'
                WHERE transaction_id = ?;
                """,
                (req_row["transaction_id"],),
            )
            create_or_get_incident_for_denial(
                conn=conn,
                transaction_id=req_row["transaction_id"],
                verification_request_id=request_id,
                user_id=req_row["user_id"],
                denial_notes=payload.response_notes,
                db_path=db_path,
            )
        else:
            if needs_admin:
                conn.execute(
                    """
                    UPDATE transactions
                    SET status = 'HELD_HIGH_RISK',
                        balance_deducted = 0,
                        decision_reason = 'Customer confirmed ownership; awaiting Admin investigation & release in Risk Analysis Lab.'
                    WHERE transaction_id = ?;
                    """,
                    (req_row["transaction_id"],),
                )
            else:
                tx_row = conn.execute(
                    "SELECT amount, user_id, status, balance_deducted FROM transactions WHERE transaction_id = ?;",
                    (req_row["transaction_id"],),
                ).fetchone()
                if tx_row is not None:
                    already_deducted = bool(tx_row["balance_deducted"]) if "balance_deducted" in tx_row.keys() else True
                    if not already_deducted and tx_row["status"] in ("PENDING_VERIFICATION", "HELD_HIGH_RISK"):
                        conn.execute(
                            """
                            UPDATE users
                            SET simulated_balance = ROUND(MAX(0.0, simulated_balance - ?), 2)
                            WHERE user_id = ?;
                            """,
                            (round(float(tx_row["amount"]), 2), tx_row["user_id"]),
                        )
                    conn.execute(
                        """
                        UPDATE transactions
                        SET status = 'COMPLETED',
                            balance_deducted = 1,
                            decision_reason = 'Thank you for your confirmation — your transfer has been approved and completed.'
                        WHERE transaction_id = ?;
                        """,
                        (req_row["transaction_id"],),
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


def admin_decide_transaction(
    transaction_id: str,
    payload: AdminTransactionDecisionSchema,
    admin_user_id: str = "ADMIN-001",
    db_path: Optional[Path] = None,
) -> Optional[AdminDecisionResponseSchema]:
    """Allow an Administrator to approve/release or block a pending/held transaction after investigation.

    - If `admin_decision == 'approve'`:
      - Deducts `amount` from the customer's `simulated_balance` once (if not yet deducted).
      - Updates `transactions.status = 'COMPLETED'`, `balance_deducted = 1`.
      - Marks the linked `verification_requests` row `confirmed_legitimate` with `admin_decision = 'approved'`.
    - If `admin_decision == 'block'`:
      - Keeps `balance_deducted = 0`, marks `transactions.status = 'BLOCKED'`.
      - Marks the linked `verification_requests` row `denied_suspicious` with `admin_decision = 'blocked'`.
      - Automatically creates/links a tamper-evident SHA-256 forensic incident.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?;",
            (transaction_id,),
        ).fetchone()
        if tx_row is None:
            return None

        uid = tx_row["user_id"]
        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (uid,),
        ).fetchone()
        if user_row is None:
            return None

        ver_row = conn.execute(
            """
            SELECT * FROM verification_requests
            WHERE transaction_id = ?
            ORDER BY created_at_utc DESC LIMIT 1;
            """,
            (transaction_id,),
        ).fetchone()

        if ver_row is None:
            cnt = int(conn.execute("SELECT COUNT(*) AS cnt FROM verification_requests;").fetchone()["cnt"])
            req_id = f"VER-{cnt + 1:04d}"
            while conn.execute("SELECT 1 FROM verification_requests WHERE request_id = ?;", (req_id,)).fetchone():
                cnt += 1
                req_id = f"VER-{cnt + 1:04d}"
            conn.execute(
                """
                INSERT INTO verification_requests (
                    request_id, transaction_id, user_id, status,
                    created_at_utc, requires_admin_release
                ) VALUES (?, ?, ?, 'pending', ?, 1);
                """,
                (req_id, transaction_id, uid, now_utc),
            )
        else:
            req_id = str(ver_row["request_id"])

        tx_keys = tx_row.keys()
        current_tx_status = str(tx_row["status"]) if "status" in tx_keys and tx_row["status"] else "COMPLETED"
        already_deducted = bool(tx_row["balance_deducted"]) if "balance_deducted" in tx_keys else True
        tx_amount = round(float(tx_row["amount"]), 2)
        notes = (payload.admin_notes or "Investigated in Risk Analysis Lab and confirmed with account owner.").strip()

        if payload.admin_decision == "approve":
            if current_tx_status == "BLOCKED":
                raise VerificationConflictError(
                    f"Transaction '{transaction_id}' has already been BLOCKED and cannot be released."
                )
            if not already_deducted:
                current_bal = float(user_row["simulated_balance"]) if "simulated_balance" in user_row.keys() else 25000.0
                if tx_amount > current_bal:
                    raise ValueError(
                        f"Cannot release transfer: customer simulated balance (₹{current_bal:,.2f}) is lower than transfer amount (₹{tx_amount:,.2f})."
                    )
                conn.execute(
                    """
                    UPDATE users
                    SET simulated_balance = ROUND(MAX(0.0, simulated_balance - ?), 2)
                    WHERE user_id = ?;
                    """,
                    (tx_amount, uid),
                )
            conn.execute(
                """
                UPDATE transactions
                SET status = 'COMPLETED',
                    balance_deducted = 1,
                    decision_reason = ?
                WHERE transaction_id = ?;
                """,
                (f"Released & completed by Admin ({admin_user_id}) after Risk Analysis Lab investigation: {notes}", transaction_id),
            )
            conn.execute(
                """
                UPDATE verification_requests
                SET status = 'confirmed_legitimate',
                    admin_decision = 'approved',
                    admin_id = ?,
                    admin_notes = ?,
                    admin_decided_at_utc = ?,
                    responded_at_utc = COALESCE(responded_at_utc, ?)
                WHERE request_id = ?;
                """,
                (admin_user_id, notes, now_utc, now_utc, req_id),
            )
        else:
            conn.execute(
                """
                UPDATE transactions
                SET status = 'BLOCKED',
                    balance_deducted = 0,
                    decision_reason = ?
                WHERE transaction_id = ?;
                """,
                (f"Blocked by Admin ({admin_user_id}) during Risk Analysis Lab investigation: {notes}", transaction_id),
            )
            conn.execute(
                """
                UPDATE verification_requests
                SET status = 'denied_suspicious',
                    admin_decision = 'blocked',
                    admin_id = ?,
                    admin_notes = ?,
                    admin_decided_at_utc = ?,
                    responded_at_utc = COALESCE(responded_at_utc, ?)
                WHERE request_id = ?;
                """,
                (admin_user_id, notes, now_utc, now_utc, req_id),
            )
            create_or_get_incident_for_denial(
                conn=conn,
                transaction_id=transaction_id,
                verification_request_id=req_id,
                user_id=uid,
                denial_notes=f"[Admin Block by {admin_user_id}] {notes}",
                db_path=db_path,
            )

        conn.commit()

        updated_tx = conn.execute(
            """
            SELECT t.*, u.display_name, u.profile_type, u.expenditure_model
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.transaction_id = ?;
            """,
            (transaction_id,),
        ).fetchone()
        updated_user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (uid,),
        ).fetchone()
        updated_ver = conn.execute(
            """
            SELECT vr.*, t.amount, t.currency, t.beneficiary_id, t.beneficiary_name, u.display_name
            FROM verification_requests vr
            JOIN transactions t ON vr.transaction_id = t.transaction_id
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.request_id = ?;
            """,
            (req_id,),
        ).fetchone()
        ver_schema = _row_to_verification_schema(conn, updated_ver, created_new=False)

    return AdminDecisionResponseSchema(
        transaction=_row_to_tx_summary(updated_tx),
        user_profile=_row_to_user_profile(updated_user),
        verification_request=ver_schema,
        linked_incident_id=ver_schema.linked_incident_id,
    )
