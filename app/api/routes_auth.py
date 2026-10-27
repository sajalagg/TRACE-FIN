from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.deps import (
    enforce_resource_ownership,
    extract_raw_token,
    get_optional_auth_context,
    get_required_auth_context,
)
from app.schemas.api_schemas import (
    AuthLoginSchema,
    AuthRegisterSchema,
    AuthTokenResponseSchema,
    LoginSessionSchema,
    NetworkPresetSchema,
    UserProfileSchema,
)
from app.services.auth import (
    AuthenticationError,
    authenticate_and_create_session,
    get_network_presets_for_user,
    get_session_by_id,
    list_user_sessions,
    logout_session,
    register_customer_account,
)

router = APIRouter(prefix="/auth", tags=["authentication & session intelligence"])


@router.post(
    "/register",
    response_model=AuthTokenResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def post_auth_register(payload: AuthRegisterSchema) -> AuthTokenResponseSchema:
    """Register a new customer account with baseline home IP/location and return an active session."""
    try:
        return register_customer_account(payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/login", response_model=AuthTokenResponseSchema)
def post_auth_login(payload: AuthLoginSchema) -> AuthTokenResponseSchema:
    """Authenticate a customer or admin account and record a login session with network context."""
    try:
        return authenticate_and_create_session(payload=payload)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/logout")
def post_auth_logout(
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
) -> Dict[str, object]:
    """Revoke the caller's active session token."""
    raw_token = extract_raw_token(authorization, x_session_token)
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No session token provided.",
        )
    revoked = logout_session(raw_token)
    return {"status": "logged_out", "revoked": revoked}


@router.get("/me", response_model=AuthTokenResponseSchema)
def get_auth_me(
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
    auth_ctx: Tuple[UserProfileSchema, LoginSessionSchema] = Depends(get_required_auth_context),
) -> AuthTokenResponseSchema:
    """Return the currently authenticated user profile and active login session intelligence."""
    user, session = auth_ctx
    raw_token = extract_raw_token(authorization, x_session_token) or ""
    return AuthTokenResponseSchema(
        session_token=raw_token,
        user=user,
        session=session,
    )


@router.get("/sessions", response_model=List[LoginSessionSchema])
def get_auth_sessions(
    user_id: Optional[str] = Query(
        default=None,
        description="Optional user_id filter (Admins can inspect any user's sessions; customers can only view their own).",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    auth_ctx: Tuple[UserProfileSchema, LoginSessionSchema] = Depends(get_required_auth_context),
) -> List[LoginSessionSchema]:
    """List recent login sessions and network context for the authenticated user (or target user for Admin)."""
    current_user, _ = auth_ctx
    target_uid = user_id or current_user.user_id
    enforce_resource_ownership(auth_ctx, target_uid, resource_label="login sessions")
    return list_user_sessions(user_id=target_uid, limit=limit)


@router.get("/sessions/{session_id}", response_model=LoginSessionSchema)
def get_auth_session_detail(
    session_id: str,
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]] = Depends(get_optional_auth_context),
) -> LoginSessionSchema:
    """Retrieve a single login session's Observed / Simulated / Inferred evidence by `session_id`."""
    session = get_session_by_id(session_id=session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Login session '{session_id}' was not found.",
        )
    enforce_resource_ownership(auth_ctx, session.user_id, resource_label=f"session '{session_id}'")
    return session


@router.get("/network-presets", response_model=List[NetworkPresetSchema])
def get_login_network_presets(
    username: Optional[str] = Query(
        default=None,
        description="Optional username or user_id to tailor the home IP/location baseline preset.",
    ),
) -> List[NetworkPresetSchema]:
    """Return pre-configured login network/location presets for controlled classroom demonstrations."""
    return get_network_presets_for_user(username_or_id=username)
