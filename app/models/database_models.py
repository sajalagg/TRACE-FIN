from __future__ import annotations

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- 1. Synthetic Users & Financial/Business Profiles (with Demo Auth, Role & Simulated Balance)
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    simulated_balance REAL NOT NULL DEFAULT 10000.0 CHECK (simulated_balance >= 0),
    display_name TEXT NOT NULL,
    account_category TEXT NOT NULL CHECK (account_category IN ('individual', 'business')),
    profile_type TEXT NOT NULL,
    industry_sector TEXT NOT NULL,
    expenditure_model TEXT NOT NULL CHECK (expenditure_model IN ('opex_heavy', 'capex_heavy', 'personal_consumption')),
    net_worth_band TEXT NOT NULL,
    estimated_net_worth REAL NOT NULL CHECK (estimated_net_worth > 0),
    declared_monthly_turnover REAL NOT NULL CHECK (declared_monthly_turnover > 0),
    typical_tx_amount REAL NOT NULL CHECK (typical_tx_amount > 0),
    typical_max_tx_amount REAL NOT NULL CHECK (typical_max_tx_amount > 0),
    expected_monthly_tx_count INTEGER NOT NULL CHECK (expected_monthly_tx_count > 0),
    operating_hours_utc TEXT NOT NULL,
    home_geo_location TEXT NOT NULL,
    home_ip_prefix TEXT NOT NULL DEFAULT '103.21.244.',
    created_at_utc TEXT NOT NULL
);

