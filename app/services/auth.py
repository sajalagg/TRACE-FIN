from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.database import get_connection, next_sequential_id
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.schemas.api_schemas import (
    AuthLoginSchema,
    AuthRegisterSchema,
    AuthTokenResponseSchema,
    LoginSessionSchema,
    NetworkPresetSchema,
    SessionInferredContextSchema,
    SessionObservedEvidenceSchema,
    SessionSimulatedInputSchema,
    UserProfileSchema,
)
from app.services.alert_policy import validate_timezone_iana
from app.services.transactions import _row_to_user_profile


class AuthenticationError(Exception):
    """Raised when username or password authentication fails."""


def extract_ip_prefix(ip_address: str) -> str:
    """Extract the first three octets (e.g. '106.51.72.') from an IPv4 string."""
    cleaned = ip_address.strip()
    parts = cleaned.split(".")
    if len(parts) >= 3:
        return f"{parts[0]}.{parts[1]}.{parts[2]}."
    return cleaned if cleaned.endswith(".") else f"{cleaned}."


def _check_active_ip_threat_intel(
    conn: sqlite3.Connection,
    ip_address: str,
    now_utc: str,
) -> Tuple[bool, Optional[str]]:
    """Return `(is_active_match, threat_category)` if `ip_address` matches an unexpired indicator."""
    row = conn.execute(
        """
        SELECT threat_category, expires_at_utc
        FROM threat_intelligence
        WHERE indicator = ? AND indicator_type = 'ip_address';
        """,
        (ip_address,),
    ).fetchone()
    if row is None:
        return False, None
    if str(row["expires_at_utc"]) >= now_utc:
        return True, str(row["threat_category"])
    return False, None


def _build_context_summary(
    is_known_ip: bool,
    is_known_device: bool,
    is_home_location: bool,
    network_type: str,
    failed_logins_1h: int,
    active_ti: bool,
    ti_cat: Optional[str],
) -> str:
    """Create a concise human-readable forensic summary for a login session."""
    notes: List[str] = []
    if is_known_ip and is_known_device and is_home_location and network_type in ("home_broadband", "corporate_network"):
        notes.append("Baseline trusted home/corporate session on a registered device.")
    else:
        if not is_home_location:
            notes.append("Unfamiliar geographic location compared to registered home location.")
        if not is_known_ip:
            notes.append("First-time or non-baseline IP address for this user.")
        if not is_known_device:
            notes.append("Unrecognized device not previously registered to this user.")
        if network_type in ("public_wifi", "commercial_vpn", "mobile_roaming", "anonymizer_proxy"):
            notes.append(f"Network context reported as '{network_type.replace('_', ' ')}'.")
    if failed_logins_1h > 0:
        notes.append(f"{failed_logins_1h} failed login attempt(s) observed in the preceding hour.")
    if active_ti:
        notes.append(f"Active demo threat-intelligence match ({ti_cat or 'flagged_ip'}).")
    return " ".join(notes)


