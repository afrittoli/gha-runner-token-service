"""FastAPI authentication dependencies."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.oidc import OIDCValidator
from app.config import Settings, get_settings
from app.database import get_db

if TYPE_CHECKING:
    from app.models import User

logger = structlog.get_logger()

# Use auto_error=False so we can handle missing tokens when OIDC is disabled
security = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Represents an authenticated and authorized user."""

    def __init__(
        self,
        identity: str,
        claims: dict,
        db_user: Optional["User"] = None,
    ):
        self.identity = identity
        self.claims = claims
        self.email = claims.get("email")
        self.name = claims.get("name")
        self.sub = claims.get("sub")

        # Database-backed authorization
        self.db_user = db_user
        self.user_id = db_user.id if db_user else None
        self.display_name = (
            db_user.display_name if db_user else self.name or self.identity
        )
        self.is_admin = db_user.is_admin if db_user else False
        self.is_active = db_user.is_active if db_user else True
        self.can_use_registration_token = (
            db_user.can_use_registration_token if db_user else True
        )
        self.can_use_jit = db_user.can_use_jit if db_user else True

    def __str__(self) -> str:
        return self.identity


def _find_user_by_claims(db: Session, claims: dict) -> Optional["User"]:
    """
    Find user by email or OIDC sub from token claims.

    Args:
        db: Database session
        claims: Token claims

    Returns:
        User if found, None otherwise
    """
    from sqlalchemy import or_

    from app.models import User

    email = claims.get("email")
    sub = claims.get("sub")

    conditions = []
    if email:
        conditions.append(User.email == email)
    if sub:
        conditions.append(User.oidc_sub == sub)

    if not conditions:
        return None

    return db.query(User).filter(or_(*conditions)).first()


def _count_users(db: Session) -> int:
    """Count total users in the database."""
    from app.models import User

    return db.query(User).count()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """
    Validate OIDC token and verify user exists in database.

    Args:
        credentials: HTTP Bearer token (optional when OIDC is disabled)
        settings: Application settings
        db: Database session

    Returns:
        AuthenticatedUser object with database-backed authorization

    Raises:
        HTTPException: If authentication or authorization fails
    """
    if not settings.enable_oidc_auth:
        # For testing/development: return a mock user without DB check
        return AuthenticatedUser(
            identity="dev-user@example.com",
            claims={"sub": "dev-user", "email": "dev-user@example.com"},
            db_user=None,
        )

    # OIDC is enabled - require credentials
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    validator = OIDCValidator(settings)

    # Validate token
    payload = await validator.validate_token(token)

    # Extract user identity
    identity = validator.get_user_identity(payload)

    # Check if any users exist in the database (bootstrap check)
    user_count = _count_users(db)

    if user_count == 0:
        # Bootstrap mode: no users yet, allow access without DB check
        # This allows the first admin to set up the system
        logger.warning(
            "bootstrap_mode_active",
            reason="no_users_in_database",
            identity=identity,
        )
        return AuthenticatedUser(identity=identity, claims=payload, db_user=None)

    # Find user in database
    db_user = _find_user_by_claims(db, payload)

    if db_user is None:
        logger.warning(
            "user_not_authorized",
            identity=identity,
            email=payload.get("email"),
            sub=payload.get("sub"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized. Contact administrator to request access.",
        )

    if not db_user.is_active:
        logger.warning(
            "user_deactivated",
            identity=identity,
            user_id=db_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # Update last login timestamp
    db_user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return AuthenticatedUser(identity=identity, claims=payload, db_user=db_user)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        HTTPBearer(auto_error=False)
    ),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> Optional[AuthenticatedUser]:
    """
    Optionally validate OIDC token.

    Args:
        credentials: HTTP Bearer token (optional)
        settings: Application settings
        db: Database session

    Returns:
        AuthenticatedUser if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, settings, db)
    except HTTPException:
        return None


def require_registration_token_access(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Require access to registration token API.

    Args:
        user: Authenticated user

    Returns:
        Authenticated user if authorized

    Raises:
        HTTPException: If user doesn't have registration token access
    """
    if not user.can_use_registration_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to registration token API not permitted for this user.",
        )
    return user


def require_jit_access(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Require access to JIT API.

    Args:
        user: Authenticated user

    Returns:
        Authenticated user if authorized

    Raises:
        HTTPException: If user doesn't have JIT access
    """
    if not user.can_use_jit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to JIT API not permitted for this user.",
        )
    return user
