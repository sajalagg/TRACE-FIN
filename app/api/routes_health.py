from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Schema for the service health-check response."""

    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return service status so callers can verify the backend is running."""
    return HealthResponse(status="ok", service="TRACE-Fin")
