from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.database import get_connection
from app.schemas.api_schemas import (
    EvidenceIntegritySchema,
    IncidentDetailResponseSchema,
    IncidentEvidenceSchema,
    IncidentStatusUpdateSchema,
    IncidentSummarySchema,
    TransactionSummarySchema,
    UserProfileSchema,
    VerificationRequestSchema,
)
from app.services.evidence import build_transaction_timeline
from app.services.scoring import score_transaction


def _compute_canonical_sha256(snapshot_obj: Dict[str, Any]) -> tuple[str, str]:
    """Serialize `snapshot_obj` deterministically and return `(canonical_json, sha256_hex)`."""
    canonical_json = json.dumps(snapshot_obj, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return canonical_json, digest


def _build_recommended_actions(
    expenditure_model: str,
    profile_type: str,
    triggered_rule_ids: set[str],
) -> str:
    """Return profile-aware advisory investigation steps (suggestions only, not automated actions)."""
    steps: List[str] = [
        "1. [Advisory Only] Review the user's signed denial statement and contact the account holder out-of-band.",
    ]
    if "VENDOR_BEC_BANK_MODIFIED" in triggered_rule_ids:
        steps.append(
            "2. [B2B BEC Playbook] Verify the recent counterparty bank-routing change (beneficiary_bank_updated) against independent vendor invoice controls."
        )
    if (
        "STRUCTURING_CUMULATIVE_DRAIN" in triggered_rule_ids
        or "CROSS_USER_MULE_CONVERGENCE" in triggered_rule_ids
    ):
        steps.append(
            "3. [Mule & Structuring Playbook] Inspect all 24h split transfers and cross-reference other accounts paying the same beneficiary."
        )
    if (
        "IMPOSSIBLE_TRAVEL_GEO_VELOCITY" in triggered_rule_ids
        or "UNSEEN_DEVICE_USED" in triggered_rule_ids
    ):
        steps.append(
            "4. [Session Forensics Playbook] Audit authentication logs for the unseen device and impossible-travel IP hop; recommend credential reset in a real environment."
        )
    if expenditure_model in ("capex_heavy", "opex_heavy"):
        steps.append(
            f"5. [Corporate '{profile_type}' Check] Confirm whether dual-approval corporate disbursement sign-off was bypassed."
        )
    else:
        steps.append(
            f"5. [Individual '{profile_type}' Check] Review recent peer-to-peer beneficiary additions for unauthorized access."
        )
    return "\n".join(steps)


def create_or_get_incident_for_denial(
    conn: sqlite3.Connection,
    transaction_id: str,
    verification_request_id: str,
    user_id: str,
    denial_notes: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    """Create an evidence-linked incident for a denied transaction, or return existing active incident ID.

    Prevents duplicate active incidents (`open` or `investigating`) for the same transaction.
    """
    existing = conn.execute(
        """
        SELECT incident_id
        FROM incidents
        WHERE transaction_id = ? AND status IN ('open', 'investigating')
        ORDER BY created_at_utc DESC
        LIMIT 1;
        """,
        (transaction_id,),
    ).fetchone()
    if existing is not None:
        return str(existing["incident_id"])

    score_res = score_transaction(
        transaction_id=transaction_id,
        method="contextual_ti",
        db_path=db_path,
    )
    timeline_res = build_transaction_timeline(
        transaction_id=transaction_id,
        db_path=db_path,
    )
    assert score_res is not None and timeline_res is not None

    user_row = conn.execute(
        "SELECT * FROM users WHERE user_id = ?;",
        (user_id,),
    ).fetchone()
    tx_row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?;",
        (transaction_id,),
    ).fetchone()

    count_row = conn.execute("SELECT COUNT(*) AS cnt FROM incidents;").fetchone()
    next_num = int(count_row["cnt"]) + 1
    incident_id = f"INC-{next_num:04d}"

    score_val = score_res.risk_score
    if score_val >= 85:
        severity = "critical"
    elif score_val >= 60:
        severity = "high"
    else:
        severity = "medium"

    triggered_ids = {r.rule_id for r in score_res.triggered_rules}
    recommended = _build_recommended_actions(
        expenditure_model=user_row["expenditure_model"],
        profile_type=user_row["profile_type"],
        triggered_rule_ids=triggered_ids,
    )

    snapshot_payload: Dict[str, Any] = {
        "transaction_id": transaction_id,
        "verification_request_id": verification_request_id,
        "user_id": user_id,
        "amount": float(tx_row["amount"]),
        "currency": tx_row["currency"],
        "timestamp_utc": tx_row["timestamp_utc"],
        "beneficiary_id": tx_row["beneficiary_id"],
        "device_id": tx_row["device_id"],
        "ip_address": tx_row["ip_address"],
        "geo_location": tx_row["geo_location"],
        "user_profile_snapshot": {
            "profile_type": user_row["profile_type"],
            "industry_sector": user_row["industry_sector"],
            "expenditure_model": user_row["expenditure_model"],
            "net_worth_band": user_row["net_worth_band"],
            "typical_max_tx_amount": float(user_row["typical_max_tx_amount"]),
        },
        "scoring_method": "contextual_ti",
        "risk_score_at_creation": score_val,
        "triggered_rules": [
            {
                "rule_id": r.rule_id,
                "points_awarded": r.points_awarded,
                "evidence_refs": r.evidence_refs,
            }
            for r in score_res.triggered_rules
        ],
        "timeline_record_ids": [
            f"{e.source_table}:{e.source_record_id}" for e in timeline_res.timeline
        ],
    }
    canonical_json, sha256_hex = _compute_canonical_sha256(snapshot_payload)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note_suffix = f" User note: {denial_notes}" if denial_notes else ""
    summary_reason = (
        f"User '{user_row['display_name']}' ({user_id}) denied transaction {transaction_id} "
        f"(${float(tx_row['amount']):,.2f} to '{tx_row['beneficiary_name']}') via verification request "
        f"{verification_request_id}. Contextual+TI risk score at escalation: {score_val}/100.{note_suffix}"
    )

    conn.execute(
        """
        INSERT INTO incidents (
            incident_id, transaction_id, verification_request_id, user_id,
            status, severity, risk_score_at_creation, scoring_method_used,
            summary_reason, recommended_actions, evidence_snapshot_json,
            evidence_sha256, created_at_utc, updated_at_utc
        ) VALUES (?, ?, ?, ?, 'open', ?, ?, 'contextual_ti', ?, ?, ?, ?, ?, ?);
        """,
        (
            incident_id,
            transaction_id,
            verification_request_id,
            user_id,
            severity,
            score_val,
            summary_reason,
            recommended,
            canonical_json,
            sha256_hex,
            now_utc,
            now_utc,
        ),
    )

    ev_count_row = conn.execute("SELECT COUNT(*) AS cnt FROM incident_evidence;").fetchone()
    ev_seq = int(ev_count_row["cnt"]) + 1

    for entry in timeline_res.timeline:
        ev_id = f"EVID-{ev_seq:04d}"
        ev_seq += 1
        conn.execute(
            """
            INSERT INTO incident_evidence (
                evidence_id, incident_id, evidence_type,
                source_record_id, timestamp_utc, explanation
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                ev_id,
                incident_id,
                f"{entry.event_category}:{entry.event_type}",
                f"{entry.source_table}:{entry.source_record_id}",
                entry.timestamp_utc,
                f"[{entry.kill_chain_phase}] {entry.recorded_fact} | {entry.system_interpretation}",
            ),
        )

    return incident_id


def _row_to_incident_summary(row: sqlite3.Row) -> IncidentSummarySchema:
    return IncidentSummarySchema(
        incident_id=row["incident_id"],
        transaction_id=row["transaction_id"],
        verification_request_id=row["verification_request_id"],
        user_id=row["user_id"],
        user_display_name=row["display_name"],
        user_profile_type=row["profile_type"],
        user_expenditure_model=row["expenditure_model"],
        amount=float(row["amount"]),
        currency=row["currency"],
        beneficiary_name=row["beneficiary_name"],
        status=row["status"],
        severity=row["severity"],
        risk_score_at_creation=int(row["risk_score_at_creation"]),
        scoring_method_used=row["scoring_method_used"],
        summary_reason=row["summary_reason"],
        evidence_sha256=row["evidence_sha256"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
    )


def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[IncidentSummarySchema]:
    """List incidents ordered newest first, optionally filtered by status, severity, or user_id."""
    clauses: List[str] = []
    params: List[object] = []

    if status:
        clauses.append("i.status = ?")
        params.append(status)
    if severity:
        clauses.append("i.severity = ?")
        params.append(severity)
    if user_id:
        clauses.append("i.user_id = ?")
        params.append(user_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT i.*,
               t.amount, t.currency, t.beneficiary_name,
               u.display_name, u.profile_type, u.expenditure_model
        FROM incidents i
        JOIN transactions t ON i.transaction_id = t.transaction_id
        JOIN users u ON i.user_id = u.user_id
        {where_sql}
        ORDER BY i.created_at_utc DESC, i.incident_id DESC;
    """

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_incident_summary(r) for r in rows]


def get_incident_detail(
    incident_id: str,
    db_path: Optional[Path] = None,
) -> Optional[IncidentDetailResponseSchema]:
    """Retrieve full incident detail, linked evidence, user profile, and live SHA-256 verification."""
    with get_connection(db_path) as conn:
        inc_row = conn.execute(
            """
            SELECT i.*,
                   t.amount, t.currency, t.beneficiary_id, t.beneficiary_name,
                   t.beneficiary_category, t.beneficiary_industry,
                   t.timestamp_utc AS tx_timestamp_utc,
                   t.device_id, t.ip_address, t.geo_location,
                   u.display_name, u.account_category, u.profile_type,
                   u.industry_sector, u.expenditure_model, u.net_worth_band,
                   u.estimated_net_worth, u.declared_monthly_turnover,
                   u.typical_tx_amount, u.typical_max_tx_amount,
                   u.expected_monthly_tx_count, u.operating_hours_utc,
                   u.home_geo_location, u.created_at_utc AS user_created_at_utc
            FROM incidents i
            JOIN transactions t ON i.transaction_id = t.transaction_id
            JOIN users u ON i.user_id = u.user_id
            WHERE i.incident_id = ?;
            """,
            (incident_id,),
        ).fetchone()
        if inc_row is None:
            return None

        ev_rows = conn.execute(
            """
            SELECT *
            FROM incident_evidence
            WHERE incident_id = ?
            ORDER BY timestamp_utc ASC, evidence_id ASC;
            """,
            (incident_id,),
        ).fetchall()

        ver_row = None
        if inc_row["verification_request_id"]:
            ver_row = conn.execute(
                """
                SELECT *
                FROM verification_requests
                WHERE request_id = ?;
                """,
                (inc_row["verification_request_id"],),
            ).fetchone()

    tx_id = inc_row["transaction_id"]
    method_used = inc_row["scoring_method_used"] or "contextual_ti"
    risk_eval = score_transaction(
        transaction_id=tx_id,
        method=method_used,
        db_path=db_path,
    )
    assert risk_eval is not None

    # Verify SHA-256 integrity of the stored canonical JSON snapshot
    stored_sha256 = inc_row["evidence_sha256"]
    raw_snapshot_json = inc_row["evidence_snapshot_json"]
    recomputed_sha256 = hashlib.sha256(raw_snapshot_json.encode("utf-8")).hexdigest()
    is_valid = recomputed_sha256 == stored_sha256
    integrity = EvidenceIntegritySchema(
        stored_sha256=stored_sha256,
        recomputed_sha256=recomputed_sha256,
        integrity_verified=is_valid,
        verification_message=(
            "Verified: Stored forensic snapshot matches its SHA-256 digest."
            if is_valid
            else "INTEGRITY MISMATCH: Stored forensic snapshot does not match original SHA-256 digest!"
        ),
    )

    tx_summary = TransactionSummarySchema(
        transaction_id=tx_id,
        user_id=inc_row["user_id"],
        user_display_name=inc_row["display_name"],
        user_profile_type=inc_row["profile_type"],
        user_expenditure_model=inc_row["expenditure_model"],
        amount=float(inc_row["amount"]),
        currency=inc_row["currency"],
        timestamp_utc=inc_row["tx_timestamp_utc"],
        beneficiary_id=inc_row["beneficiary_id"],
        beneficiary_name=inc_row["beneficiary_name"],
        beneficiary_category=inc_row["beneficiary_category"],
        beneficiary_industry=inc_row["beneficiary_industry"],
        device_id=inc_row["device_id"],
        ip_address=inc_row["ip_address"],
        geo_location=inc_row["geo_location"],
    )

    user_profile = UserProfileSchema(
        user_id=inc_row["user_id"],
        display_name=inc_row["display_name"],
        account_category=inc_row["account_category"],
        profile_type=inc_row["profile_type"],
        industry_sector=inc_row["industry_sector"],
        expenditure_model=inc_row["expenditure_model"],
        net_worth_band=inc_row["net_worth_band"],
        estimated_net_worth=float(inc_row["estimated_net_worth"]),
        declared_monthly_turnover=float(inc_row["declared_monthly_turnover"]),
        typical_tx_amount=float(inc_row["typical_tx_amount"]),
        typical_max_tx_amount=float(inc_row["typical_max_tx_amount"]),
        expected_monthly_tx_count=int(inc_row["expected_monthly_tx_count"]),
        operating_hours_utc=inc_row["operating_hours_utc"],
        home_geo_location=inc_row["home_geo_location"],
        created_at_utc=inc_row["user_created_at_utc"],
    )

    ver_schema = None
    if ver_row is not None:
        ver_schema = VerificationRequestSchema(
            request_id=ver_row["request_id"],
            transaction_id=tx_id,
            user_id=inc_row["user_id"],
            user_display_name=inc_row["display_name"],
            amount=float(inc_row["amount"]),
            currency=inc_row["currency"],
            beneficiary_id=inc_row["beneficiary_id"],
            beneficiary_name=inc_row["beneficiary_name"],
            status=ver_row["status"],
            created_at_utc=ver_row["created_at_utc"],
            responded_at_utc=ver_row["responded_at_utc"],
            user_response=ver_row["user_response"],
            response_notes=ver_row["response_notes"],
            linked_incident_id=incident_id,
            created_new=False,
        )

    evidence_list = [
        IncidentEvidenceSchema(
            evidence_id=r["evidence_id"],
            incident_id=r["incident_id"],
            evidence_type=r["evidence_type"],
            source_record_id=r["source_record_id"],
            timestamp_utc=r["timestamp_utc"],
            explanation=r["explanation"],
        )
        for r in ev_rows
    ]

    rec_lines = [
        line.strip()
        for line in (inc_row["recommended_actions"] or "").splitlines()
        if line.strip()
    ]

    return IncidentDetailResponseSchema(
        incident=_row_to_incident_summary(inc_row),
        recommended_actions=rec_lines,
        evidence_integrity=integrity,
        transaction=tx_summary,
        user_profile=user_profile,
        verification_request=ver_schema,
        risk_evaluation=risk_eval,
        linked_evidence=evidence_list,
    )


def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdateSchema,
    db_path: Optional[Path] = None,
) -> Optional[IncidentDetailResponseSchema]:
    """Update an incident's lifecycle status ('open', 'investigating', 'closed') while preserving evidence."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT summary_reason FROM incidents WHERE incident_id = ?;",
            (incident_id,),
        ).fetchone()
        if row is None:
            return None

        updated_reason = row["summary_reason"]
        if payload.investigator_note:
            updated_reason = (
                f"{updated_reason} | [{now_utc} status->{payload.status}] {payload.investigator_note}"
            )

        conn.execute(
            """
            UPDATE incidents
            SET status = ?,
                summary_reason = ?,
                updated_at_utc = ?
            WHERE incident_id = ?;
            """,
            (payload.status, updated_reason, now_utc, incident_id),
        )
        conn.commit()

    return get_incident_detail(incident_id=incident_id, db_path=db_path)
