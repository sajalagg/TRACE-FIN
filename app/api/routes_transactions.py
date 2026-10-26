from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.api_schemas import (
    RiskComparisonResponseSchema,
    RiskScoreResponseSchema,
    RuleDefinitionSchema,
    TransactionDetailResponseSchema,
    TransactionListResponseSchema,
    TransactionTimelineResponseSchema,
    UserProfileSchema,
)
from app.services.evidence import build_transaction_timeline
from app.services.scoring import (
    VALID_SCORING_METHODS,
    compare_transaction_scores,
    get_rule_catalog,
    score_transaction,
)
from app.services.transactions import (
    get_transaction_detail,
    get_user_by_id,
    list_transactions,
    list_users,
)

router = APIRouter(tags=["transactions", "users", "risk-scoring"])


@router.get("/users", response_model=List[UserProfileSchema])
def get_users_endpoint(
    expenditure_model: Optional[str] = Query(
        default=None,
        description="Optional filter: 'opex_heavy', 'capex_heavy', or 'personal_consumption'",
    ),
    profile_type: Optional[str] = Query(
        default=None,
        description="Optional filter by profile archetype (e.g., 'student', 'sme_opex_merchant', 'enterprise_capex_firm')",
    ),
) -> List[UserProfileSchema]:
    """List synthetic users and their financial/business profiles."""
    return list_users(
        expenditure_model=expenditure_model,
        profile_type=profile_type,
    )


@router.get("/users/{user_id}", response_model=UserProfileSchema)
def get_user_detail_endpoint(user_id: str) -> UserProfileSchema:
    """Retrieve a single synthetic user's financial and business profile by ID."""
    profile = get_user_by_id(user_id=user_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"User '{user_id}' not found.",
        )
    return profile


@router.get("/transactions", response_model=TransactionListResponseSchema)
def get_transactions_endpoint(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of transactions to return (1-500).",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip for pagination.",
    ),
    user_id: Optional[str] = Query(
        default=None,
        description="Filter transactions by sender user_id (e.g., 'USR-010').",
    ),
    profile_type: Optional[str] = Query(
        default=None,
        description="Filter transactions by sender profile_type (e.g., 'enterprise_capex_firm').",
    ),
    expenditure_model: Optional[str] = Query(
        default=None,
        description="Filter transactions by sender expenditure_model ('opex_heavy', 'capex_heavy', 'personal_consumption').",
    ),
    beneficiary_category: Optional[str] = Query(
        default=None,
        description="Filter transactions by counterparty category (e.g., 'verified_b2b_vendor', 'personal_peer').",
    ),
) -> TransactionListResponseSchema:
    """Return a paginated, optionally filtered list of synthetic transactions."""
    return list_transactions(
        limit=limit,
        offset=offset,
        user_id=user_id,
        profile_type=profile_type,
        expenditure_model=expenditure_model,
        beneficiary_category=beneficiary_category,
    )


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionDetailResponseSchema,
)
def get_transaction_detail_endpoint(
    transaction_id: str,
) -> TransactionDetailResponseSchema:
    """Retrieve a single transaction, its sender's financial/business profile, and linked security events."""
    detail = get_transaction_detail(transaction_id=transaction_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return detail


@router.get("/risk/rules", response_model=List[RuleDefinitionSchema])
def get_risk_rules_endpoint() -> List[RuleDefinitionSchema]:
    """Return the complete catalog of documented risk-scoring rules and their maximum weights."""
    return get_rule_catalog()


@router.get(
    "/transactions/{transaction_id}/risk",
    response_model=RiskScoreResponseSchema,
)
def get_transaction_risk_endpoint(
    transaction_id: str,
    method: str = Query(
        default="contextual",
        description="Scoring approach to run: 'baseline', 'contextual', or 'contextual_ti'.",
    ),
) -> RiskScoreResponseSchema:
    """Compute an explainable 0-100 risk score and counterfactual summary for a transaction."""
    if method not in VALID_SCORING_METHODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid scoring method '{method}'. Choose from: {', '.join(VALID_SCORING_METHODS)}.",
        )

    result = score_transaction(transaction_id=transaction_id, method=method)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return result


@router.get(
    "/transactions/{transaction_id}/risk/compare",
    response_model=RiskComparisonResponseSchema,
)
def compare_transaction_risk_endpoint(
    transaction_id: str,
) -> RiskComparisonResponseSchema:
    """Run all three scoring methods on a transaction and return a side-by-side comparison."""
    comparison = compare_transaction_scores(transaction_id=transaction_id)
    if comparison is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return comparison


@router.get(
    "/transactions/{transaction_id}/timeline",
    response_model=TransactionTimelineResponseSchema,
)
def get_transaction_timeline_endpoint(
    transaction_id: str,
) -> TransactionTimelineResponseSchema:
    """Return a unified, chronologically ordered forensic evidence timeline with Kill-Chain tags."""
    timeline = build_transaction_timeline(transaction_id=transaction_id)
    if timeline is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return timeline


