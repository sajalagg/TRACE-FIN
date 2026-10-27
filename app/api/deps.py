from __future__ import annotations

from typing import Optional, Tuple

from fastapi import Header, HTTPException, status

from app.schemas.api_schemas import LoginSessionSchema, UserProfileSchema
from app.services.auth import get_session_by_token


def extract_raw_token(
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Extract a raw session token from `Authorization: Bearer <token>` or `X-Session-Token`."""
    if authorization and authorization.strip():
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()
    if x_session_token and x_session_token.strip():
        return x_session_token.strip()
    return None


def get_optional_auth_context(
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
) -> Optional[Tuple[UserProfileSchema, LoginSessionSchema]]:
    """Return `(UserProfileSchema, LoginSessionSchema)` if a session token header is provided.

    Raises 401 if a token header is explicitly provided but is invalid, expired, or revoked.
    Returns `None` if no token header was provided.
    """
    raw_token = extract_raw_token(authorization, x_session_token)
    if raw_token is None:
        return None
    ctx = get_session_by_token(raw_token)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked session token. Please sign in again.",
        )
    return ctx


def get_required_auth_context(
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
) -> Tuple[UserProfileSchema, LoginSessionSchema]:
    """Require a valid active session token and return `(UserProfileSchema, LoginSessionSchema)`."""
    raw_token = extract_raw_token(authorization, x_session_token)
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide an Authorization Bearer token or X-Session-Token.",
        )
    ctx = get_session_by_token(raw_token)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked session token. Please sign in again.",
        )
    return ctx


def require_admin_context(
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
) -> Tuple[UserProfileSchema, LoginSessionSchema]:
    """Require an authenticated user with `role == 'admin'`."""
    user, session = get_required_auth_context(authorization, x_session_token)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role is required to perform this action.",
        )
    return user, session


def enforce_resource_ownership(
    auth_ctx: Optional[Tuple[UserProfileSchema, LoginSessionSchema]],
    owner_user_id: str,
    resource_label: str = "resource",
) -> None:
    """Enforce backend ownership: a customer session cannot read or mutate another user's resource."""
    if auth_ctx is None:
        return
    current_user, _ = auth_ctx
    if current_user.role == "admin":
        return
    if current_user.user_id != owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access denied: customer '{current_user.user_id}' cannot access or modify "
                f"{resource_label} belonging to '{owner_user_id}'."
            ),
        )