-- 1B. Login Sessions & Network Intelligence (Server-Side Session Store + Forensic Context)
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('customer', 'admin')),
    ip_address TEXT NOT NULL DEFAULT '127.0.0.1',
    geo_location TEXT NOT NULL DEFAULT 'IN-Mumbai',
    device_id TEXT NOT NULL DEFAULT 'DEV-WEB-SESSION',
    device_label TEXT NOT NULL DEFAULT 'Primary Web Session',
    network_type TEXT NOT NULL DEFAULT 'home_broadband' CHECK (
        network_type IN (
            'home_broadband',
            'corporate_network',
            'public_wifi',
            'commercial_vpn',
            'mobile_roaming',
            'anonymizer_proxy'
        )
    ),
    is_known_ip INTEGER NOT NULL DEFAULT 1 CHECK (is_known_ip IN (0, 1)),
    is_known_device INTEGER NOT NULL DEFAULT 1 CHECK (is_known_device IN (0, 1)),
    is_home_location INTEGER NOT NULL DEFAULT 1 CHECK (is_home_location IN (0, 1)),
    failed_logins_1h INTEGER NOT NULL DEFAULT 0,
    created_at_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL,
    is_revoked INTEGER NOT NULL DEFAULT 0 CHECK (is_revoked IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 1C. Customer Beneficiaries (Paired with `beneficiary_events` for Forensic Correlation)
CREATE TABLE IF NOT EXISTS beneficiaries (
    beneficiary_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    account_reference TEXT NOT NULL,
    beneficiary_category TEXT NOT NULL DEFAULT 'personal_peer',
    beneficiary_industry TEXT NOT NULL DEFAULT 'general_consumer',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (user_id, beneficiary_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 2. Synthetic Transactions (Ground-truth labels stored strictly for Stage 10 evaluation)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    timestamp_utc TEXT NOT NULL,
    beneficiary_id TEXT NOT NULL,
    beneficiary_name TEXT NOT NULL,
    beneficiary_category TEXT NOT NULL,
    beneficiary_industry TEXT NOT NULL,
    device_id TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    geo_location TEXT NOT NULL,
    is_suspicious INTEGER NOT NULL CHECK (is_suspicious IN (0, 1)),
    scenario_label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (
        status IN ('COMPLETED', 'PENDING_VERIFICATION', 'HELD_HIGH_RISK', 'BLOCKED')
    ),
    decision_reason TEXT NOT NULL DEFAULT 'Approved under baseline simulation policy.',
    notes TEXT,
    idempotency_key TEXT UNIQUE,
    balance_deducted INTEGER NOT NULL DEFAULT 1 CHECK (balance_deducted IN (0, 1)),
    session_id TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 3. Authentication Events (Logins and Failed Login Attempts)
CREATE TABLE IF NOT EXISTS authentication_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('login_success', 'login_failure', 'mfa_challenge_failed')),
    ip_address TEXT NOT NULL,
    geo_location TEXT NOT NULL,
    device_id TEXT NOT NULL,
    is_success INTEGER NOT NULL CHECK (is_success IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 4. Device Events (Known Device Registrations vs Unseen Device First-Seen)
CREATE TABLE IF NOT EXISTS device_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    device_id TEXT NOT NULL,
    device_label TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('device_registered', 'new_device_detected', 'device_verified')),
    known_status TEXT NOT NULL CHECK (known_status IN ('known', 'new')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 5. Beneficiary Events (Creation, Verification, and Vendor BEC Bank-Account Updates)
CREATE TABLE IF NOT EXISTS beneficiary_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    beneficiary_id TEXT NOT NULL,
    beneficiary_name TEXT NOT NULL,
    beneficiary_category TEXT NOT NULL,
    beneficiary_industry TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('beneficiary_added', 'beneficiary_verified', 'beneficiary_bank_updated')),
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 6. Simulated Threat-Intelligence Feed (Clearly marked as demo/synthetic indicators)
CREATE TABLE IF NOT EXISTS threat_intelligence (
    indicator TEXT PRIMARY KEY,
    indicator_type TEXT NOT NULL CHECK (indicator_type IN ('ip_address', 'beneficiary_account')),
    source_label TEXT NOT NULL,
    threat_category TEXT NOT NULL,
    confidence_level TEXT NOT NULL CHECK (confidence_level IN ('high', 'medium', 'low')),
    first_seen_utc TEXT NOT NULL,
    last_seen_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL,
    is_demo_indicator INTEGER NOT NULL DEFAULT 1 CHECK (is_demo_indicator = 1),
    description TEXT NOT NULL
);

-- 7. Per-User Alert Policy Preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    risk_threshold INTEGER NOT NULL DEFAULT 60 CHECK (risk_threshold BETWEEN 10 AND 95),
    critical_bypass_threshold INTEGER NOT NULL DEFAULT 85 CHECK (critical_bypass_threshold BETWEEN 50 AND 100),
    timezone_iana TEXT NOT NULL DEFAULT 'UTC',
    quiet_hours_enabled INTEGER NOT NULL DEFAULT 1 CHECK (quiet_hours_enabled IN (0, 1)),
    quiet_hours_start TEXT NOT NULL DEFAULT '22:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '07:00',
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 8. Simulated Verification Requests & User / Admin Responses
CREATE TABLE IF NOT EXISTS verification_requests (
    request_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'awaiting_admin_release', 'confirmed_legitimate', 'denied_suspicious')
    ),
    created_at_utc TEXT NOT NULL,
    responded_at_utc TEXT,
    user_response TEXT CHECK (user_response IN ('approved', 'denied') OR user_response IS NULL),
    response_notes TEXT,
    requires_admin_release INTEGER NOT NULL DEFAULT 0 CHECK (requires_admin_release IN (0, 1)),
    admin_decision TEXT CHECK (admin_decision IN ('approved', 'blocked') OR admin_decision IS NULL),
    admin_id TEXT,
    admin_notes TEXT,
    admin_decided_at_utc TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 9. Incident Register
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    verification_request_id TEXT,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'investigating', 'closed')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    risk_score_at_creation INTEGER NOT NULL,
    scoring_method_used TEXT NOT NULL,
    summary_reason TEXT NOT NULL,
    recommended_actions TEXT NOT NULL,
    evidence_snapshot_json TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL DEFAULT '',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (verification_request_id) REFERENCES verification_requests(request_id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 10. Incident Evidence Links
CREATE TABLE IF NOT EXISTS incident_evidence (
    evidence_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    explanation TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tx_user_time ON transactions(user_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_tx_beneficiary ON transactions(beneficiary_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_tx_status ON transactions(status, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_auth_user_time ON authentication_events(user_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_device_user_time ON device_events(user_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_ben_user_time ON beneficiary_events(user_id, beneficiary_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_beneficiaries_user ON beneficiaries(user_id, created_at_utc);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_ver_tx ON verification_requests(transaction_id);
CREATE INDEX IF NOT EXISTS idx_ver_user_status ON verification_requests(user_id, status);
CREATE INDEX IF NOT EXISTS idx_inc_tx ON incidents(transaction_id);
CREATE INDEX IF NOT EXISTS idx_inc_user_status ON incidents(user_id, status);
CREATE INDEX IF NOT EXISTS idx_inc_ev_incident ON incident_evidence(incident_id);
"""
