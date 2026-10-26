from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.api_schemas import (
    VerificationRequestCreateSchema,
    VerificationRequestSchema,
    VerificationRespondSchema,
)
from app.services.verification import (
    VerificationConflictError,
    create_verification_request,
    get_verification_request_by_id,
    list_verification_requests,
    respond_to_verification_request,
)

router = APIRouter(tags=["verification"])


@router.get("/verification-requests", response_model=List[VerificationRequestSchema])
def get_verification_requests_endpoint(
    status: Optional[str] = Query(
        default=None,
        description="Optional filter: 'pending', 'confirmed_legitimate', or 'denied_suspicious'.",
    ),
    user_id: Optional[str] = Query(
        default=None,
        description="Optional filter by user_id (e.g., 'USR-001').",
    ),
) -> List[VerificationRequestSchema]:
    """List simulated transaction verification requests."""
    return list_verification_requests(status=status, user_id=user_id)


@router.get(
    "/verification-requests/{request_id}",
    response_model=VerificationRequestSchema,
)
def get_verification_request_detail_endpoint(
    request_id: str,
) -> VerificationRequestSchema:
    """Retrieve a single simulated verification request by ID."""
    req = get_verification_request_by_id(request_id=request_id)
    if req is None:
        raise HTTPException(
            status_code=404,
            detail=f"Verification request '{request_id}' not found.",
        )
    return req


@router.post("/verification-requests", response_model=VerificationRequestSchema)
def create_verification_request_endpoint(
    payload: VerificationRequestCreateSchema,
) -> VerificationRequestSchema:
    """Create a pending simulated verification request for a transaction (idempotent against duplicates)."""
    created = create_verification_request(payload=payload)
    if created is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{payload.transaction_id}' not found.",
        )
    return created


@router.post(
    "/verification-requests/{request_id}/respond",
    response_model=VerificationRequestSchema,
)
def respond_verification_request_endpoint(
    request_id: str,
    payload: VerificationRespondSchema,
) -> VerificationRequestSchema:
    """Submit a simulated user verification response ('approved' or 'denied').

    A 'denied' response automatically opens a forensic incident and links all timeline evidence.
    """
    try:
        result = respond_to_verification_request(
            request_id=request_id,
            payload=payload,
        )
    except VerificationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Verification request '{request_id}' not found.",
        )
    return result
