from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_db_path
from app.core.database import get_connection, init_db
from app.core.security import hash_password

DEFAULT_SEED = 42
DEFAULT_TOTAL_TRANSACTIONS = 500
DEMO_CUSTOMER_PASSWORD = "DemoUser@123"
DEMO_ADMIN_PASSWORD = "AdminTrace@123"
_DETERMINISTIC_CUSTOMER_SALT = "a1b2c3d4e5f600112233445566778899"
_DETERMINISTIC_ADMIN_SALT = "99887766554433221100f6e5d4c3b2a1"


USER_PROFILES: List[Dict[str, Any]] = [
    {
        "user_id": "USR-001",
        "username": "aarav.sharma",
        "display_name": "Aarav Sharma (University Student)",
        "account_category": "individual",
        "profile_type": "student",
        "industry_sector": "education",
        "expenditure_model": "personal_consumption",
        "net_worth_band": "<₹10K",
        "estimated_net_worth": 4500.0,
        "declared_monthly_turnover": 900.0,
        "typical_tx_amount": 35.0,
        "typical_max_tx_amount": 250.0,
        "expected_monthly_tx_count": 28,
        "operating_hours_utc": "04:00-18:00",
        "home_geo_location": "IN-Mumbai",
        "home_ip_prefix": "103.21.244.",
        "timezone_iana": "Asia/Kolkata",
        "risk_threshold": 55,
        "simulated_balance": 3250.00,
    },
    {
        "user_id": "USR-002",
        "username": "maya.lin",
        "display_name": "Maya Lin (Graduate Researcher)",
        "account_category": "individual",
        "profile_type": "student",
        "industry_sector": "education",
        "expenditure_model": "personal_consumption",
        "net_worth_band": "<₹10K",
        "estimated_net_worth": 6200.0,
        "declared_monthly_turnover": 1100.0,
        "typical_tx_amount": 45.0,
        "typical_max_tx_amount": 300.0,
        "expected_monthly_tx_count": 30,
        "operating_hours_utc": "01:00-15:00",
        "home_geo_location": "SG-Singapore",
        "home_ip_prefix": "116.14.120.",
        "timezone_iana": "Asia/Singapore",
        "risk_threshold": 60,
        "simulated_balance": 4800.00,
    },
    {
        "user_id": "USR-003",
        "username": "rohan.patel",
        "display_name": "Rohan Patel (Salaried Engineer)",
        "account_category": "individual",
        "profile_type": "salaried_individual",
        "industry_sector": "personal_finance",
        "expenditure_model": "personal_consumption",
        "net_worth_band": "₹25K-₹100K",
        "estimated_net_worth": 55000.0,
        "declared_monthly_turnover": 4200.0,
        "typical_tx_amount": 140.0,
        "typical_max_tx_amount": 1200.0,
        "expected_monthly_tx_count": 35,
        "operating_hours_utc": "04:00-17:30",
        "home_geo_location": "IN-Bengaluru",
        "home_ip_prefix": "106.51.72.",
        "timezone_iana": "Asia/Kolkata",
        "risk_threshold": 60,
        "simulated_balance": 18500.00,
    },
    {
        "user_id": "USR-004",
        "username": "elena.rostova",
        "display_name": "Elena Rostova (Senior Analyst)",
        "account_category": "individual",
        "profile_type": "salaried_individual",
        "industry_sector": "personal_finance",
        "expenditure_model": "personal_consumption",
        "net_worth_band": "₹25K-₹100K",
        "estimated_net_worth": 78000.0,
        "declared_monthly_turnover": 5500.0,
        "typical_tx_amount": 180.0,
        "typical_max_tx_amount": 1500.0,
        "expected_monthly_tx_count": 40,
        "operating_hours_utc": "07:30-21:00",
        "home_geo_location": "GB-London",
        "home_ip_prefix": "81.2.69.",
        "timezone_iana": "Europe/London",
        "risk_threshold": 65,
        "simulated_balance": 24600.00,
    },
    {
        "user_id": "USR-005",
        "username": "marcus.vance",
        "display_name": "Marcus Vance (Independent UX Consultant)",
        "account_category": "individual",
        "profile_type": "freelancer",
        "industry_sector": "independent_consulting",
        "expenditure_model": "personal_consumption",
        "net_worth_band": "₹100K-₹250K",
        "estimated_net_worth": 145000.0,
        "declared_monthly_turnover": 9500.0,
        "typical_tx_amount": 420.0,
        "typical_max_tx_amount": 3500.0,
        "expected_monthly_tx_count": 25,
        "operating_hours_utc": "12:00-23:30",
        "home_geo_location": "US-NewYork",
        "home_ip_prefix": "74.125.224.",
        "timezone_iana": "America/New_York",
        "risk_threshold": 60,
        "simulated_balance": 42000.00,
    },
    {
        "user_id": "USR-006",
        "username": "vikram.singhania",
        "display_name": "Vikramaditya Singhania (Private Wealth HNW)",
        "account_category": "individual",
        "profile_type": "high_net_worth",
        "industry_sector": "private_wealth",
        "expenditure_model": "personal_consumption",
        "net_worth_band": ">₹1M",
        "estimated_net_worth": 2400000.0,
        "declared_monthly_turnover": 65000.0,
        "typical_tx_amount": 3200.0,
        "typical_max_tx_amount": 28000.0,
        "expected_monthly_tx_count": 22,
        "operating_hours_utc": "05:00-19:00",
        "home_geo_location": "AE-Dubai",
        "home_ip_prefix": "94.200.14.",
        "timezone_iana": "Asia/Dubai",
        "risk_threshold": 70,
        "simulated_balance": 385000.00,
    },
    {
        "user_id": "USR-007",
        "username": "novamart.retail",
        "display_name": "NovaMart Retail Pvt Ltd (OpEx E-Commerce SME)",
        "account_category": "business",
        "profile_type": "sme_opex_merchant",
        "industry_sector": "retail_ecommerce",
        "expenditure_model": "opex_heavy",
        "net_worth_band": "₹250K-₹1M",
        "estimated_net_worth": 380000.0,
        "declared_monthly_turnover": 52000.0,
        "typical_tx_amount": 850.0,
        "typical_max_tx_amount": 6500.0,
        "expected_monthly_tx_count": 95,
        "operating_hours_utc": "04:00-16:00",
        "home_geo_location": "IN-Mumbai",
        "home_ip_prefix": "103.48.19.",
        "timezone_iana": "Asia/Kolkata",
        "risk_threshold": 60,
        "simulated_balance": 115000.00,
    },
    {
        "user_id": "USR-008",
        "username": "cloudpulse.saas",
        "display_name": "CloudPulse Systems Inc (OpEx SaaS SME)",
        "account_category": "business",
        "profile_type": "sme_opex_merchant",
        "industry_sector": "saas_it_services",
        "expenditure_model": "opex_heavy",
        "net_worth_band": "₹250K-₹1M",
        "estimated_net_worth": 620000.0,
        "declared_monthly_turnover": 75000.0,
        "typical_tx_amount": 1400.0,
        "typical_max_tx_amount": 9000.0,
        "expected_monthly_tx_count": 80,
        "operating_hours_utc": "15:00-02:00",
        "home_geo_location": "US-SanFrancisco",
        "home_ip_prefix": "172.56.21.",
        "timezone_iana": "America/Los_Angeles",
        "risk_threshold": 65,
        "simulated_balance": 168000.00,
    },
    {
        "user_id": "USR-009",
        "username": "saffron.hospitality",
        "display_name": "Saffron Table Hospitality Group (OpEx Restaurant SME)",
        "account_category": "business",
        "profile_type": "sme_opex_merchant",
        "industry_sector": "hospitality",
        "expenditure_model": "opex_heavy",
        "net_worth_band": "₹100K-₹250K",
        "estimated_net_worth": 210000.0,
        "declared_monthly_turnover": 38000.0,
        "typical_tx_amount": 600.0,
        "typical_max_tx_amount": 4200.0,
        "expected_monthly_tx_count": 110,
        "operating_hours_utc": "08:00-20:00",
        "home_geo_location": "GB-London",
        "home_ip_prefix": "86.14.90.",
        "timezone_iana": "Europe/London",
        "risk_threshold": 55,
        "simulated_balance": 74000.00,
    },
    {
        "user_id": "USR-010",
        "username": "apex.forge",
        "display_name": "Apex Forge & Turbines Ltd (CapEx Manufacturing)",
        "account_category": "business",
        "profile_type": "enterprise_capex_firm",
        "industry_sector": "manufacturing_heavy_machinery",
        "expenditure_model": "capex_heavy",
        "net_worth_band": ">₹5M",
        "estimated_net_worth": 6800000.0,
        "declared_monthly_turnover": 420000.0,
        "typical_tx_amount": 24000.0,
        "typical_max_tx_amount": 110000.0,
        "expected_monthly_tx_count": 14,
        "operating_hours_utc": "04:00-14:00",
        "home_geo_location": "IN-Pune",
        "home_ip_prefix": "115.112.44.",
        "timezone_iana": "Asia/Kolkata",
        "risk_threshold": 65,
        "simulated_balance": 920000.00,
    },
    {
        "user_id": "USR-011",
        "username": "terrabuild.infra",
        "display_name": "TerraBuild Civil Infrastructure Corp (CapEx Construction)",
        "account_category": "business",
        "profile_type": "enterprise_capex_firm",
        "industry_sector": "construction_infra",
        "expenditure_model": "capex_heavy",
        "net_worth_band": ">₹5M",
        "estimated_net_worth": 5200000.0,
        "declared_monthly_turnover": 360000.0,
        "typical_tx_amount": 19500.0,
        "typical_max_tx_amount": 95000.0,
        "expected_monthly_tx_count": 12,
        "operating_hours_utc": "05:00-15:00",
        "home_geo_location": "AE-Dubai",
        "home_ip_prefix": "94.202.88.",
        "timezone_iana": "Asia/Dubai",
        "risk_threshold": 65,
        "simulated_balance": 780000.00,
    },
    {
        "user_id": "USR-012",
        "username": "helios.grid",
        "display_name": "Helios Grid & Solar Utilities (CapEx Energy)",
        "account_category": "business",
        "profile_type": "enterprise_capex_firm",
        "industry_sector": "energy_utilities",
        "expenditure_model": "capex_heavy",
        "net_worth_band": ">₹5M",
        "estimated_net_worth": 8500000.0,
        "declared_monthly_turnover": 550000.0,
        "typical_tx_amount": 32000.0,
        "typical_max_tx_amount": 140000.0,
        "expected_monthly_tx_count": 10,
        "operating_hours_utc": "01:00-11:00",
        "home_geo_location": "SG-Singapore",
        "home_ip_prefix": "118.200.55.",
        "timezone_iana": "Asia/Singapore",
        "risk_threshold": 70,
        "simulated_balance": 1250000.00,
    },
]


