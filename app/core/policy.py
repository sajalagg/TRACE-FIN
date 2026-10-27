from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

# ---------------------------------------------------------------------------
# Central Documented Transfer & Risk Policy Configuration
# ---------------------------------------------------------------------------
# IMPORTANT DESIGN DISTINCTION:
# Risk scores in TRACE-Fin are deterministic rule-based heuristic scores on a
# 0 to 100 scale. A score of 80 is NOT an "80% probability of fraud."
# All transfers and balances in TRACE-Fin are 100% synthetic for classroom use.
# ---------------------------------------------------------------------------

# Transaction lifecycle statuses persisted in `transactions.status`
TX_STATUS_COMPLETED = "COMPLETED"
TX_STATUS_PENDING_VERIFICATION = "PENDING_VERIFICATION"
TX_STATUS_HELD_HIGH_RISK = "HELD_HIGH_RISK"
TX_STATUS_BLOCKED = "BLOCKED"

VALID_TRANSACTION_STATUSES: Tuple[str, ...] = (
    TX_STATUS_COMPLETED,
    TX_STATUS_PENDING_VERIFICATION,
    TX_STATUS_HELD_HIGH_RISK,
    TX_STATUS_BLOCKED,
)

# Policy decision codes
DECISION_ALLOW = "ALLOW"
DECISION_REQUIRE_VERIFICATION = "REQUIRE_VERIFICATION"
DECISION_HOLD_AND_ADMIN_REVIEW = "HOLD_AND_ADMIN_REVIEW"
DECISION_BLOCK = "BLOCK"

# Central score thresholds governing simulated transfer execution
DEFAULT_MEDIUM_RISK_THRESHOLD: int = 40
DEFAULT_HIGH_RISK_HOLD_THRESHOLD: int = 75
DEFAULT_USER_ALERT_THRESHOLD: int = 60

POLICY_DOCUMENTATION_SUMMARY = (
    "TRACE-Fin Simulated Transfer Policy: "
    "(1) Low Risk (score < min(40, user_threshold)): Transfer is completed immediately and simulated balance is deducted once. "
    "(2) Medium Risk (score >= min(40, user_threshold) and < 75): Transfer is placed in PENDING_VERIFICATION without deducting balance; "
    "can be completed after customer verification or Admin review in the Risk Analysis Lab. "
    "(3) High/Critical Risk (score >= 75): Transfer is placed in HELD_HIGH_RISK without deducting balance; "
    "requires Admin investigation in the Risk Analysis Lab and confirmation with the account owner before completion."
)


def score_to_risk_band(score: int) -> str:
    """Map a 0-100 rule-based score to a severity band ('low', 'medium', 'high', 'critical')."""
    if score >= 85:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


@dataclass(frozen=True)
class TransferPolicyOutcome:
    """Deterministic policy decision for a proposed simulated transfer."""

    risk_score: int
    risk_band: str
    user_alert_threshold: int
    effective_verify_threshold: int
    high_risk_hold_threshold: int
    recommended_decision: str
    resulting_status: str
    requires_user_verification: bool
    requires_admin_release: bool
    deduct_balance_immediately: bool
    policy_rule_applied: str
    plain_language_summary: str


def evaluate_transfer_policy(
    risk_score: int,
    user_alert_threshold: int = DEFAULT_USER_ALERT_THRESHOLD,
    medium_risk_threshold: int = DEFAULT_MEDIUM_RISK_THRESHOLD,
    high_risk_hold_threshold: int = DEFAULT_HIGH_RISK_HOLD_THRESHOLD,
) -> TransferPolicyOutcome:
    """Evaluate a 0-100 rule-based risk score against the central transfer policy.

    - Low Risk (`score < effective_verify_threshold`):
      Approved immediately (`COMPLETED`), simulated balance deducted once.
    - Medium Risk (`effective_verify_threshold <= score < high_risk_hold_threshold`):
      Paused (`PENDING_VERIFICATION`), balance NOT deducted. Customer can confirm/deny in
      Security Alerts, or Admin can release/block after review.
    - High / Critical Risk (`score >= high_risk_hold_threshold`):
      Held (`HELD_HIGH_RISK`), balance NOT deducted. Customer can deny immediately or confirm
      intent, and Admin must complete investigation in the Risk Analysis Lab to release funds.
    """
    bounded_score = max(0, min(100, int(risk_score)))
    band = score_to_risk_band(bounded_score)
    effective_verify = min(int(medium_risk_threshold), int(user_alert_threshold))

    if bounded_score >= high_risk_hold_threshold:
        return TransferPolicyOutcome(
            risk_score=bounded_score,
            risk_band=band,
            user_alert_threshold=user_alert_threshold,
            effective_verify_threshold=effective_verify,
            high_risk_hold_threshold=high_risk_hold_threshold,
            recommended_decision=DECISION_HOLD_AND_ADMIN_REVIEW,
            resulting_status=TX_STATUS_HELD_HIGH_RISK,
            requires_user_verification=True,
            requires_admin_release=True,
            deduct_balance_immediately=False,
            policy_rule_applied=(
                f"HIGH_RISK_HOLD (score {bounded_score}/100 >= hold threshold {high_risk_hold_threshold})"
            ),
            plain_language_summary=(
                f"Simulated transfer placed on security hold (rule-based score: {bounded_score}/100). "
                "Your simulated balance has not been deducted. Please review the alert in Security Alerts; "
                "an administrator will also verify this transfer in the Risk Analysis Lab before completion."
            ),
        )

    if bounded_score >= effective_verify:
        return TransferPolicyOutcome(
            risk_score=bounded_score,
            risk_band=band,
            user_alert_threshold=user_alert_threshold,
            effective_verify_threshold=effective_verify,
            high_risk_hold_threshold=high_risk_hold_threshold,
            recommended_decision=DECISION_REQUIRE_VERIFICATION,
            resulting_status=TX_STATUS_PENDING_VERIFICATION,
            requires_user_verification=True,
            requires_admin_release=False,
            deduct_balance_immediately=False,
            policy_rule_applied=(
                f"STEP_UP_VERIFICATION (score {bounded_score}/100 >= verification threshold {effective_verify})"
            ),
            plain_language_summary=(
                f"Additional verification required before completing this simulated transfer "
                f"(rule-based score: {bounded_score}/100). Your simulated balance has not been deducted yet. "
                "Confirm or deny this activity in Security Alerts, or await administrator verification."
            ),
        )

    return TransferPolicyOutcome(
        risk_score=bounded_score,
        risk_band=band,
        user_alert_threshold=user_alert_threshold,
        effective_verify_threshold=effective_verify,
        high_risk_hold_threshold=high_risk_hold_threshold,
        recommended_decision=DECISION_ALLOW,
        resulting_status=TX_STATUS_COMPLETED,
        requires_user_verification=False,
        requires_admin_release=False,
        deduct_balance_immediately=True,
        policy_rule_applied=(
            f"LOW_RISK_AUTO_ALLOW (score {bounded_score}/100 < verification threshold {effective_verify})"
        ),
        plain_language_summary=(
            f"Simulated transfer completed (rule-based score: {bounded_score}/100 — Low Risk). "
            "This transaction matched normal account patterns and your simulated balance has been updated."
        ),
    )
