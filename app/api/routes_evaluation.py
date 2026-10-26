from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.api_schemas import (
    DashboardSummarySchema,
    EvaluationReportResponseSchema,
)
from app.services.evaluation import (
    compute_evaluation_report,
    get_dashboard_summary,
)

router = APIRouter(tags=["dashboard", "evaluation"])


@router.get("/dashboard/summary", response_model=DashboardSummarySchema)
def get_dashboard_summary_endpoint() -> DashboardSummarySchema:
    """Return top-level KPI counts, expenditure-model breakdown, and 10 most recent transactions."""
    return get_dashboard_summary()


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
