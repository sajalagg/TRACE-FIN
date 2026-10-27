from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_optional_auth_context
from app.schemas.api_schemas import (
    IncidentDetailResponseSchema,
    IncidentStatusUpdateSchema,
    IncidentSummarySchema,
    LoginSessionSchema,
    UserProfileSchema,
)
from app.services.incidents import (
    get_incident_detail,
    list_incidents,
    update_incident_status,
)

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=List[IncidentSummarySchema])
def get_incidents_endpoint(
    status: Optional[str] = Query(
        default=None,
        description="Optional filter: 'open', 'investigating', or 'closed'.",
    ),
    severity: Optional[str] = Query(
        default=None,
        description="Optional filter: 'low', 'medium', 'high', or 'critical'.",
    ),
    user_id: Optional[str] = Query(
        default=None,
        description="Optional filter by user_id (e.g., 'USR-001').",
    ),
) -> List[IncidentSummarySchema]:
    """List forensic incidents ordered newest first, with optional status/severity/user filters."""
    return list_incidents(status=status, severity=severity, user_id=user_id)


@router.get("/incidents/{incident_id}", response_model=IncidentDetailResponseSchema)
def get_incident_detail_endpoint(
    incident_id: str,
) -> IncidentDetailResponseSchema:
    """Retrieve full incident detail, linked evidence, user profile, and SHA-256 integrity status."""
    detail = get_incident_detail(incident_id=incident_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident '{incident_id}' not found.",
        )
    return detail


@router.patch("/incidents/{incident_id}", response_model=IncidentDetailResponseSchema)
def update_incident_status_endpoint(
    incident_id: str,
    payload: IncidentStatusUpdateSchema,
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]] = Depends(get_optional_auth_context),
) -> IncidentDetailResponseSchema:
    """Update an incident's lifecycle status ('open', 'investigating', 'closed') and optional audit note."""
    if auth_ctx is not None:
        current_user, _ = auth_ctx
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can modify forensic incident status.",
            )
    updated = update_incident_status(incident_id=incident_id, payload=payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident '{incident_id}' not found.",
        )
    return updated
