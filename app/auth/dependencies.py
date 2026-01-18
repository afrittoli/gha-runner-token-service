"""FastAPI authentication dependencies."""

from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.oidc import OIDCValidator
from app.config import Settings, get_settings

# Use auto_error=False so we can handle missing tokens when OIDC is disabled
security = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Represents an authenticated user."""

    def __init__(self, identity: str, claims: dict):
        self.identity = identity
        self.claims = claims
        self.email = claims.get("email")
        self.name = claims.get("name")
        self.sub = claims.get("sub")

    def __str__(self) -> str:
        return self.identity


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings)
) -> AuthenticatedUser:
    """
    Validate OIDC token and return authenticated user.

    Args:
        credentials: HTTP Bearer token (optional when OIDC is disabled)
        settings: Application settings

    Returns:
        AuthenticatedUser object

    Raises:
        HTTPException: If authentication fails
    """
    if not settings.enable_oidc_auth:
        # For testing/development: return a mock user
        return AuthenticatedUser(
            identity="dev-user@example.com",
            claims={"sub": "dev-user", "email": "dev-user@example.com"}
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

    return AuthenticatedUser(identity=identity, claims=payload)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        HTTPBearer(auto_error=False)
    ),
    settings: Settings = Depends(get_settings)
) -> Optional[AuthenticatedUser]:
    """
    Optionally validate OIDC token.

    Args:
        credentials: HTTP Bearer token (optional)
        settings: Application settings

    Returns:
        AuthenticatedUser if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, settings)
    except HTTPException:
        return None
