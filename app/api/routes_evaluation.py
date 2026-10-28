from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from app.schemas.api_schemas import (
    DashboardSummarySchema,
    EvaluationReportResponseSchema,
    ThreatIndicatorCreateSchema,
)
from app.services.evaluation import (
    add_threat_intelligence_indicator,
    compute_evaluation_report,
    get_dashboard_summary,
    get_full_analytics_dataset,
    get_threat_intelligence_registry,
)

router = APIRouter(tags=["dashboard", "evaluation", "threat-intelligence"])


@router.get("/dashboard/summary", response_model=DashboardSummarySchema)
def get_dashboard_summary_endpoint() -> DashboardSummarySchema:
    """Return top-level KPI counts, expenditure-model breakdown, and 10 most recent transactions."""
    return get_dashboard_summary()


@router.get("/dashboard/dataset", response_model=Dict[str, Any])
def get_dashboard_dataset_endpoint() -> Dict[str, Any]:
    """Return full enriched transaction dataset, 3-method scores, KPIs, and activity series from SQLite."""
    return get_full_analytics_dataset()


@router.get("/threat-intel", response_model=List[Dict[str, Any]])
def get_threat_intel_endpoint() -> List[Dict[str, Any]]:
    """Return all threat-intelligence indicators with freshness validation and linked transactions."""
    return get_threat_intelligence_registry()


@router.post("/threat-intel", status_code=201)
def create_threat_intel_endpoint(payload: ThreatIndicatorCreateSchema) -> Dict[str, Any]:
    """Register a new threat-intelligence indicator into SQLite."""
    return add_threat_intelligence_indicator(
        indicator=payload.indicator,
        indicator_type=payload.indicator_type,
        source_label=payload.source_label,
        threat_category=payload.threat_category,
        confidence_level=payload.confidence_level,
        description=payload.description,
        expires_at_utc=payload.expires_at_utc,
        expires_in_days=payload.expires_in_days,
    )


@router.get("/evaluation/metrics", response_model=EvaluationReportResponseSchema)
def get_evaluation_metrics_endpoint(
    threshold: int = Query(
        default=60,
        ge=10,
        le=95,
        description="Fixed risk-score threshold (10-95) used when use_user_preferences_threshold is False.",
    ),
    use_user_preferences_threshold: bool = Query(
        default=False,
        description="If True, evaluates each transaction against its user's configured risk_threshold.",
    ),
) -> EvaluationReportResponseSchema:
    """Compute live Stage 10 evaluation metrics across all synthetic transactions for all 3 scoring methods."""
    return compute_evaluation_report(
        threshold=threshold,
        use_user_preferences_threshold=use_user_preferences_threshold,
    )

