"""Demo-mode authentication with impersonation token support."""

import os
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    AuthenticatedUser,
    _get_authenticated_user,
    security,
)
from app.auth.oidc import OIDCValidator
from app.config import Settings, get_settings
from app.database import get_db

logger = structlog.get_logger()

# Secret used to sign impersonation tokens. Set via env var in demo deployments.
_IMPERSONATION_SECRET = os.environ.get(
    "DEMO_IMPERSONATION_SECRET", "demo-impersonation-secret"
)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """
    Impersonation-aware replacement for get_current_user (demo mode only).

    Checks for impersonation tokens first; falls back to standard OIDC validation.
    This function is injected via FastAPI dependency override in demo_main.py and
    is never present in production container images.
    """
    if not settings.enable_oidc_auth:
        return AuthenticatedUser(
            identity="dev-user@example.com",
            claims={"sub": "dev-user", "email": "dev-user@example.com"},
            db_user=None,
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    validator = OIDCValidator(settings)

    # Check for impersonation token before attempting OIDC validation.
    # Impersonation tokens are HS256-signed and carry is_impersonation=True.
    try:
        from jose import jwt

        unverified_payload = jwt.get_unverified_claims(token)
        if unverified_payload.get("is_impersonation"):
            payload = jwt.decode(
                token,
                _IMPERSONATION_SECRET,
                algorithms=["HS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
            )
            logger.warning(
                "impersonation_token_validated",
                impersonated_by=payload.get("impersonated_by"),
                target_user=payload.get("email"),
            )
            return await _get_authenticated_user(payload, db, validator)
    except Exception:
        pass

    # Regular OIDC token path
    payload = await validator.validate_token(token)
    return await _get_authenticated_user(payload, db, validator)