def _row_to_login_session(
    conn: sqlite3.Connection,
    session_row: sqlite3.Row,
    user_row: sqlite3.Row,
) -> LoginSessionSchema:
    """Build a `LoginSessionSchema` with Observed / Simulated / Inferred provenance."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    is_revoked = bool(session_row["is_revoked"])
    is_expired = str(session_row["expires_at_utc"]) < now_utc
    is_active = (not is_revoked) and (not is_expired)

    u_keys = user_row.keys()
    home_geo = str(user_row["home_geo_location"])
    home_prefix = (
        str(user_row["home_ip_prefix"])
        if "home_ip_prefix" in u_keys and user_row["home_ip_prefix"]
        else "103.21.244."
    )

    s_keys = session_row.keys()
    ip_addr = str(session_row["ip_address"])
    geo_loc = str(session_row["geo_location"]) if "geo_location" in s_keys else home_geo
    dev_id = str(session_row["device_id"])
    dev_label = str(session_row["device_label"]) if "device_label" in s_keys else "Registered Web Session"
    net_type = str(session_row["network_type"]) if "network_type" in s_keys else "home_broadband"
    is_known_ip = bool(session_row["is_known_ip"]) if "is_known_ip" in s_keys else True
    is_known_dev = bool(session_row["is_known_device"]) if "is_known_device" in s_keys else True
    is_home_loc = bool(session_row["is_home_location"]) if "is_home_location" in s_keys else (geo_loc == home_geo)
    failed_1h = int(session_row["failed_logins_1h"]) if "failed_logins_1h" in s_keys else 0

    active_ti, ti_cat = _check_active_ip_threat_intel(
        conn,
        ip_addr,
        str(session_row["created_at_utc"]),
    )
    summary = _build_context_summary(
        is_known_ip=is_known_ip,
        is_known_device=is_known_dev,
        is_home_location=is_home_loc,
        network_type=net_type,
        failed_logins_1h=failed_1h,
        active_ti=active_ti,
        ti_cat=ti_cat,
    )

    observed = SessionObservedEvidenceSchema(
        session_id=str(session_row["session_id"]),
        user_id=str(session_row["user_id"]),
        created_at_utc=str(session_row["created_at_utc"]),
        expires_at_utc=str(session_row["expires_at_utc"]),
        failed_logins_1h=failed_1h,
        is_active=is_active,
    )
    simulated = SessionSimulatedInputSchema(
        ip_address=ip_addr,
        network_type=net_type,
        device_id=dev_id,
        device_label=dev_label,
    )
    inferred = SessionInferredContextSchema(
        geo_location=geo_loc,
        home_geo_location=home_geo,
        home_ip_prefix=home_prefix,
        is_known_ip=is_known_ip,
        is_known_device=is_known_dev,
        is_home_location=is_home_loc,
        active_threat_intel_match=active_ti,
        threat_intel_category=ti_cat,
        context_summary=summary,
    )

    return LoginSessionSchema(
        session_id=str(session_row["session_id"]),
        user_id=str(session_row["user_id"]),
        role=str(session_row["role"]),
        ip_address=ip_addr,
        geo_location=geo_loc,
        device_id=dev_id,
        device_label=dev_label,
        network_type=net_type,
        is_known_ip=is_known_ip,
        is_known_device=is_known_dev,
        is_home_location=is_home_loc,
        failed_logins_1h=failed_1h,
        created_at_utc=str(session_row["created_at_utc"]),
        expires_at_utc=str(session_row["expires_at_utc"]),
        is_revoked=is_revoked,
        observed_evidence=observed,
        simulated_input=simulated,
        inferred_context=inferred,
    )


def register_customer_account(
    payload: AuthRegisterSchema,
    db_path: Optional[Path] = None,
) -> AuthTokenResponseSchema:
    """Register a new customer account with baseline home IP/location and return an active session."""
    if not validate_timezone_iana(payload.timezone_iana):
        raise ValueError(f"Unrecognized IANA timezone '{payload.timezone_iana}'.")

    clean_username = payload.username.strip().lower()
    if not clean_username:
        raise ValueError("Username cannot be empty.")

    now_dt = datetime.now(timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    home_ip = payload.home_ip_address.strip()
    home_prefix = extract_ip_prefix(home_ip)
    pw_hash = hash_password(payload.password)

    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE LOWER(username) = LOWER(?);",
            (clean_username,),
        ).fetchone()
        if existing is not None:
            raise ValueError(f"Username '{clean_username}' is already registered.")

        new_uid = next_sequential_id(
            conn, "users", "user_id", "USR-", width=3, where_clause="user_id LIKE 'USR-%'"
        )

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
            ) VALUES (?, ?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                new_uid,
                clean_username,
                pw_hash,
                round(float(payload.simulated_balance), 2),
                payload.display_name.strip(),
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
                payload.home_geo_location.strip(),
                home_prefix,
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
            (new_uid, payload.risk_threshold, payload.timezone_iana, now_utc),
        )

        # Register the user's primary baseline device
        uid_num = new_uid.split("-")[1]
        dev_id = f"DEV-{uid_num}-PRIMARY"
        dev_ev_id = next_sequential_id(conn, "device_events", "event_id", "DEV-EVT-")
        conn.execute(
            """
            INSERT INTO device_events (
                event_id, user_id, timestamp_utc, device_id,
                device_label, event_type, known_status
            ) VALUES (?, ?, ?, ?, ?, 'device_registered', 'known');
            """,
            (
                dev_ev_id,
                new_uid,
                now_utc,
                dev_id,
                payload.primary_device_label.strip(),
            ),
        )

        # Seed 2 baseline beneficiaries so the new customer can immediately test routine vs new-beneficiary transfers
        starter_bens = [
            (
                f"BEN-{uid_num}-01",
                "City Utilities & Broadband Services",
                f"SIM-ACCT-{uid_num}-0101",
                "utility_tax",
                "utilities_municipal",
            ),
            (
                f"BEN-{uid_num}-02",
                "Trusted Family & Savings Account",
                f"SIM-ACCT-{uid_num}-0202",
                "personal_peer",
                "general_consumer",
            ),
        ]
        ben_evt_cnt = int(conn.execute("SELECT COUNT(*) AS c FROM beneficiary_events;").fetchone()["c"])
        for idx, (b_id, b_name, b_acct, b_cat, b_ind) in enumerate(starter_bens, start=1):
            conn.execute(
                """
                INSERT INTO beneficiaries (
                    beneficiary_id, user_id, display_name, account_reference,
                    beneficiary_category, beneficiary_industry, status,
                    is_verified, created_at_utc, updated_at_utc, notes
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', 1, ?, ?, ?);
                """,
                (
                    b_id,
                    new_uid,
                    b_name,
                    b_acct,
                    b_cat,
                    b_ind,
                    now_utc,
                    now_utc,
                    "Baseline beneficiary established during account registration.",
                ),
            )
            conn.execute(
                """
                INSERT INTO beneficiary_events (
                    event_id, user_id, beneficiary_id, beneficiary_name,
                    beneficiary_category, beneficiary_industry,
                    timestamp_utc, event_type, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'beneficiary_added', ?);
                """,
                (
                    f"BEN-EVT-{ben_evt_cnt + idx:04d}",
                    new_uid,
                    b_id,
                    b_name,
                    b_cat,
                    b_ind,
                    (now_dt - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "Baseline beneficiary established during account onboarding.",
                ),
            )

        conn.commit()

    return authenticate_and_create_session(
        AuthLoginSchema(
            username=clean_username,
            password=payload.password,
            ip_address=home_ip,
            geo_location=payload.home_geo_location.strip(),
            device_id=dev_id,
            device_label=payload.primary_device_label.strip(),
            network_type="home_broadband",
        ),
        db_path=db_path,
    )


def authenticate_and_create_session(
    payload: AuthLoginSchema,
    db_path: Optional[Path] = None,
) -> AuthTokenResponseSchema:
    """Authenticate a customer or admin user and create a forensic login session record."""
    ident = payload.username.strip()
    now_dt = datetime.now(timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_utc = (now_dt + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        user_row = conn.execute(
            """
            SELECT * FROM users
            WHERE LOWER(username) = LOWER(?) OR UPPER(user_id) = UPPER(?);
            """,
            (ident, ident),
        ).fetchone()
        if user_row is None:
            raise AuthenticationError("Invalid username or password.")

        uid = str(user_row["user_id"])
        u_keys = user_row.keys()
        home_geo = str(user_row["home_geo_location"])
        home_prefix = (
            str(user_row["home_ip_prefix"])
            if "home_ip_prefix" in u_keys and user_row["home_ip_prefix"]
            else "103.21.244."
        )

        # Look up the user's known devices
        known_dev_rows = conn.execute(
            """
            SELECT device_id, device_label
            FROM device_events
            WHERE user_id = ? AND known_status = 'known'
            ORDER BY timestamp_utc ASC;
            """,
            (uid,),
        ).fetchall()
        known_dev_map = {str(r["device_id"]): str(r["device_label"]) for r in known_dev_rows}
        default_dev_id = (
            str(known_dev_rows[0]["device_id"])
            if known_dev_rows
            else f"DEV-{uid.split('-')[-1]}-PRIMARY"
        )
        default_dev_label = (
            str(known_dev_rows[0]["device_label"])
            if known_dev_rows
            else "Primary Registered Workstation"
        )

        ip_addr = (payload.ip_address or f"{home_prefix}25").strip()
        geo_loc = (payload.geo_location or home_geo).strip()
        dev_id = (payload.device_id or default_dev_id).strip()
        dev_label = (
            payload.device_label
            or known_dev_map.get(dev_id, "Unrecognized Web/Mobile Client")
        ).strip()
        net_type = payload.network_type or "home_broadband"

        # Verify password hash
        stored_hash = str(user_row["password_hash"]) if "password_hash" in u_keys else ""
        if not verify_password(payload.password, stored_hash):
            auth_cnt = int(conn.execute("SELECT COUNT(*) AS c FROM authentication_events;").fetchone()["c"])
            conn.execute(
                """
                INSERT INTO authentication_events (
                    event_id, user_id, timestamp_utc, event_type,
                    ip_address, geo_location, device_id, is_success
                ) VALUES (?, ?, ?, 'login_failure', ?, ?, ?, 0);
                """,
                (
                    f"AUTH-EVT-{auth_cnt + 1:04d}",
                    uid,
                    now_utc,
                    ip_addr,
                    geo_loc,
                    dev_id,
                ),
            )
            conn.commit()
            raise AuthenticationError("Invalid username or password.")

        # Optional demo helper: record simulated failed attempts immediately before successful login
        auth_cnt = int(conn.execute("SELECT COUNT(*) AS c FROM authentication_events;").fetchone()["c"])
        for f_idx in range(payload.simulate_failed_attempts):
            auth_cnt += 1
            fail_ts = (now_dt - timedelta(minutes=(payload.simulate_failed_attempts - f_idx) * 2)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
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
                    fail_ts,
                    ip_addr,
                    geo_loc,
                    dev_id,
                ),
            )

        # Evaluate session intelligence against user's historical baseline BEFORE inserting new login_success
        prior_ip_row = conn.execute(
            """
            SELECT 1 FROM authentication_events
            WHERE user_id = ? AND is_success = 1 AND ip_address = ?
            LIMIT 1;
            """,
            (uid, ip_addr),
        ).fetchone()
        is_known_ip = ip_addr.startswith(home_prefix) or (prior_ip_row is not None)
        is_known_device = dev_id in known_dev_map
        is_home_location = geo_loc == home_geo

        one_hour_ago = (now_dt - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        failed_1h = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM authentication_events
                WHERE user_id = ? AND is_success = 0 AND timestamp_utc >= ? AND timestamp_utc <= ?;
                """,
                (uid, one_hour_ago, now_utc),
            ).fetchone()["c"]
        )

        # Record the successful login event
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
                now_utc,
                ip_addr,
                geo_loc,
                dev_id,
            ),
        )

        # If this is an unseen device, record a new_device_detected event for forensic correlation
        if not is_known_device and str(user_row["role"]) == "customer":
            existing_new_dev = conn.execute(
                "SELECT 1 FROM device_events WHERE user_id = ? AND device_id = ? LIMIT 1;",
                (uid, dev_id),
            ).fetchone()
            if existing_new_dev is None:
                dev_ev_id = next_sequential_id(conn, "device_events", "event_id", "DEV-EVT-")
                conn.execute(
                    """
                    INSERT INTO device_events (
                        event_id, user_id, timestamp_utc, device_id,
                        device_label, event_type, known_status
                    ) VALUES (?, ?, ?, ?, ?, 'new_device_detected', 'new');
                    """,
                    (
                        dev_ev_id,
                        uid,
                        now_utc,
                        dev_id,
                        dev_label,
                    ),
                )

        # Create the persisted session record
        raw_token, token_digest = generate_session_token()
        session_id = next_sequential_id(conn, "user_sessions", "session_id", "SES-")

        conn.execute(
            """
            INSERT INTO user_sessions (
                session_id, token_hash, user_id, role,
                ip_address, geo_location, device_id, device_label,
                network_type, is_known_ip, is_known_device, is_home_location,
                failed_logins_1h, created_at_utc, expires_at_utc, is_revoked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
            """,
            (
                session_id,
                token_digest,
                uid,
                str(user_row["role"]),
                ip_addr,
                geo_loc,
                dev_id,
                dev_label,
                net_type,
                1 if is_known_ip else 0,
                1 if is_known_device else 0,
                1 if is_home_location else 0,
                failed_1h,
                now_utc,
                expires_utc,
            ),
        )
        conn.commit()

        session_row = conn.execute(
            "SELECT * FROM user_sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        session_schema = _row_to_login_session(conn, session_row, user_row)
        user_schema = _row_to_user_profile(user_row)

        return AuthTokenResponseSchema(
            session_token=raw_token,
            user=user_schema,
            session=session_schema,
        )


def get_session_by_token(
    token: str,
    db_path: Optional[Path] = None,
) -> Optional[Tuple[UserProfileSchema, LoginSessionSchema]]:
    """Validate a raw session token and return `(UserProfileSchema, LoginSessionSchema)` if active."""
    if not token or not token.strip():
        return None
    token_digest = hash_session_token(token.strip())
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_connection(db_path) as conn:
        ses_row = conn.execute(
            "SELECT * FROM user_sessions WHERE token_hash = ?;",
            (token_digest,),
        ).fetchone()
        if ses_row is None:
            return None
        if int(ses_row["is_revoked"]) == 1 or str(ses_row["expires_at_utc"]) < now_utc:
            return None

        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (ses_row["user_id"],),
        ).fetchone()
        if user_row is None:
            return None

        return _row_to_user_profile(user_row), _row_to_login_session(conn, ses_row, user_row)


