"""FastAPI authentication dependencies."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.api_keys import is_api_key, verify_api_key
from app.auth.oidc import OIDCValidator
from app.auth.token_types import TokenType, detect_token_type
from app.config import Settings, get_settings
from app.database import get_db

if TYPE_CHECKING:
    from app.models import Team, User

logger = structlog.get_logger()

# Use auto_error=False so we can handle missing tokens when OIDC is disabled
security = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Represents an authenticated and authorized user.

    Supports three authentication paths:

    * **Individual** (``token_type == TokenType.INDIVIDUAL``): standard OIDC
      user token. ``db_user`` is populated; team membership is fetched from
      the DB.
    * **M2M team** (``token_type == TokenType.M2M_TEAM``): GHARTS-native
      opaque API key (``Bearer gharts_…``).  ``team`` is populated directly
      from the ``OAuthClient`` row; no JWT validation is performed.
    * **Impersonation** (``token_type == TokenType.IMPERSONATION``): demo
      admin impersonation. Behaves like INDIVIDUAL but token is HS256-signed.
    """

    def __init__(
        self,
        identity: str,
        claims: dict,
        token_type: TokenType = TokenType.INDIVIDUAL,
        db_user: Optional["User"] = None,
        team: Optional["Team"] = None,
    ):
        self.identity = identity
        self.claims = claims
        self.token_type = token_type
        self.email = claims.get("email")
        self.name = claims.get("name")
        self.sub = claims.get("sub")

        # M2M team context (set for TokenType.M2M_TEAM)
        self.team = team
        self.team_name_from_token: Optional[str] = claims.get("team")

        # Database-backed authorization
        # (set for TokenType.INDIVIDUAL / IMPERSONATION)
        self.db_user = db_user
        self.user_id = db_user.id if db_user else None
        self.display_name = (
            db_user.display_name if db_user else self.name or self.identity
        )
        self.is_admin = db_user.is_admin if db_user else False
        self.is_active = db_user.is_active if db_user else True

        # M2M tokens always have full API access (governed by team policy)
        _is_m2m = token_type == TokenType.M2M_TEAM
        self.can_use_jit = db_user.can_use_jit if db_user else _is_m2m

    def __str__(self) -> str:
        return self.identity


def _find_user_by_claims(db: Session, claims: dict) -> Optional["User"]:
    """Find user by email or OIDC sub from token claims.

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


def _find_team_by_name(db: Session, team_name: str) -> Optional["Team"]:
    """Find an active team by name.

    Args:
        db: Database session
        team_name: Team name from JWT claim

    Returns:
        Team if found and active, None otherwise
    """
    from app.models import Team

    return (
        db.query(Team).filter(Team.name == team_name, Team.is_active.is_(True)).first()
    )


async def _authenticate_api_key(token: str, db: Session) -> AuthenticatedUser:
    """Authenticate a GHARTS-native opaque API key.

    Scans all active OAuthClient rows that have a hashed_key set and
    verifies the key via bcrypt.  On success returns an M2M-scoped
    AuthenticatedUser bound to the client's team.

    Args:
        token: Raw bearer token value starting with ``gharts_``.
        db: Database session.

    Returns:
        AuthenticatedUser with M2M_TEAM token type.

    Raises:
        HTTPException: 401 if the key is invalid or not found.
    """
    from app.models import OAuthClient, Team

    # Load all active clients that have a key hash set.
    # In practice there will be O(teams) rows — typically < 100.
    # A dedicated hash index is not used here because bcrypt verification is
    # the bottleneck and cannot be accelerated by indexing the full hash.
    candidates = (
        db.query(OAuthClient)
        .filter(
            OAuthClient.is_active.is_(True),
            OAuthClient.hashed_key.isnot(None),
        )
        .all()
    )

    matched: Optional[OAuthClient] = None
    for candidate in candidates:
        if verify_api_key(token, candidate.hashed_key):
            matched = candidate
            break

    if matched is None:
        logger.warning("api_key_not_matched")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognised API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    team = (
        db.query(Team)
        .filter(Team.id == matched.team_id, Team.is_active.is_(True))
        .first()
    )
    if team is None:
        logger.warning(
            "api_key_team_inactive",
            client_id=matched.client_id,
            team_id=matched.team_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team not found or inactive.",
        )

    # Record usage for audit trail
    matched.last_used_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "api_key_authenticated",
        client_id=matched.client_id,
        team=team.name,
    )
    return AuthenticatedUser(
        identity=f"m2m:{team.name}",
        claims={"client_id": matched.client_id},
        token_type=TokenType.M2M_TEAM,
        team=team,
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Validate token and return an authenticated user.

    Handles three token types:
    - GHARTS API keys (``Bearer gharts_…``): resolves team from OAuthClient table.
    - Individual OIDC tokens: resolves user from DB by email/sub.
    - Impersonation tokens (``is_impersonation`` claim): same as individual.

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
            claims={
                "sub": "dev-user",
                "email": "dev-user@example.com",
            },
            token_type=TokenType.INDIVIDUAL,
        )

    # OIDC is enabled - require credentials
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # --- GHARTS-native API key path (Proposal B-1) ---
    # The gharts_ prefix unambiguously identifies opaque API keys.
    # This check short-circuits JWT validation entirely for M2M clients.
    if is_api_key(token):
        return await _authenticate_api_key(token, db)

    # --- JWT path (SPA / device flow / impersonation) ---
    validator = OIDCValidator(settings)

    # Check if this is an impersonation token (demo feature).
    # Impersonation tokens are signed with HS256 and carry is_impersonation=True.
    try:
        from jose import jwt

        # Peek at claims without verification to detect impersonation tokens.
        unverified_payload = jwt.get_unverified_claims(token)
        if unverified_payload.get("is_impersonation"):
            payload = jwt.decode(
                token,
                "demo-impersonation-secret",  # TODO: Move to settings
                algorithms=["HS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
            )
            logger.info(
                "impersonation_token_validated",
                impersonated_by=payload.get("impersonated_by"),
                target_user=payload.get("email"),
            )
        else:
            # Regular OIDC token - validate normally
            payload = await validator.validate_token(token)
    except Exception as e:
        # If impersonation check fails, try OIDC validation
        logger.debug("impersonation_check_failed", error=str(e))
        payload = await validator.validate_token(token)

    token_type = detect_token_type(payload)

    # --- Individual / impersonation path ---
    identity = validator.get_user_identity(payload)
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
            detail=("User not authorized. Contact administrator to request access."),
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

    return AuthenticatedUser(
        identity=identity,
        claims=payload,
        token_type=token_type,
        db_user=db_user,
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        HTTPBearer(auto_error=False)
    ),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> Optional[AuthenticatedUser]:
    """Optionally validate OIDC token.

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


def require_jit_access(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require access to JIT API.

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
