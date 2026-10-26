from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.database import get_connection
from app.schemas.api_schemas import (
    AlertDecisionResponseSchema,
    UserPreferencesSchema,
    UserPreferencesUpdateSchema,
)
from app.services.scoring import score_transaction

DEFAULT_RISK_THRESHOLD = 60
DEFAULT_CRITICAL_BYPASS_THRESHOLD = 85
DEFAULT_TIMEZONE_IANA = "UTC"
DEFAULT_QUIET_HOURS_ENABLED = True
DEFAULT_QUIET_HOURS_START = "22:00"
DEFAULT_QUIET_HOURS_END = "07:00"

SUPPORTED_DEMO_TIMEZONES: List[str] = [
    "UTC",
    "Asia/Kolkata",
    "Europe/London",
    "America/New_York",
    "America/Los_Angeles",
    "Asia/Singapore",
    "Asia/Dubai",
    "Europe/Paris",
    "Asia/Tokyo",
]

POLICY_DISCLAIMER_TEXT = (
    "Demonstration Alert Policy Only: Quiet-hours queueing and critical-event bypass are simulated "
    "for classroom evaluation. Quiet hours never erase forensic evidence or modify the underlying rule-based risk score."
)

_HHMM_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validate_timezone_iana(tz_name: str) -> ZoneInfo:
    """Validate an IANA timezone string and return its `ZoneInfo` object."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError(
            f"Invalid IANA time zone '{tz_name}'. Examples: 'Asia/Kolkata', 'Europe/London', 'America/New_York', 'UTC'."
        ) from exc


def validate_hhmm(time_str: str, field_name: str = "time") -> int:
    """Validate a 24-hour `HH:MM` string and return minutes since midnight (0..1439)."""
    if not _HHMM_REGEX.match(time_str):
        raise ValueError(f"Invalid {field_name} '{time_str}'. Expected 24-hour HH:MM format (00:00 to 23:59).")
    hh_s, mm_s = time_str.split(":")
    return int(hh_s) * 60 + int(mm_s)


def is_within_quiet_hours(
    local_dt: datetime,
    quiet_hours_enabled: bool,
    quiet_hours_start: str,
    quiet_hours_end: str,
) -> bool:
    """Determine whether `local_dt` falls inside the configured `[start, end)` quiet-hours window.

    Correctly handles both same-day windows (e.g., 13:00-15:00) and overnight windows
    crossing midnight (e.g., 22:00-07:00).
    """
    if not quiet_hours_enabled:
        return False

    start_min = validate_hhmm(quiet_hours_start, "quiet_hours_start")
    end_min = validate_hhmm(quiet_hours_end, "quiet_hours_end")
    current_min = local_dt.hour * 60 + local_dt.minute

    if start_min == end_min:
        return False
    if start_min < end_min:
        return start_min <= current_min < end_min
    # Overnight window crossing midnight (e.g., 22:00 to 07:00)
    return current_min >= start_min or current_min < end_min


def convert_utc_to_local(timestamp_utc_str: str, timezone_iana: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`) and convert to `timezone_iana`."""
    tz = validate_timezone_iana(timezone_iana)
    dt_utc = datetime.strptime(timestamp_utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return dt_utc.astimezone(tz)


def get_user_preferences(
    user_id: str,
    db_path: Optional[Path] = None,
) -> Optional[UserPreferencesSchema]:
    """Retrieve stored alert preferences for `user_id`, or `None` if user does not exist."""
    with get_connection(db_path) as conn:
        user_row = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        if user_row is None:
            return None

        pref_row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?;",
            (user_id,),
        ).fetchone()

    if pref_row is None:
        return UserPreferencesSchema(
            user_id=user_id,
            risk_threshold=DEFAULT_RISK_THRESHOLD,
            critical_bypass_threshold=DEFAULT_CRITICAL_BYPASS_THRESHOLD,
            timezone_iana=DEFAULT_TIMEZONE_IANA,
            quiet_hours_enabled=DEFAULT_QUIET_HOURS_ENABLED,
            quiet_hours_start=DEFAULT_QUIET_HOURS_START,
            quiet_hours_end=DEFAULT_QUIET_HOURS_END,
            updated_at_utc="2026-01-01T00:00:00Z",
        )

    return UserPreferencesSchema(
        user_id=pref_row["user_id"],
        risk_threshold=int(pref_row["risk_threshold"]),
        critical_bypass_threshold=int(pref_row["critical_bypass_threshold"]),
        timezone_iana=pref_row["timezone_iana"],
        quiet_hours_enabled=bool(pref_row["quiet_hours_enabled"]),
        quiet_hours_start=pref_row["quiet_hours_start"],
        quiet_hours_end=pref_row["quiet_hours_end"],
        updated_at_utc=pref_row["updated_at_utc"],
    )