def get_session_by_id(
    session_id: str,
    db_path: Optional[Path] = None,
) -> Optional[LoginSessionSchema]:
    """Retrieve a `LoginSessionSchema` by its `session_id` (used for Admin forensic inspection)."""
    with get_connection(db_path) as conn:
        ses_row = conn.execute(
            "SELECT * FROM user_sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        if ses_row is None:
            return None
        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (ses_row["user_id"],),
        ).fetchone()
        if user_row is None:
            return None
        return _row_to_login_session(conn, ses_row, user_row)


def logout_session(
    token: str,
    db_path: Optional[Path] = None,
) -> bool:
    """Revoke an active session token. Returns `True` if a session was revoked."""
    if not token or not token.strip():
        return False
    token_digest = hash_session_token(token.strip())
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "UPDATE user_sessions SET is_revoked = 1 WHERE token_hash = ? AND is_revoked = 0;",
            (token_digest,),
        )
        conn.commit()
        return cur.rowcount > 0


def list_user_sessions(
    user_id: str,
    limit: int = 20,
    db_path: Optional[Path] = None,
) -> List[LoginSessionSchema]:
    """List recent login sessions for `user_id` in reverse chronological order."""
    with get_connection(db_path) as conn:
        user_row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;",
            (user_id,),
        ).fetchone()
        if user_row is None:
            return []
        rows = conn.execute(
            """
            SELECT * FROM user_sessions
            WHERE user_id = ?
            ORDER BY created_at_utc DESC, session_id DESC
            LIMIT ?;
            """,
            (user_id, limit),
        ).fetchall()
        return [_row_to_login_session(conn, r, user_row) for r in rows]


