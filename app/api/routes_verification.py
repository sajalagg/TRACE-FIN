from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import enforce_resource_ownership, get_optional_auth_context
from app.schemas.api_schemas import (
    AdminDecisionResponseSchema,
    AdminTransactionDecisionSchema,
    LoginSessionSchema,
    UserProfileSchema,
    VerificationRequestCreateSchema,
    VerificationRequestSchema,
    VerificationRespondSchema,
)
from app.services.verification import (
    VerificationConflictError,
    admin_decide_transaction,
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
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]] = Depends(get_optional_auth_context),
) -> List[VerificationRequestSchema]:
    """List simulated transaction verification requests."""
    if auth_ctx is not None:
        current_user, _ = auth_ctx
        if current_user.role != "admin":
            if user_id and user_id != current_user.user_id:
                enforce_resource_ownership(auth_ctx, user_id, resource_label="verification requests")
            user_id = current_user.user_id
    return list_verification_requests(status=status, user_id=user_id)


@router.get(
    "/verification-requests/{request_id}",
    response_model=VerificationRequestSchema,
)
def get_verification_request_detail_endpoint(
    request_id: str,
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]] = Depends(get_optional_auth_context),
) -> VerificationRequestSchema:
    """Retrieve a single simulated verification request by ID."""
    req = get_verification_request_by_id(request_id=request_id)
    if req is None:
        raise HTTPException(
            status_code=404,
            detail=f"Verification request '{request_id}' not found.",
        )
    enforce_resource_ownership(auth_ctx, req.user_id, resource_label=f"verification request '{request_id}'")
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
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]] = Depends(get_optional_auth_context),
) -> VerificationRequestSchema:
    """Submit a simulated user verification response ('approved' or 'denied').

    A 'denied' response automatically opens a forensic incident and links all timeline evidence.
    """
    if auth_ctx is not None:
        existing_req = get_verification_request_by_id(request_id=request_id)
        if existing_req is not None:
            enforce_resource_ownership(auth_ctx, existing_req.user_id, resource_label=f"verification request '{request_id}'")
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


@router.post(
    "/transactions/{transaction_id}/admin-decision",
    response_model=AdminDecisionResponseSchema,
)
def admin_decide_transaction_endpoint(
    transaction_id: str,
    payload: AdminTransactionDecisionSchema,
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]] = Depends(get_optional_auth_context),
) -> AdminDecisionResponseSchema:
    """Allow an Administrator in the Risk Analysis Lab to approve/release or block a pending/held transaction."""
    admin_uid = "ADMIN-001"
    if auth_ctx is not None:
        current_user, _ = auth_ctx
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Administrator role is required to release or block transactions in the Risk Analysis Lab.",
            )
        admin_uid = current_user.user_id

    try:
        result = admin_decide_transaction(
            transaction_id=transaction_id,
            payload=payload,
            admin_user_id=admin_uid,
        )
    except VerificationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return result