def update_user_preferences(
    user_id: str,
    payload: UserPreferencesUpdateSchema,
    db_path: Optional[Path] = None,
) -> Optional[UserPreferencesSchema]:
    """Validate and persist updated alert preferences for `user_id`.

    Returns `None` if `user_id` does not exist.
    Raises `ValueError` if timezone is invalid or `critical_bypass_threshold < risk_threshold`.
    """
    validate_timezone_iana(payload.timezone_iana)
    validate_hhmm(payload.quiet_hours_start, "quiet_hours_start")
    validate_hhmm(payload.quiet_hours_end, "quiet_hours_end")

    if payload.critical_bypass_threshold < payload.risk_threshold:
        raise ValueError(
            f"critical_bypass_threshold ({payload.critical_bypass_threshold}) must be greater than or equal to "
            f"risk_threshold ({payload.risk_threshold})."
        )

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        user_row = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        if user_row is None:
            return None

        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, risk_threshold, critical_bypass_threshold,
                timezone_iana, quiet_hours_enabled, quiet_hours_start,
                quiet_hours_end, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                risk_threshold = excluded.risk_threshold,
                critical_bypass_threshold = excluded.critical_bypass_threshold,
                timezone_iana = excluded.timezone_iana,
                quiet_hours_enabled = excluded.quiet_hours_enabled,
                quiet_hours_start = excluded.quiet_hours_start,
                quiet_hours_end = excluded.quiet_hours_end,
                updated_at_utc = excluded.updated_at_utc;
            """,
            (
                user_id,
                payload.risk_threshold,
                payload.critical_bypass_threshold,
                payload.timezone_iana,
                1 if payload.quiet_hours_enabled else 0,
                payload.quiet_hours_start,
                payload.quiet_hours_end,
                now_utc,
            ),
        )
        conn.commit()

    return get_user_preferences(user_id=user_id, db_path=db_path)


def evaluate_alert_decision(
    transaction_id: str,
    method: str = "contextual",
    override_threshold: Optional[int] = None,
    override_critical_bypass: Optional[int] = None,
    override_timezone: Optional[str] = None,
    override_quiet_hours_enabled: Optional[bool] = None,
    override_quiet_hours_start: Optional[str] = None,
    override_quiet_hours_end: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[AlertDecisionResponseSchema]:
    """Evaluate a transaction's risk score against user alert policy (or What-If overrides).

    Returns `None` if `transaction_id` does not exist.
    """
    score_res = score_transaction(
        transaction_id=transaction_id,
        method=method,
        db_path=db_path,
    )
    if score_res is None:
        return None

    with get_connection(db_path) as conn:
        tx_row = conn.execute(
            "SELECT timestamp_utc, user_id FROM transactions WHERE transaction_id = ?;",
            (transaction_id,),
        ).fetchone()

    user_id = tx_row["user_id"]
    tx_utc_str = tx_row["timestamp_utc"]

    stored_prefs = get_user_preferences(user_id=user_id, db_path=db_path)
    assert stored_prefs is not None

    is_what_if = any(
        v is not None
        for v in (
            override_threshold,
            override_critical_bypass,
            override_timezone,
            override_quiet_hours_enabled,
            override_quiet_hours_start,
            override_quiet_hours_end,
        )
    )

    eff_threshold = (
        override_threshold if override_threshold is not None else stored_prefs.risk_threshold
    )
    eff_critical = (
        override_critical_bypass
        if override_critical_bypass is not None
        else max(stored_prefs.critical_bypass_threshold, eff_threshold)
    )
    if eff_critical < eff_threshold:
        raise ValueError(
            f"critical_bypass_threshold ({eff_critical}) cannot be lower than risk_threshold ({eff_threshold})."
        )

    eff_tz = override_timezone if override_timezone is not None else stored_prefs.timezone_iana
    eff_qh_enabled = (
        override_quiet_hours_enabled
        if override_quiet_hours_enabled is not None
        else stored_prefs.quiet_hours_enabled
    )
    eff_qh_start = (
        override_quiet_hours_start
        if override_quiet_hours_start is not None
        else stored_prefs.quiet_hours_start
    )
    eff_qh_end = (
        override_quiet_hours_end
        if override_quiet_hours_end is not None
        else stored_prefs.quiet_hours_end
    )

    local_dt = convert_utc_to_local(tx_utc_str, eff_tz)
    local_formatted = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    in_quiet = is_within_quiet_hours(
        local_dt=local_dt,
        quiet_hours_enabled=eff_qh_enabled,
        quiet_hours_start=eff_qh_start,
        quiet_hours_end=eff_qh_end,
    )

    score = score_res.risk_score
    exceeds_threshold = score >= eff_threshold
    exceeds_critical = score >= eff_critical

    if not exceeds_threshold:
        decision = "NO_ALERT_BELOW_THRESHOLD"
        explanation = (
            f"No alert triggered: rule-based score ({score}/100) is below the configured "
            f"threshold ({eff_threshold}). Underlying forensic evidence remains recorded."
        )
    elif not in_quiet:
        decision = "ALERT_NOW"
        explanation = (
            f"Alert immediately: rule-based score ({score}/100) meets/exceeds threshold ({eff_threshold}) "
            f"and local transaction time ({local_dt.strftime('%H:%M')} {eff_tz}) is outside quiet hours "
            f"({eff_qh_start}-{eff_qh_end})."
        )
    elif exceeds_critical:
        decision = "ALERT_NOW_CRITICAL_BYPASS"
        explanation = (
            f"Urgent alert (quiet-hours bypass): transaction occurred during local quiet hours "
            f"({local_dt.strftime('%H:%M')} {eff_tz}, window {eff_qh_start}-{eff_qh_end}), "
            f"but score ({score}/100) meets/exceeds critical bypass threshold ({eff_critical})."
        )
    else:
        decision = "QUEUED_FOR_QUIET_HOURS"
        explanation = (
            f"Alert queued until {eff_qh_end} ({eff_tz}): rule-based score ({score}/100) meets/exceeds "
            f"threshold ({eff_threshold}) during local quiet hours ({local_dt.strftime('%H:%M')} {eff_tz}), "
            f"and is below the critical bypass level ({eff_critical})."
        )

    applied_prefs = UserPreferencesSchema(
        user_id=user_id,
        risk_threshold=eff_threshold,
        critical_bypass_threshold=eff_critical,
        timezone_iana=eff_tz,
        quiet_hours_enabled=eff_qh_enabled,
        quiet_hours_start=eff_qh_start,
        quiet_hours_end=eff_qh_end,
        updated_at_utc=stored_prefs.updated_at_utc,
    )

    return AlertDecisionResponseSchema(
        transaction_id=transaction_id,
        user_id=user_id,
        scoring_method=method,
        risk_score=score,
        risk_band=score_res.risk_band,
        applied_preferences=applied_prefs,
        is_what_if_simulation=is_what_if,
        transaction_timestamp_utc=tx_utc_str,
        transaction_local_time=local_formatted,
        within_quiet_hours=in_quiet,
        exceeds_risk_threshold=exceeds_threshold,
        exceeds_critical_bypass=exceeds_critical,
        alert_decision=decision,
        decision_explanation=explanation,
        policy_disclaimer=POLICY_DISCLAIMER_TEXT,
    )