def get_network_presets_for_user(
    username_or_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[NetworkPresetSchema]:
    """Return realistic login network/location presets tailored to the selected user's baseline."""
    home_geo = "IN-Mumbai"
    home_prefix = "103.21.244."
    primary_dev = "DEV-001-PRIMARY"
    mobile_dev = "DEV-001-SECONDARY"

    if username_or_id:
        with get_connection(db_path) as conn:
            u_row = conn.execute(
                "SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR UPPER(user_id) = UPPER(?);",
                (username_or_id.strip(), username_or_id.strip()),
            ).fetchone()
            if u_row is not None:
                u_keys = u_row.keys()
                home_geo = str(u_row["home_geo_location"])
                home_prefix = (
                    str(u_row["home_ip_prefix"])
                    if "home_ip_prefix" in u_keys and u_row["home_ip_prefix"]
                    else "103.21.244."
                )
                devs = conn.execute(
                    """
                    SELECT device_id FROM device_events
                    WHERE user_id = ? AND known_status = 'known'
                    ORDER BY timestamp_utc ASC;
                    """,
                    (u_row["user_id"],),
                ).fetchall()
                if devs:
                    primary_dev = str(devs[0]["device_id"])
                    mobile_dev = str(devs[1]["device_id"]) if len(devs) > 1 else primary_dev

    travel_geo = "SG-Singapore" if home_geo != "SG-Singapore" else "GB-London"
    travel_ip = "116.14.120.48" if travel_geo == "SG-Singapore" else "81.2.69.142"

    return [
        NetworkPresetSchema(
            preset_id="home_trusted",
            label="1. Normal Home / Office Network (Trusted Baseline)",
            description="Sign in from the account's registered home location, trusted IP range, and primary device.",
            ip_address=f"{home_prefix}25",
            geo_location=home_geo,
            device_id=primary_dev,
            device_label="Primary Registered Workstation",
            network_type="home_broadband",
            simulate_failed_attempts=0,
            expected_signal_note="No network anomaly signals (+0 risk points). Routine transfers complete immediately.",
        ),
        NetworkPresetSchema(
            preset_id="legitimate_travel_wifi",
            label="2. Legitimate Travel / Hotel Wi-Fi or VPN (Known Mobile Device)",
            description="Customer traveling in another city using their registered mobile app over hotel Wi-Fi / VPN.",
            ip_address=travel_ip,
            geo_location=travel_geo,
            device_id=mobile_dev,
            device_label="Registered Mobile App",
            network_type="public_wifi",
            simulate_failed_attempts=0,
            expected_signal_note="Moderate unfamiliar-location signal only; does NOT auto-block routine transfers.",
        ),
        NetworkPresetSchema(
            preset_id="suspicious_new_device_ato",
            label="3. Unfamiliar Location + Unseen Device + Failed Logins (ATO Scenario)",
            description="Simulates an account takeover session from NL-Amsterdam on an unrecognized browser after 3 failed logins.",
            ip_address="185.220.101.44",
            geo_location="NL-Amsterdam",
            device_id="DEV-UNSEEN-BROWSER-99",
            device_label="Unrecognized Headless Browser",
            network_type="commercial_vpn",
            simulate_failed_attempts=3,
            expected_signal_note="Combines multiple signals (new device + foreign IP + failed logins) for step-up verification or hold.",
        ),
        NetworkPresetSchema(
            preset_id="threat_intel_proxy",
            label="4. Flagged Anonymizer / Threat-Intel Proxy IP",
            description="Originates from a simulated high-confidence Tor/botnet exit node indicator (198.51.100.201).",
            ip_address="198.51.100.201",
            geo_location="RO-Bucharest",
            device_id="DEV-UNSEEN-PROXY-77",
            device_label="Unrecognized Proxy Client",
            network_type="anonymizer_proxy",
            simulate_failed_attempts=2,
            expected_signal_note="Triggers active Threat-Intelligence indicator correlation (+25 points) plus session anomalies.",
        ),
    ]