DEMO_THREAT_INDICATORS: List[Dict[str, Any]] = [
    {
        "indicator": "198.51.100.201",
        "indicator_type": "ip_address",
        "source_label": "SIMULATED_DEMO_FEED_TOR_EXIT",
        "threat_category": "anonymizer_proxy_node",
        "confidence_level": "high",
        "first_seen_utc": "2026-01-10T00:00:00Z",
        "last_seen_utc": "2026-03-20T00:00:00Z",
        "expires_at_utc": "2026-12-31T23:59:59Z",
        "description": "Simulated high-confidence Tor/anonymizer exit node indicator for classroom demo.",
    },
    {
        "indicator": "198.51.100.202",
        "indicator_type": "ip_address",
        "source_label": "SIMULATED_DEMO_FEED_BOTNET_C2",
        "threat_category": "credential_stuffing_botnet",
        "confidence_level": "high",
        "first_seen_utc": "2026-02-01T00:00:00Z",
        "last_seen_utc": "2026-03-22T00:00:00Z",
        "expires_at_utc": "2026-12-31T23:59:59Z",
        "description": "Simulated high-confidence credential-stuffing botnet proxy IP.",
    },
    {
        "indicator": "203.0.113.155",
        "indicator_type": "ip_address",
        "source_label": "SIMULATED_DEMO_FEED_VPN_SUSPECT",
        "threat_category": "bulletproof_hosting_vpn",
        "confidence_level": "medium",
        "first_seen_utc": "2026-02-15T00:00:00Z",
        "last_seen_utc": "2026-03-18T00:00:00Z",
        "expires_at_utc": "2026-12-31T23:59:59Z",
        "description": "Simulated medium-confidence commercial proxy IP used in synthetic ATO scenarios.",
    },
    {
        "indicator": "192.0.2.99",
        "indicator_type": "ip_address",
        "source_label": "SIMULATED_DEMO_FEED_STALE_2025",
        "threat_category": "historical_Residential_reassigned_ip",
        "confidence_level": "low",
        "first_seen_utc": "2025-01-10T00:00:00Z",
        "last_seen_utc": "2025-06-01T00:00:00Z",
        "expires_at_utc": "2025-12-31T23:59:59Z",
        "description": "Simulated EXPIRED indicator (expired end of 2025) to test indicator freshness validation.",
    },
    {
        "indicator": "BEN-MULE-9901",
        "indicator_type": "beneficiary_account",
        "source_label": "SIMULATED_DEMO_CONSORTIUM_MULE_LIST",
        "threat_category": "suspected_drop_beneficiary",
        "confidence_level": "high",
        "first_seen_utc": "2026-02-20T00:00:00Z",
        "last_seen_utc": "2026-03-25T00:00:00Z",
        "expires_at_utc": "2026-12-31T23:59:59Z",
        "description": "Simulated consortium-flagged mule beneficiary account.",
    },
]


