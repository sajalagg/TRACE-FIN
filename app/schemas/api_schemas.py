from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class UserProfileSchema(BaseModel):
    """Schema representing a synthetic user's financial and business profile."""

    user_id: str
    display_name: str
    account_category: str = Field(description="'individual' or 'business'")
    profile_type: str = Field(
        description="Archetype such as 'student', 'salaried_individual', 'sme_opex_merchant', 'enterprise_capex_firm', or 'high_net_worth'"
    )
    industry_sector: str
    expenditure_model: str = Field(
        description="'opex_heavy', 'capex_heavy', or 'personal_consumption'"
    )
    net_worth_band: str
    estimated_net_worth: float
    declared_monthly_turnover: float
    typical_tx_amount: float
    typical_max_tx_amount: float
    expected_monthly_tx_count: int
    operating_hours_utc: str
    home_geo_location: str
    created_at_utc: str


class AuthenticationEventSchema(BaseModel):
    """Schema for an authentication event linked to a user."""

    event_id: str
    user_id: str
    timestamp_utc: str
    event_type: str
    ip_address: str
    geo_location: str
    device_id: str
    is_success: bool


class DeviceEventSchema(BaseModel):
    """Schema for a device registration or unseen-device detection event."""

    event_id: str
    user_id: str
    timestamp_utc: str
    device_id: str
    device_label: str
    event_type: str
    known_status: str


class BeneficiaryEventSchema(BaseModel):
    """Schema for a beneficiary addition, verification, or bank-detail modification event."""

    event_id: str
    user_id: str
    beneficiary_id: str
    beneficiary_name: str
    beneficiary_category: str
    beneficiary_industry: str
    timestamp_utc: str
    event_type: str
    notes: Optional[str] = None


class TransactionSummarySchema(BaseModel):
    """Schema for a single transaction record enriched with sender summary fields."""

    transaction_id: str
    user_id: str
    user_display_name: str
    user_profile_type: str
    user_expenditure_model: str
    amount: float
    currency: str
    timestamp_utc: str
    beneficiary_id: str
    beneficiary_name: str
    beneficiary_category: str
    beneficiary_industry: str
    device_id: str
    ip_address: str
    geo_location: str


class TransactionListResponseSchema(BaseModel):
    """Paginated response schema for `GET /transactions`."""

    total_matching: int
    limit: int
    offset: int
    items: List[TransactionSummarySchema]


class TransactionDetailResponseSchema(BaseModel):
    """Detailed response schema for `GET /transactions/{transaction_id}`."""

    transaction: TransactionSummarySchema
    user_profile: UserProfileSchema
    recent_authentication_events: List[AuthenticationEventSchema]
    device_events: List[DeviceEventSchema]
    beneficiary_events: List[BeneficiaryEventSchema]


class TriggeredRuleSchema(BaseModel):
    """Schema for an individual rule evaluated during risk scoring."""

    rule_id: str
    rule_name: str
    category: str = Field(
        description="Rule category: 'baseline', 'profile', 'counterparty', 'structuring', 'temporal', 'forensic_auth_device', 'telemetry', or 'threat_intel'"
    )
    points_awarded: int = Field(ge=0, le=100)
    max_points: int = Field(ge=0, le=100)
    explanation: str
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="IDs of supporting database records (e.g., AUTH-EVT-..., DEV-EVT-..., BEN-EVT-..., indicator)",
    )


class RiskScoreResponseSchema(BaseModel):
    """Response schema for `GET /transactions/{transaction_id}/risk`."""

    transaction_id: str
    user_id: str
    method: str = Field(description="'baseline', 'contextual', or 'contextual_ti'")
    raw_points_sum: int = Field(ge=0)
    risk_score: int = Field(
        ge=0,
        le=100,
        description="Capped rule-based risk score (0-100). Not a calibrated probability.",
    )
    risk_band: str = Field(description="'low' (0-29), 'medium' (30-59), 'high' (60-84), or 'critical' (85-100)")
    user_alert_threshold: int = Field(
        description="The user's configured risk_threshold from user_preferences (for visual comparison)."
    )
    exceeds_user_threshold: bool
    score_interpretation: str
    triggered_rules: List[TriggeredRuleSchema]
    counterfactual_summary: str


class RiskComparisonResponseSchema(BaseModel):
    """Side-by-side comparison of all three scoring methods for a single transaction."""

    transaction_id: str
    user_id: str
    user_display_name: str
    user_profile_type: str
    user_expenditure_model: str
    amount: float
    user_alert_threshold: int
    baseline: RiskScoreResponseSchema
    contextual: RiskScoreResponseSchema
    contextual_ti: RiskScoreResponseSchema
    delta_contextual_vs_baseline: int
    delta_ti_vs_contextual: int
    context_added_rules: List[TriggeredRuleSchema]
    ti_added_rules: List[TriggeredRuleSchema]
    comparison_narrative: str


class RuleDefinitionSchema(BaseModel):
    """Catalog entry documenting a rule and its maximum weight."""

    rule_id: str
    rule_name: str
    applies_to_methods: List[str]
    category: str
    max_points: int
    description: str


class TimelineEntrySchema(BaseModel):
    """Single chronological entry in a transaction's unified forensic timeline.

    Explicitly separates `recorded_fact` (objective database telemetry) from
    `system_interpretation` (forensic inference and kill-chain phase tag).
    """

    sequence_no: int
    timestamp_utc: str
    event_category: str = Field(
        description="'authentication', 'device', 'beneficiary', 'threat_intelligence', or 'transaction'"
    )
    event_type: str
    source_table: str
    source_record_id: str
    geo_location: Optional[str] = None
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    recorded_fact: str = Field(
        description="Objective statement of what was stored in the source record."
    )
    kill_chain_phase: str = Field(
        description="'RECON_BRUTE_FORCE', 'INITIAL_ACCESS', 'PREPARATION_PERSISTENCE', 'EXFILTRATION_EXECUTION', or 'NORMAL_ACTIVITY'"
    )
    system_interpretation: str = Field(
        description="System forensic interpretation of how this record relates to the transaction."
    )


class TransactionTimelineResponseSchema(BaseModel):
    """Unified chronological evidence timeline for `GET /transactions/{transaction_id}/timeline`."""

    transaction_id: str
    user_id: str
    user_display_name: str
    user_profile_type: str
    user_expenditure_model: str
    target_timestamp_utc: str
    total_events: int
    present_categories: List[str]
    missing_categories: List[str]
    kill_chain_phases_observed: List[str]
    timeline: List[TimelineEntrySchema]


