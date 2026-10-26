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


class UserPreferencesSchema(BaseModel):
    """Schema for a user's stored alert policy preferences."""

    user_id: str
    risk_threshold: int = Field(
        ge=10,
        le=95,
        description="Rule-based risk score threshold (10-95). Not a probability.",
    )
    critical_bypass_threshold: int = Field(
        ge=50,
        le=100,
        description="Critical risk score threshold (50-100) that bypasses quiet hours for immediate review.",
    )
    timezone_iana: str = Field(
        description="IANA time zone identifier (e.g., 'Asia/Kolkata', 'Europe/London', 'America/New_York')."
    )
    quiet_hours_enabled: bool
    quiet_hours_start: str = Field(
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="24-hour local start time in HH:MM format (e.g., '22:00').",
    )
    quiet_hours_end: str = Field(
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="24-hour local end time in HH:MM format (e.g., '07:00').",
    )
    updated_at_utc: str


class UserPreferencesUpdateSchema(BaseModel):
    """Request body schema for updating a user's alert preferences (`PUT /preferences/{user_id}`)."""

    risk_threshold: int = Field(
        ge=10,
        le=95,
        description="Rule-based risk score threshold (10-95). Not a probability.",
    )
    critical_bypass_threshold: int = Field(
        default=85,
        ge=50,
        le=100,
        description="Critical score threshold (50-100) that bypasses quiet hours.",
    )
    timezone_iana: str = Field(
        description="Valid IANA time zone (e.g., 'Asia/Kolkata', 'Europe/London')."
    )
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = Field(
        default="22:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    quiet_hours_end: str = Field(
        default="07:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )


class AlertDecisionResponseSchema(BaseModel):
    """Result of evaluating a transaction's risk score against a user's alert policy."""

    transaction_id: str
    user_id: str
    scoring_method: str
    risk_score: int = Field(
        ge=0,
        le=100,
        description="Underlying rule-based risk score (unchanged by alert preferences).",
    )
    risk_band: str
    applied_preferences: UserPreferencesSchema
    is_what_if_simulation: bool = Field(
        description="True if temporary query-parameter overrides were used instead of stored preferences."
    )
    transaction_timestamp_utc: str
    transaction_local_time: str = Field(
        description="Transaction timestamp converted to the user's configured IANA time zone."
    )
    within_quiet_hours: bool
    exceeds_risk_threshold: bool
    exceeds_critical_bypass: bool
    alert_decision: str = Field(
        description="'NO_ALERT_BELOW_THRESHOLD', 'ALERT_NOW', 'QUEUED_FOR_QUIET_HOURS', or 'ALERT_NOW_CRITICAL_BYPASS'"
    )
    decision_explanation: str
    policy_disclaimer: str


class VerificationRequestCreateSchema(BaseModel):
    """Request body for `POST /verification-requests`."""

    transaction_id: str = Field(description="ID of the transaction to send for user verification (e.g., 'TX-0391').")


class VerificationRespondSchema(BaseModel):
    """Request body for `POST /verification-requests/{request_id}/respond`."""

    user_response: str = Field(
        pattern=r"^(approved|denied)$",
        description="'approved' ('I made this transaction') or 'denied' ('I did not make this transaction').",
    )
    response_notes: Optional[str] = Field(
        default=None,
        description="Optional context note from the simulated user.",
    )


class VerificationRequestSchema(BaseModel):
    """Response schema representing a simulated transaction verification request."""

    request_id: str
    transaction_id: str
    user_id: str
    user_display_name: str
    amount: float
    currency: str
    beneficiary_id: str
    beneficiary_name: str
    status: str = Field(
        description="'pending', 'confirmed_legitimate', or 'denied_suspicious'"
    )
    created_at_utc: str
    responded_at_utc: Optional[str] = None
    user_response: Optional[str] = None
    response_notes: Optional[str] = None
    linked_incident_id: Optional[str] = Field(
        default=None,
        description="Populated when user_response == 'denied' and an incident is created/linked.",
    )
    created_new: bool = Field(
        default=True,
        description="False when returning an existing verification request to prevent duplicates.",
    )


class IncidentEvidenceSchema(BaseModel):
    """Schema for an individual evidence record linked to an incident."""

    evidence_id: str
    incident_id: str
    evidence_type: str
    source_record_id: str = Field(
        description="Original table and primary key reference (e.g., 'authentication_events:AUTH-EVT-0392')."
    )
    timestamp_utc: str
    explanation: str


class EvidenceIntegritySchema(BaseModel):
    """Tamper-evident SHA-256 verification status for an incident's forensic snapshot."""

    stored_sha256: str
    recomputed_sha256: str
    integrity_verified: bool
    verification_message: str


class IncidentSummarySchema(BaseModel):
    """Summary schema for listing incidents (`GET /incidents`)."""

    incident_id: str
    transaction_id: str
    verification_request_id: Optional[str] = None
    user_id: str
    user_display_name: str
    user_profile_type: str
    user_expenditure_model: str
    amount: float
    currency: str
    beneficiary_name: str
    status: str = Field(description="'open', 'investigating', or 'closed'")
    severity: str = Field(description="'low', 'medium', 'high', or 'critical'")
    risk_score_at_creation: int
    scoring_method_used: str
    summary_reason: str
    evidence_sha256: str
    created_at_utc: str
    updated_at_utc: str


class IncidentDetailResponseSchema(BaseModel):
    """Comprehensive detail schema for `GET /incidents/{incident_id}`."""

    incident: IncidentSummarySchema
    recommended_actions: List[str] = Field(
        description="Advisory next steps for the investigator (suggestions only, not automated actions)."
    )
    evidence_integrity: EvidenceIntegritySchema
    transaction: TransactionSummarySchema
    user_profile: UserProfileSchema
    verification_request: Optional[VerificationRequestSchema] = None
    risk_evaluation: RiskScoreResponseSchema
    linked_evidence: List[IncidentEvidenceSchema]


class IncidentStatusUpdateSchema(BaseModel):
    """Request body for `PATCH /incidents/{incident_id}`."""

    status: str = Field(
        pattern=r"^(open|investigating|closed)$",
        description="New lifecycle status: 'open', 'investigating', or 'closed'.",
    )
    investigator_note: Optional[str] = Field(
        default=None,
        description="Optional investigator audit note recorded with the status change.",
    )


class DashboardSummarySchema(BaseModel):
    """Overview KPI metrics and recent activity for the frontend dashboard (`GET /dashboard/summary`)."""

    disclaimer: str
    total_users: int
    users_by_expenditure_model: dict[str, int]
    total_transactions: int
    pending_verifications_count: int
    confirmed_verifications_count: int
    denied_verifications_count: int
    open_incidents_count: int
    investigating_incidents_count: int
    closed_incidents_count: int
    recent_transactions: List[TransactionSummarySchema]


class ConfusionMatrixSchema(BaseModel):
    """Standard binary classification confusion matrix counts."""

    true_positives: int = Field(description="Suspicious transactions correctly flagged (score >= threshold).")
    false_positives: int = Field(description="Legitimate transactions falsely flagged (score >= threshold).")
    true_negatives: int = Field(description="Legitimate transactions correctly unflagged (score < threshold).")
    false_negatives: int = Field(description="Suspicious transactions missed (score < threshold).")


class MethodEvaluationMetricsSchema(BaseModel):
    """Aggregate evaluation metrics for one scoring approach on the synthetic dataset."""

    method: str
    threshold_mode: str = Field(description="'fixed' or 'per_user_preference'")
    fixed_threshold: Optional[int] = None
    total_transactions: int
    total_suspicious_ground_truth: int
    total_legitimate_ground_truth: int
    confusion_matrix: ConfusionMatrixSchema
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    flagged_count: int
    flagged_percentage: float
    ato_scenario_detection_rate: float = Field(
        description="Recall on 'low_and_slow_ato' account-takeover transactions."
    )
    bec_scenario_detection_rate: float = Field(
        description="Recall on 'b2b_vendor_bec_tamper' vendor bank-modification transactions."
    )
    structuring_scenario_detection_rate: float = Field(
        description="Recall on 'structured_smurfing_drain' split-transfer transactions."
    )
    capex_false_positive_rate: float = Field(
        description="False-positive rate on 'legitimate_capex_high_value' corporate CapEx purchases."
    )


class ScenarioBreakdownItemSchema(BaseModel):
    """Per-scenario flagging rates across all three scoring approaches."""

    scenario_label: str
    ground_truth_class: str = Field(description="'suspicious', 'legitimate', or 'mixed'")
    total_cases: int
    suspicious_cases: int
    legitimate_cases: int
    baseline_flagged_count: int
    baseline_flagged_rate: float
    contextual_flagged_count: int
    contextual_flagged_rate: float
    contextual_ti_flagged_count: int
    contextual_ti_flagged_rate: float


class ExpenditureModelBreakdownSchema(BaseModel):
    """Evaluation metrics stratified by user expenditure model (opex_heavy, capex_heavy, personal_consumption)."""

    expenditure_model: str
    total_transactions: int
    baseline_precision: float
    baseline_recall: float
    baseline_f1: float
    baseline_fpr: float
    contextual_precision: float
    contextual_recall: float
    contextual_f1: float
    contextual_fpr: float
    contextual_ti_precision: float
    contextual_ti_recall: float
    contextual_ti_f1: float
    contextual_ti_fpr: float


class ThresholdTradeoffPointSchema(BaseModel):
    """Alert volume and detection metrics at a specific score threshold."""

    threshold: int
    method: str
    flagged_count: int
    flagged_percentage: float
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float


class EvaluationReportResponseSchema(BaseModel):
    """Complete Stage 10 reproducible evaluation report (`GET /evaluation/metrics`)."""

    evaluation_disclaimer: str
    positive_prediction_definition: str
    threshold_evaluated: int
    use_user_preferences_threshold: bool
    methods_comparison: dict[str, MethodEvaluationMetricsSchema]
    per_scenario_breakdown: List[ScenarioBreakdownItemSchema]
    per_expenditure_model_breakdown: List[ExpenditureModelBreakdownSchema]
    threshold_tradeoff_curve: List[ThresholdTradeoffPointSchema]