def _fmt_utc(dt: datetime) -> str:
    """Format a datetime as ISO-8601 UTC string (`YYYY-MM-DDTHH:MM:SSZ`)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_vendor_for_user(user: Dict[str, Any], index: int) -> Tuple[str, str, str, str]:
    """Return a realistic established beneficiary (id, name, category, industry) matching the user's sector."""
    sector = user["industry_sector"]
    uid_num = user["user_id"].split("-")[1]
    ben_id = f"BEN-{uid_num}-0{index}"

    if sector == "manufacturing_heavy_machinery":
        names = [
            ("Krupp Steel & Alloys GmbH", "verified_b2b_vendor", "raw_materials_steel_cement"),
            ("Precision CNC Robotics Ltd", "verified_b2b_vendor", "heavy_machinery_equipment"),
            ("Continental Industrial Freight", "verified_b2b_vendor", "logistics_freight"),
        ]
    elif sector == "construction_infra":
        names = [
            ("Titan Cement & Aggregates Corp", "verified_b2b_vendor", "raw_materials_steel_cement"),
            ("Atlas Earthmoving Equipment", "verified_b2b_vendor", "heavy_machinery_equipment"),
            ("Metro Structural Engineering", "verified_b2b_vendor", "construction_subcontractor"),
        ]
    elif sector == "energy_utilities":
        names = [
            ("Solaris Photovoltaic Modules", "verified_b2b_vendor", "heavy_machinery_equipment"),
            ("HighVolt Transformer Works", "verified_b2b_vendor", "heavy_machinery_equipment"),
            ("GridLine Maintenance Partners", "verified_b2b_vendor", "construction_subcontractor"),
        ]
    elif sector == "retail_ecommerce":
        names = [
            ("Global FMCG Wholesale Distributors", "verified_b2b_vendor", "wholesale_fmcg_inventory"),
            ("SwiftShip Last-Mile Logistics", "verified_b2b_vendor", "logistics_freight"),
            ("NovaMart Monthly Payroll Pool", "employee_payroll", "payroll_settlement"),
        ]
    elif sector == "saas_it_services":
        names = [
            ("HyperScale Cloud Hosting Services", "verified_b2b_vendor", "cloud_saas_hosting"),
            ("DevSecOps License Partner", "verified_b2b_vendor", "cloud_saas_hosting"),
            ("CloudPulse Engineering Payroll", "employee_payroll", "payroll_settlement"),
        ]
    elif sector == "hospitality":
        names = [
            ("FreshHarvest Food & Beverage Supply", "verified_b2b_vendor", "wholesale_fmcg_inventory"),
            ("City Commercial Kitchen Utilities", "utility_tax", "utilities_municipal"),
            ("Saffron Table Staff Payroll", "employee_payroll", "payroll_settlement"),
        ]
    elif sector == "private_wealth":
        names = [
            ("Meridian Sovereign Wealth Advisory", "financial_brokerage", "wealth_management"),
            ("Grand Heritage Luxury Aviation", "verified_b2b_vendor", "luxury_travel_hospitality"),
            ("Alpine Private Estate Services", "verified_b2b_vendor", "property_management"),
        ]
    else:
        names = [
            ("Metro City Electricity & Broadband", "utility_tax", "utilities_municipal"),
            ("Everyday Supermarket & Groceries", "verified_b2b_vendor", "general_consumer"),
            ("Trusted Family Savings Transfer", "personal_peer", "general_consumer"),
        ]

    name, category, industry = names[(index - 1) % len(names)]
    return ben_id, name, category, industry


def _in_operating_hour(user: Dict[str, Any], rng: random.Random) -> int:
    """Pick an hour (0-23 UTC) inside the user's normal operating window."""
    start_s, end_s = user["operating_hours_utc"].split("-")
    start_h = int(start_s.split(":")[0])
    end_h = int(end_s.split(":")[0])
    if start_h <= end_h:
        return rng.randint(start_h, max(start_h, end_h - 1))
    hours = list(range(start_h, 24)) + list(range(0, end_h))
    return rng.choice(hours)


def _off_operating_hour(user: Dict[str, Any], rng: random.Random) -> int:
    """Pick an hour (0-23 UTC) outside the user's declared operating window."""
    start_s, end_s = user["operating_hours_utc"].split("-")
    start_h = int(start_s.split(":")[0])
    end_h = int(end_s.split(":")[0])
    if start_h <= end_h:
        inside = set(range(start_h, end_h + 1))
    else:
        inside = set(range(start_h, 24)) | set(range(0, end_h + 1))
    outside = [h for h in range(24) if h not in inside]
    return rng.choice(outside) if outside else 3


