from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.api_schemas import (
    AlertDecisionResponseSchema,
    UserPreferencesSchema,
    UserPreferencesUpdateSchema,
)
from app.services.alert_policy import (
    evaluate_alert_decision,
    get_user_preferences,
    update_user_preferences,
)
from app.services.scoring import VALID_SCORING_METHODS

router = APIRouter(tags=["alert-preferences"])


@router.get("/preferences/{user_id}", response_model=UserPreferencesSchema)
def get_user_preferences_endpoint(user_id: str) -> UserPreferencesSchema:
    """Retrieve stored alert policy preferences (threshold, timezone, quiet hours) for a user."""
    prefs = get_user_preferences(user_id=user_id)
    if prefs is None:
        raise HTTPException(
            status_code=404,
            detail=f"User '{user_id}' not found.",
        )
    return prefs


@router.put("/preferences/{user_id}", response_model=UserPreferencesSchema)
def update_user_preferences_endpoint(
    user_id: str,
    payload: UserPreferencesUpdateSchema,
) -> UserPreferencesSchema:
    """Update a user's alert threshold, critical bypass level, IANA timezone, or quiet hours."""
    try:
        updated = update_user_preferences(user_id=user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"User '{user_id}' not found.",
        )
    return updated


@router.get(
    "/transactions/{transaction_id}/alert-decision",
    response_model=AlertDecisionResponseSchema,
)
def get_transaction_alert_decision_endpoint(
    transaction_id: str,
    method: str = Query(
        default="contextual",
        description="Scoring approach to evaluate: 'baseline', 'contextual', or 'contextual_ti'.",
    ),
    override_threshold: Optional[int] = Query(
        default=None,
        ge=10,
        le=95,
        description="Optional What-If simulator override for risk_threshold (10-95).",
    ),
    override_critical_bypass: Optional[int] = Query(
        default=None,
        ge=50,
        le=100,
        description="Optional What-If simulator override for critical_bypass_threshold (50-100).",
    ),
    override_timezone: Optional[str] = Query(
        default=None,
        description="Optional What-If simulator override for IANA time zone (e.g., 'Asia/Kolkata').",
    ),
    override_quiet_hours_enabled: Optional[bool] = Query(
        default=None,
        description="Optional What-If simulator override for quiet_hours_enabled.",
    ),
    override_quiet_hours_start: Optional[str] = Query(
        default=None,
        description="Optional What-If simulator override for quiet_hours_start (HH:MM).",
    ),
    override_quiet_hours_end: Optional[str] = Query(
        default=None,
        description="Optional What-If simulator override for quiet_hours_end (HH:MM).",
    ),
) -> AlertDecisionResponseSchema:
    """Evaluate the alert policy decision for a transaction using stored preferences or What-If overrides."""
    if method not in VALID_SCORING_METHODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid scoring method '{method}'. Choose from: {', '.join(VALID_SCORING_METHODS)}.",
        )

    try:
        decision = evaluate_alert_decision(
            transaction_id=transaction_id,
            method=method,
            override_threshold=override_threshold,
            override_critical_bypass=override_critical_bypass,
            override_timezone=override_timezone,
            override_quiet_hours_enabled=override_quiet_hours_enabled,
            override_quiet_hours_start=override_quiet_hours_start,
            override_quiet_hours_end=override_quiet_hours_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return decision