def seed_database(
    db_path: Optional[Path] = None,
    total_transactions: int = DEFAULT_TOTAL_TRANSACTIONS,
    seed: int = DEFAULT_SEED,
) -> Dict[str, int]:
    """Reset and populate the SQLite database with deterministic synthetic records.

    Re-running this function clears existing rows and inserts the exact same dataset
    for a given `seed` and `total_transactions`.
    """
    init_db(db_path)
    rng = random.Random(seed)

    base_created = datetime(2026, 1, 1, 8, 0, 0)
    sim_start = datetime(2026, 3, 1, 0, 0, 0)

    with get_connection(db_path) as conn:
        # Clear existing tables in reverse dependency order so seeding is idempotent
        for table in [
            "incident_evidence",
            "incidents",
            "verification_requests",
            "user_sessions",
            "beneficiaries",
            "user_preferences",
            "beneficiary_events",
            "device_events",
            "authentication_events",
            "transactions",
            "threat_intelligence",
            "users",
        ]:
            conn.execute(f"DELETE FROM {table};")

        # 1. Insert Users, Preferences, Baseline Devices, and Established Beneficiaries
        user_known_devices: Dict[str, List[str]] = {}
        user_known_bens: Dict[str, List[Tuple[str, str, str, str]]] = {}

        device_seq = 1
        ben_event_seq = 1
        auth_seq = 1
        customer_pw_hash = hash_password(DEMO_CUSTOMER_PASSWORD, salt_hex=_DETERMINISTIC_CUSTOMER_SALT)
        admin_pw_hash = hash_password(DEMO_ADMIN_PASSWORD, salt_hex=_DETERMINISTIC_ADMIN_SALT)

        for u in USER_PROFILES:
            uid = u["user_id"]
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
                ) VALUES (?, ?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    u["username"],
                    customer_pw_hash,
                    float(u["simulated_balance"]),
                    u["display_name"],
                    u["account_category"],
                    u["profile_type"],
                    u["industry_sector"],
                    u["expenditure_model"],
                    u["net_worth_band"],
                    u["estimated_net_worth"],
                    u["declared_monthly_turnover"],
                    u["typical_tx_amount"],
                    u["typical_max_tx_amount"],
                    u["expected_monthly_tx_count"],
                    u["operating_hours_utc"],
                    u["home_geo_location"],
                    u["home_ip_prefix"],
                    _fmt_utc(base_created),
                ),
            )

            conn.execute(
                """
                INSERT INTO user_preferences (
                    user_id, risk_threshold, critical_bypass_threshold,
                    timezone_iana, quiet_hours_enabled, quiet_hours_start,
                    quiet_hours_end, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    u["risk_threshold"],
                    85,
                    u["timezone_iana"],
                    1,
                    "22:00",
                    "07:00",
                    _fmt_utc(base_created),
                ),
            )

            # Register 2 known baseline devices per user in Jan 2026
            uid_num = uid.split("-")[1]
            dev1 = f"DEV-{uid_num}-PRIMARY"
            dev2 = f"DEV-{uid_num}-SECONDARY"
            user_known_devices[uid] = [dev1, dev2]

            for d_idx, dev_id in enumerate([dev1, dev2], start=1):
                conn.execute(
                    """
                    INSERT INTO device_events (
                        event_id, user_id, timestamp_utc, device_id,
                        device_label, event_type, known_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"DEV-EVT-{device_seq:04d}",
                        uid,
                        _fmt_utc(base_created + timedelta(hours=d_idx)),
                        dev_id,
                        "Primary Corporate/Personal Workstation" if d_idx == 1 else "Registered Mobile App",
                        "device_registered",
                        "known",
                    ),
                )
                device_seq += 1

            # Register 3 established beneficiaries per user in Jan 2026
            user_known_bens[uid] = []
            for b_idx in range(1, 4):
                ben_tuple = _default_vendor_for_user(u, b_idx)
                user_known_bens[uid].append(ben_tuple)
                ben_id, ben_name, ben_cat, ben_ind = ben_tuple
                ben_created = _fmt_utc(base_created + timedelta(days=b_idx))
                acct_ref = f"SIM-ACCT-{uid_num}-0{b_idx}99"
                conn.execute(
                    """
                    INSERT INTO beneficiaries (
                        beneficiary_id, user_id, display_name, account_reference,
                        beneficiary_category, beneficiary_industry, status,
                        created_at_utc, updated_at_utc, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (
                        ben_id,
                        uid,
                        ben_name,
                        acct_ref,
                        ben_cat,
                        ben_ind,
                        ben_created,
                        ben_created,
                        "Baseline verified counterparty added during onboarding.",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO beneficiary_events (
                        event_id, user_id, beneficiary_id, beneficiary_name,
                        beneficiary_category, beneficiary_industry,
                        timestamp_utc, event_type, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"BEN-EVT-{ben_event_seq:04d}",
                        uid,
                        ben_id,
                        ben_name,
                        ben_cat,
                        ben_ind,
                        ben_created,
                        "beneficiary_added",
                        "Baseline verified counterparty added during onboarding.",
                    ),
                )
                ben_event_seq += 1

        # 1b. Insert Demo SOC Admin Account (ADMIN-001)
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
            ) VALUES (?, ?, ?, 'admin', 0.0, ?, 'individual', 'salaried_individual',
                      'security_operations', 'personal_consumption', '₹25K-₹100K',
                      50000.0, 4000.0, 100.0, 1000.0, 10, '00:00-23:59', 'IN-Mumbai', '103.21.244.', ?)
            """,
            (
                "ADMIN-001",
                "admin",
                admin_pw_hash,
                "TRACE-Fin SOC Lead Investigator (Admin)",
                _fmt_utc(base_created),
            ),
        )

        # 2. Insert Simulated Threat-Intelligence Feed
        for ti in DEMO_THREAT_INDICATORS:
            conn.execute(
                """
                INSERT INTO threat_intelligence (
                    indicator, indicator_type, source_label, threat_category,
                    confidence_level, first_seen_utc, last_seen_utc,
                    expires_at_utc, is_demo_indicator, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    ti["indicator"],
                    ti["indicator_type"],
                    ti["source_label"],
                    ti["threat_category"],
                    ti["confidence_level"],
                    ti["first_seen_utc"],
                    ti["last_seen_utc"],
                    ti["expires_at_utc"],
                    ti["description"],
                ),
            )

        # 3. Build Scenario Plan for `total_transactions` (default 500)
        # Proportions carefully chosen so all 8 archetypes are well represented:
        # - normal_routine (~56%)
        # - legitimate_capex_high_value (~8%)
        # - legitimate_opex_payroll_cycle (~8%)
        # - legitimate_travel_new_ip (~6%)
        # - low_and_slow_ato (~6%)
        # - b2b_vendor_bec_tamper (~5%)
        # - structured_smurfing_drain (~6%, generated in 3-tx bursts)
        # - threat_intel_active_or_stale_ip (~5%, half active malicious, half expired legitimate)
        capex_users = [u for u in USER_PROFILES if u["expenditure_model"] == "capex_heavy"]
        opex_users = [u for u in USER_PROFILES if u["expenditure_model"] == "opex_heavy"]
        biz_users = capex_users + opex_users

        tx_seq = 1

        def insert_tx(
            user: Dict[str, Any],
            amount: float,
            ts: datetime,
            ben_id: str,
            ben_name: str,
            ben_cat: str,
            ben_ind: str,
            device_id: str,
            ip_addr: str,
            geo: str,
            is_susp: int,
            scenario: str,
        ) -> str:
            nonlocal tx_seq
            tx_id = f"TX-{tx_seq:04d}"
            tx_seq += 1
            conn.execute(
                """
                INSERT INTO transactions (
                    transaction_id, user_id, amount, currency, timestamp_utc,
                    beneficiary_id, beneficiary_name, beneficiary_category,
                    beneficiary_industry, device_id, ip_address, geo_location,
                    is_suspicious, scenario_label
                ) VALUES (?, ?, ?, 'INR', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx_id,
                    user["user_id"],
                    round(amount, 2),
                    _fmt_utc(ts),
                    ben_id,
                    ben_name,
                    ben_cat,
                    ben_ind,
                    device_id,
                    ip_addr,
                    geo,
                    is_susp,
                    scenario,
                ),
            )
            return tx_id

        def insert_auth(
            user_id: str,
            ts: datetime,
            event_type: str,
            ip_addr: str,
            geo: str,
            device_id: str,
            is_success: int,
        ) -> None:
            nonlocal auth_seq
            conn.execute(
                """
                INSERT INTO authentication_events (
                    event_id, user_id, timestamp_utc, event_type,
                    ip_address, geo_location, device_id, is_success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"AUTH-EVT-{auth_seq:04d}",
                    user_id,
                    _fmt_utc(ts),
                    event_type,
                    ip_addr,
                    geo,
                    device_id,
                    is_success,
                ),
            )
            auth_seq += 1

        def insert_dev_event(
            user_id: str,
            ts: datetime,
            device_id: str,
            label: str,
            event_type: str,
            known_status: str,
        ) -> None:
            nonlocal device_seq
            conn.execute(
                """
                INSERT INTO device_events (
                    event_id, user_id, timestamp_utc, device_id,
                    device_label, event_type, known_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"DEV-EVT-{device_seq:04d}",
                    user_id,
                    _fmt_utc(ts),
                    device_id,
                    label,
                    event_type,
                    known_status,
                ),
            )
            device_seq += 1

        def insert_ben_event(
            user_id: str,
            ben_id: str,
            ben_name: str,
            ben_cat: str,
            ben_ind: str,
            ts: datetime,
            event_type: str,
            notes: str,
        ) -> None:
            nonlocal ben_event_seq
            conn.execute(
                """
                INSERT INTO beneficiary_events (
                    event_id, user_id, beneficiary_id, beneficiary_name,
                    beneficiary_category, beneficiary_industry,
                    timestamp_utc, event_type, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"BEN-EVT-{ben_event_seq:04d}",
                    user_id,
                    ben_id,
                    ben_name,
                    ben_cat,
                    ben_ind,
                    _fmt_utc(ts),
                    event_type,
                    notes,
                ),
            )
            ben_event_seq += 1

        # Allocate exact counts summing to `total_transactions`
        n_smurf_groups = max(2, round(total_transactions * 0.06) // 3)
        n_smurf_tx = n_smurf_groups * 3
        n_capex_legit = max(2, round(total_transactions * 0.08))
        n_opex_payroll = max(2, round(total_transactions * 0.08))
        n_travel_legit = max(2, round(total_transactions * 0.06))
        n_low_slow_ato = max(2, round(total_transactions * 0.06))
        n_bec_tamper = max(2, round(total_transactions * 0.05))
        n_ti_cases = max(2, round(total_transactions * 0.05))
        n_normal = total_transactions - (
            n_smurf_tx
            + n_capex_legit
            + n_opex_payroll
            + n_travel_legit
            + n_low_slow_ato
            + n_bec_tamper
            + n_ti_cases
        )

        # Archetype 1: Normal Routine Activity (Legitimate, is_suspicious = 0)
        for i in range(n_normal):
            u = USER_PROFILES[i % len(USER_PROFILES)]
            uid = u["user_id"]
            day_offset = rng.randint(1, 24)
            hour = _in_operating_hour(u, rng)
            minute = rng.randint(5, 54)
            ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=minute)

            amount = u["typical_tx_amount"] * rng.uniform(0.45, 1.35)
            dev_id = rng.choice(user_known_devices[uid])
            ip_addr = f"{u['home_ip_prefix']}{rng.randint(10, 90)}"
            ben_id, ben_name, ben_cat, ben_ind = rng.choice(user_known_bens[uid])

            insert_auth(uid, ts - timedelta(minutes=rng.randint(3, 15)), "login_success", ip_addr, u["home_geo_location"], dev_id, 1)
            insert_tx(u, amount, ts, ben_id, ben_name, ben_cat, ben_ind, dev_id, ip_addr, u["home_geo_location"], 0, "normal_routine")

        # Archetype 2: Legitimate High-Value CapEx Equipment/Material Purchase (is_suspicious = 0)
        # Raw amount is huge (₹45k - ₹125k), which trips naive amount rules, but fits CapEx profile,
        # net worth, operating hours, known device, and matching supply-chain vendor.
        for i in range(n_capex_legit):
            u = capex_users[i % len(capex_users)]
            uid = u["user_id"]
            day_offset = rng.randint(2, 22)
            hour = _in_operating_hour(u, rng)
            ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=rng.randint(10, 50))

            amount = u["typical_max_tx_amount"] * rng.uniform(0.55, 0.92)
            dev_id = user_known_devices[uid][0]
            ip_addr = f"{u['home_ip_prefix']}{rng.randint(10, 50)}"
            ben_id, ben_name, ben_cat, ben_ind = user_known_bens[uid][i % 2]

            insert_auth(uid, ts - timedelta(minutes=12), "login_success", ip_addr, u["home_geo_location"], dev_id, 1)
            insert_tx(
                u,
                amount,
                ts,
                ben_id,
                ben_name,
                ben_cat,
                ben_ind,
                dev_id,
                ip_addr,
                u["home_geo_location"],
                0,
                "legitimate_capex_high_value",
            )

        # Archetype 3: Legitimate Month-End OpEx Payroll / Supplier Settlement Cycle (is_suspicious = 0)
        # Occurs on days 25..28 of the month during operating hours to payroll/known suppliers.
        for i in range(n_opex_payroll):
            u = opex_users[i % len(opex_users)]
            uid = u["user_id"]
            day_offset = rng.randint(24, 27)  # March 25 - March 28 (month-end window)
            hour = _in_operating_hour(u, rng)
            ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=rng.randint(5, 55))

            amount = u["typical_max_tx_amount"] * rng.uniform(0.45, 0.82)
            dev_id = user_known_devices[uid][0]
            ip_addr = f"{u['home_ip_prefix']}{rng.randint(15, 60)}"
            ben_id, ben_name, ben_cat, ben_ind = user_known_bens[uid][2]  # Payroll / recurring pool

            insert_auth(uid, ts - timedelta(minutes=8), "login_success", ip_addr, u["home_geo_location"], dev_id, 1)
            insert_tx(
                u,
                amount,
                ts,
                ben_id,
                ben_name,
                ben_cat,
                ben_ind,
                dev_id,
                ip_addr,
                u["home_geo_location"],
                0,
                "legitimate_opex_payroll_cycle",
            )

        # Archetype 4: Legitimate Travel with Known Device & Established Beneficiary (is_suspicious = 0)
        travel_geos = [
            ("FR-Paris", "90.84.12."),
            ("JP-Tokyo", "126.15.44."),
            ("DE-Frankfurt", "80.187.10."),
        ]
        for i in range(n_travel_legit):
            u = USER_PROFILES[i % len(USER_PROFILES)]
            uid = u["user_id"]
            day_offset = rng.randint(3, 23)
            hour = _in_operating_hour(u, rng)
            ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=rng.randint(10, 48))

            travel_geo, ip_prefix = travel_geos[i % len(travel_geos)]
            ip_addr = f"{ip_prefix}{rng.randint(20, 120)}"
            dev_id = user_known_devices[uid][1]  # Known registered mobile app
            ben_id, ben_name, ben_cat, ben_ind = user_known_bens[uid][0]
            amount = u["typical_tx_amount"] * rng.uniform(0.6, 1.25)

            # Previous login from home was >24h ago so geo-velocity is physically plausible
            insert_auth(uid, ts - timedelta(minutes=10), "login_success", ip_addr, travel_geo, dev_id, 1)
            insert_tx(
                u,
                amount,
                ts,
                ben_id,
                ben_name,
                ben_cat,
                ben_ind,
                dev_id,
                ip_addr,
                travel_geo,
                0,
                "legitimate_travel_new_ip",
            )

        # Archetype 5: Low-and-Slow Account Takeover (Suspicious, is_suspicious = 1)
        # Amount is intentionally modest (under `typical_max_tx_amount` so baseline misses it!),
        # but preceded by:
        # - Legitimate home login 20 mins earlier -> then impossible travel to foreign IP
        # - 3-4 failed logins
        # - Login from unseen device
        # - Newly added unverified personal peer beneficiary 4 mins before transfer
        attacker_geos = [
            ("NL-Amsterdam", "185.220.101."),
            ("RO-Bucharest", "89.38.99."),
            ("RU-Novosibirsk", "95.181.20."),
        ]
        for i in range(n_low_slow_ato):
            u = USER_PROFILES[i % len(USER_PROFILES)]
            uid = u["user_id"]
            day_offset = rng.randint(2, 23)
            hour = _off_operating_hour(u, rng)
            ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=30)

            att_geo, att_ip_prefix = attacker_geos[i % len(attacker_geos)]
            att_ip = f"{att_ip_prefix}{rng.randint(10, 99)}"
            unseen_dev = f"DEV-UNSEEN-ATO-{i + 1:03d}"
            new_ben_id = f"BEN-ATO-NEW-{i + 1:03d}"
            new_ben_name = f"Unverified Instant Wallet #{i + 1}"

            # 1) Legitimate login at home 18 minutes before attack (triggers impossible travel!)
            home_ip = f"{u['home_ip_prefix']}25"
            insert_auth(uid, ts - timedelta(minutes=18), "login_success", home_ip, u["home_geo_location"], user_known_devices[uid][0], 1)

            # 2) 3 brute-force login failures from attacker IP/device
            for f_idx in range(3):
                insert_auth(
                    uid,
                    ts - timedelta(minutes=12 - f_idx * 2),
                    "login_failure",
                    att_ip,
                    att_geo,
                    unseen_dev,
                    0,
                )

            # 3) Successful login + new device detected
            insert_auth(uid, ts - timedelta(minutes=6), "login_success", att_ip, att_geo, unseen_dev, 1)
            insert_dev_event(uid, ts - timedelta(minutes=6), unseen_dev, "Unrecognized Browser / Emulator", "new_device_detected", "new")

            # 4) New beneficiary added 4 minutes before transfer
            insert_ben_event(
                uid,
                new_ben_id,
                new_ben_name,
                "personal_peer",
                "digital_assets_brokerage",
                ts - timedelta(minutes=4),
                "beneficiary_added",
                "Added immediately after new-device login.",
            )

            # 5) Modest transfer (0.55x - 0.85x of typical_max_tx_amount) to evade single-tx baseline
            amount = u["typical_max_tx_amount"] * rng.uniform(0.55, 0.85)
            insert_tx(
                u,
                amount,
                ts,
                new_ben_id,
                new_ben_name,
                "personal_peer",
                "digital_assets_brokerage",
                unseen_dev,
                att_ip,
                att_geo,
                1,
                "low_and_slow_ato",
            )

        # Archetype 6: B2B Vendor Business Email Compromise / Bank-Detail Tamper (Suspicious, is_suspicious = 1)
        # Uses an EXISTING trusted B2B supplier, normal CapEx/OpEx amount, and normal hours,
        # BUT `beneficiary_bank_updated` occurs 14 minutes before the wire!
        for i in range(n_bec_tamper):
            u = biz_users[i % len(biz_users)]
            uid = u["user_id"]
            day_offset = rng.randint(4, 21)
            hour = _in_operating_hour(u, rng)
            ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=25)

            ben_id, ben_name, ben_cat, ben_ind = user_known_bens[uid][0]
            dev_id = user_known_devices[uid][0]
            ip_addr = f"{u['home_ip_prefix']}{rng.randint(30, 80)}"

            insert_auth(uid, ts - timedelta(minutes=20), "login_success", ip_addr, u["home_geo_location"], dev_id, 1)
            insert_ben_event(
                uid,
                ben_id,
                ben_name,
                ben_cat,
                ben_ind,
                ts - timedelta(minutes=14),
                "beneficiary_bank_updated",
                "Urgent bank routing/IBAN modification requested prior to invoice settlement.",
            )

            amount = u["typical_max_tx_amount"] * rng.uniform(0.65, 0.95)
            insert_tx(
                u,
                amount,
                ts,
                ben_id,
                ben_name,
                ben_cat,
                ben_ind,
                dev_id,
                ip_addr,
                u["home_geo_location"],
                1,
                "b2b_vendor_bec_tamper",
            )

        # Archetype 7: Structured "Smurfing" Drain & Cross-User Mule Convergence (Suspicious, is_suspicious = 1)
        # 3 rapid transfers within 35 minutes, each just under `typical_max_tx_amount` (0.78x - 0.90x),
        # so cumulative 24h outflow is ~2.5x the single-tx limit! Also uses shared mule account `BEN-MULE-9901`
        # across multiple users so cross-user mule convergence is demonstrable.
        shared_mule_id = "BEN-MULE-9901"
        shared_mule_name = "RapidClear Drop Account LLC"
        for g_idx in range(n_smurf_groups):
            u = USER_PROFILES[(g_idx * 2) % len(USER_PROFILES)]
            uid = u["user_id"]
            day_offset = rng.randint(10, 11)  # Clustered within 48h so cross-user convergence triggers
            hour = _off_operating_hour(u, rng)
            base_ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=10)

            unseen_dev = f"DEV-SMURF-{g_idx + 1:03d}"
            ip_addr = f"198.51.100.{10 + g_idx}"

            insert_auth(uid, base_ts - timedelta(minutes=15), "login_failure", ip_addr, "NL-Amsterdam", unseen_dev, 0)
            insert_auth(uid, base_ts - timedelta(minutes=12), "login_success", ip_addr, "NL-Amsterdam", unseen_dev, 1)
            insert_dev_event(uid, base_ts - timedelta(minutes=12), unseen_dev, "Unverified Headless Client", "new_device_detected", "new")
            insert_ben_event(
                uid,
                shared_mule_id,
                shared_mule_name,
                "personal_peer",
                "luxury_retail_jewelry",
                base_ts - timedelta(minutes=8),
                "beneficiary_added",
                "Unverified beneficiary linked across multiple accounts.",
            )

            for leg in range(3):
                leg_ts = base_ts + timedelta(minutes=leg * 11)
                leg_amount = u["typical_max_tx_amount"] * rng.uniform(0.78, 0.91)
                insert_tx(
                    u,
                    leg_amount,
                    leg_ts,
                    shared_mule_id,
                    shared_mule_name,
                    "personal_peer",
                    "luxury_retail_jewelry",
                    unseen_dev,
                    ip_addr,
                    "NL-Amsterdam",
                    1,
                    "structured_smurfing_drain",
                )

        # Archetype 8: Threat-Intelligence Indicator Matches (Half Active Malicious [1], Half Stale/Expired [0])
        active_ti_ips = ["198.51.100.201", "198.51.100.202", "203.0.113.155"]
        stale_ti_ip = "192.0.2.99"  # Expired on 2025-12-31, whereas transactions occur in March 2026

        for i in range(n_ti_cases):
            u = USER_PROFILES[(i + 3) % len(USER_PROFILES)]
            uid = u["user_id"]
            day_offset = rng.randint(5, 24)

            if i % 2 == 0:
                # Active threat-intelligence match: stealthy session replay using known device
                # (so contextual alone scores ~50, below threshold, and active Threat-Intel pushes it to 70-80!)
                hour = _off_operating_hour(u, rng)
                ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=15)
                ti_ip = active_ti_ips[i % len(active_ti_ips)]
                dev_id = user_known_devices[uid][0]
                ben_id = f"BEN-TI-DROP-{i + 1:03d}"
                ben_name = f"Offshore Escrow Exchange #{i + 1}"

                insert_auth(uid, ts - timedelta(minutes=7), "login_success", ti_ip, u["home_geo_location"], dev_id, 1)
                insert_ben_event(
                    uid,
                    ben_id,
                    ben_name,
                    "financial_brokerage",
                    "digital_assets_brokerage",
                    ts - timedelta(minutes=4),
                    "beneficiary_added",
                    "Created during session originating from demo threat-intel flagged IP.",
                )

                amount = u["typical_tx_amount"] * rng.uniform(1.05, 1.40)
                insert_tx(
                    u,
                    amount,
                    ts,
                    ben_id,
                    ben_name,
                    "financial_brokerage",
                    "digital_assets_brokerage",
                    dev_id,
                    ti_ip,
                    u["home_geo_location"],
                    1,
                    "threat_intel_active_or_stale_ip",
                )
            else:
                # Stale/Expired threat-intel indicator used during a completely normal transaction (is_suspicious = 0)
                hour = _in_operating_hour(u, rng)
                ts = sim_start + timedelta(days=day_offset, hours=hour, minutes=20)
                dev_id = user_known_devices[uid][0]
                ben_id, ben_name, ben_cat, ben_ind = user_known_bens[uid][0]
                amount = u["typical_tx_amount"] * rng.uniform(0.7, 1.1)

                insert_auth(uid, ts - timedelta(minutes=6), "login_success", stale_ti_ip, u["home_geo_location"], dev_id, 1)
                insert_tx(
                    u,
                    amount,
                    ts,
                    ben_id,
                    ben_name,
                    ben_cat,
                    ben_ind,
                    dev_id,
                    stale_ti_ip,
                    u["home_geo_location"],
                    0,
                    "threat_intel_active_or_stale_ip",
                )

        conn.commit()

    return get_database_summary(db_path)


def get_database_summary(db_path: Optional[Path] = None) -> Dict[str, int]:
    """Return row counts for all TRACE-Fin tables (`users` counts customer accounts)."""
    tables = [
        "transactions",
        "authentication_events",
        "device_events",
        "beneficiary_events",
        "beneficiaries",
        "threat_intelligence",
        "user_preferences",
        "verification_requests",
        "incidents",
        "incident_evidence",
    ]
    counts: Dict[str, int] = {}
    with get_connection(db_path) as conn:
        user_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE COALESCE(role, 'customer') = 'customer';"
        ).fetchone()
        counts["users"] = int(user_row["cnt"])
        for t in tables:
            row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {t};").fetchone()
            counts[t] = int(row["cnt"])
    return counts


def print_inspection_report(db_path: Optional[Path] = None) -> None:
    """Print a human-readable summary of the SQLite database for debugging and class demos."""
    target = db_path or get_db_path()
    summary = get_database_summary(target)

    print("=" * 72)
    print(f"TRACE-Fin SQLite Inspection Report ({target})")
    print("=" * 72)
    print("\n1. Table Row Counts:")
    for table, count in summary.items():
        print(f"   - {table:<24}: {count}")

    with get_connection(target) as conn:
        print("\n2. Synthetic User Profiles (OpEx / CapEx / Personal + Net Worth):")
        users = conn.execute(
            """
            SELECT user_id, profile_type, industry_sector, expenditure_model,
                   net_worth_band, typical_max_tx_amount
            FROM users
            ORDER BY user_id;
            """
        ).fetchall()
        for u in users:
            print(
                f"   - {u['user_id']} | {u['profile_type']:<21} | {u['expenditure_model']:<20} | "
                f"NW: {u['net_worth_band']:<10} | MaxTx: ₹{u['typical_max_tx_amount']:,.0f}"
            )

        print("\n3. Transaction Scenarios & Ground-Truth Breakdown:")
        scenarios = conn.execute(
            """
            SELECT scenario_label,
                   COUNT(*) AS total,
                   SUM(CASE WHEN is_suspicious = 1 THEN 1 ELSE 0 END) AS suspicious_cnt,
                   SUM(CASE WHEN is_suspicious = 0 THEN 1 ELSE 0 END) AS legitimate_cnt
            FROM transactions
            GROUP BY scenario_label
            ORDER BY total DESC;
            """
        ).fetchall()
        for s in scenarios:
            print(
                f"   - {s['scenario_label']:<32}: {s['total']:>3} total "
                f"(Suspicious={s['suspicious_cnt']}, Legitimate={s['legitimate_cnt']})"
            )

        print("\n4. Sample Linked Forensic Chain (1 Low-and-Slow ATO Transaction):")
        sample_tx = conn.execute(
            """
            SELECT transaction_id, user_id, amount, timestamp_utc,
                   beneficiary_id, device_id, ip_address, geo_location
            FROM transactions
            WHERE scenario_label = 'low_and_slow_ato'
            ORDER BY transaction_id
            LIMIT 1;
            """
        ).fetchone()
        if sample_tx:
            print(
                f"   Transaction {sample_tx['transaction_id']} | User={sample_tx['user_id']} | "
                f"Amount=₹{sample_tx['amount']:,.2f} | Time={sample_tx['timestamp_utc']} | "
                f"Dev={sample_tx['device_id']} | Ben={sample_tx['beneficiary_id']} | Geo={sample_tx['geo_location']}"
            )
            auths = conn.execute(
                """
                SELECT event_id, timestamp_utc, event_type, ip_address, geo_location, is_success
                FROM authentication_events
                WHERE user_id = ? AND timestamp_utc <= ?
                ORDER BY timestamp_utc DESC
                LIMIT 5;
                """,
                (sample_tx["user_id"], sample_tx["timestamp_utc"]),
            ).fetchall()
            for a in reversed(auths):
                print(
                    f"     -> Auth {a['event_id']} at {a['timestamp_utc']}: {a['event_type']} "
                    f"(success={a['is_success']}, geo={a['geo_location']}, ip={a['ip_address']})"
                )
    print("=" * 72)


def seed_initial_demo_incidents(db_path: Optional[Path] = None) -> None:
    """Create 3 realistic initial verification requests and SHA-256 incidents for the live UI demo."""
    from app.schemas.api_schemas import (
        IncidentStatusUpdateSchema,
        VerificationRequestCreateSchema,
        VerificationRespondSchema,
    )
    from app.services.incidents import update_incident_status
    from app.services.verification import (
        create_verification_request,
        respond_to_verification_request,
    )

    target = db_path or get_db_path()
    with get_connection(target) as conn:
        ato_tx = conn.execute(
            "SELECT transaction_id FROM transactions WHERE scenario_label = 'low_and_slow_ato' ORDER BY transaction_id ASC LIMIT 1;"
        ).fetchone()
        bec_tx = conn.execute(
            "SELECT transaction_id FROM transactions WHERE scenario_label = 'b2b_vendor_bec_tamper' ORDER BY transaction_id ASC LIMIT 1;"
        ).fetchone()
        struc_tx = conn.execute(
            "SELECT transaction_id FROM transactions WHERE scenario_label = 'structured_smurfing_drain' ORDER BY transaction_id ASC LIMIT 1;"
        ).fetchone()
        capex_tx = conn.execute(
            "SELECT transaction_id FROM transactions WHERE scenario_label = 'legitimate_capex_high_value' ORDER BY transaction_id ASC LIMIT 1;"
        ).fetchone()

    if ato_tx:
        v1 = create_verification_request(
            VerificationRequestCreateSchema(transaction_id=ato_tx["transaction_id"]),
            db_path=target,
        )
        if v1:
            respond_to_verification_request(
                request_id=v1.request_id,
                payload=VerificationRespondSchema(
                    user_response="denied",
                    response_notes="Account holder confirmed they were in Mumbai and did not authorize foreign login or peer transfer.",
                ),
                db_path=target,
            )

    if bec_tx:
        v2 = create_verification_request(
            VerificationRequestCreateSchema(transaction_id=bec_tx["transaction_id"]),
            db_path=target,
        )
        if v2:
            r2 = respond_to_verification_request(
                request_id=v2.request_id,
                payload=VerificationRespondSchema(
                    user_response="denied",
                    response_notes="CFO confirmed supplier IBAN modification email was spoofed (Vendor BEC attack).",
                ),
                db_path=target,
            )
            if r2 and r2.linked_incident_id:
                update_incident_status(
                    incident_id=r2.linked_incident_id,
                    payload=IncidentStatusUpdateSchema(
                        status="investigating",
                        investigator_note="Vendor bank account change froze pending out-of-band callback to supplier treasury.",
                    ),
                    db_path=target,
                )

    if struc_tx:
        v3 = create_verification_request(
            VerificationRequestCreateSchema(transaction_id=struc_tx["transaction_id"]),
            db_path=target,
        )
        if v3:
            respond_to_verification_request(
                request_id=v3.request_id,
                payload=VerificationRespondSchema(
                    user_response="denied",
                    response_notes="Unrecognized rapid burst of split transfers draining operating turnover.",
                ),
                db_path=target,
            )

    if capex_tx:
        # Leave one pending verification request for live triage demonstration
        create_verification_request(
            VerificationRequestCreateSchema(transaction_id=capex_tx["transaction_id"]),
            db_path=target,
        )
        with get_connection(target) as conn:
            conn.execute(
                """
                UPDATE transactions
                SET status = 'PENDING_VERIFICATION',
                    balance_deducted = 0,
                    decision_reason = 'Held pending customer or SOC verification review.'
                WHERE transaction_id = ?;
                """,
                (capex_tx["transaction_id"],),
            )
            conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or inspect the TRACE-Fin synthetic SQLite database.")
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Inspect the existing database without resetting/re-seeding.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_TOTAL_TRANSACTIONS,
        help="Total number of synthetic transactions to generate (default: 500).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed for reproducible generation (default: 42).",
    )
    args = parser.parse_args()

    if not args.inspect_only:
        seed_database(total_transactions=args.count, seed=args.seed)
        seed_initial_demo_incidents()
    print_inspection_report()


if __name__ == "__main__":
    main()
