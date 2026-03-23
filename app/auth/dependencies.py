"""FastAPI authentication dependencies."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

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

    Supports two authentication paths:

    * **Individual** (``token_type == TokenType.INDIVIDUAL``): standard OIDC
      user token. ``db_user`` is populated; team membership is fetched from
      the DB.
    * **M2M team** (``token_type == TokenType.M2M_TEAM``): OAuth
      ``client_credentials`` token. ``team`` is resolved from the
      ``OAuthClient`` table via the ``sub`` claim; no per-user DB lookup.
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


async def _get_authenticated_user(
    payload: dict,
    db: Session,
    validator: OIDCValidator,
) -> AuthenticatedUser:
    """Resolve a verified JWT payload into an AuthenticatedUser.

    Shared by the production auth path and the demo-mode impersonation override
    in ``app.demo.auth``.  Callers are responsible for verifying the token
    signature before passing the payload here.

    Args:
        payload: Decoded, verified JWT claims.
        db: Database session.
        validator: OIDCValidator instance (used for identity extraction).

    Returns:
        AuthenticatedUser object with database-backed authorization.

    Raises:
        HTTPException: If authorization fails (user not found, deactivated, etc.)
    """
    token_type = detect_token_type(payload)

    # --- M2M team path ---
    if token_type == TokenType.M2M_TEAM:
        from app.metrics import m2m_auth_requests_total
        from app.models import OAuthClient, Team

        client_sub = payload.get("sub", "")

        # Resolve team via the OAuthClient table using the sub claim.
        oauth_client = (
            db.query(OAuthClient)
            .filter(
                OAuthClient.client_id == client_sub,
                OAuthClient.is_active.is_(True),
            )
            .first()
        )
        if oauth_client is None:
            # Check whether an inactive record exists to give a clearer error.
            inactive = (
                db.query(OAuthClient)
                .filter(OAuthClient.client_id == client_sub)
                .first()
            )
            if inactive is not None:
                logger.warning(
                    "m2m_client_disabled",
                    sub=client_sub,
                    client_record_id=inactive.id,
                )
                m2m_auth_requests_total.labels(result="disabled").inc()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"M2M client '{client_sub}' is disabled. "
                        "Contact an administrator to re-enable it."
                    ),
                )
            logger.warning(
                "m2m_client_not_registered",
                sub=client_sub,
            )
            m2m_auth_requests_total.labels(result="not_registered").inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"M2M client '{client_sub}' is not registered or inactive. "
                    "Register the client ID via the admin API "
                    "(POST /api/v1/admin/oauth-clients) before use."
                ),
            )

        team = (
            db.query(Team)
            .filter(Team.id == oauth_client.team_id, Team.is_active.is_(True))
            .first()
        )
        if team is None:
            logger.warning(
                "m2m_team_not_found",
                sub=client_sub,
                team_id=oauth_client.team_id,
            )
            m2m_auth_requests_total.labels(result="team_not_found").inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Team associated with this M2M client was not found or is "
                    "inactive. Contact an administrator."
                ),
            )

        # Record usage timestamp for the audit trail (blocking — failure raises).
        from app.api.v1.oauth_clients import record_m2m_usage

        record_m2m_usage(db, client_sub)
        m2m_auth_requests_total.labels(result="success").inc()

        logger.info(
            "m2m_token_authenticated",
            team=team.name,
            sub=client_sub,
        )
        return AuthenticatedUser(
            identity=f"m2m:{team.name}",
            claims=payload,
            token_type=token_type,
            team=team,
        )

    # --- Individual path ---
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


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Validate token and return an authenticated user.

    Handles two token types:
    - M2M team tokens (``team`` claim present): resolves team from DB by name.
    - Individual OIDC tokens: resolves user from DB by email/sub.

    Impersonation tokens are a demo-only feature handled by the override in
    ``app.demo.auth`` and are never accepted here.

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
    validator = OIDCValidator(settings)
    payload = await validator.validate_token(token)
    return await _get_authenticated_user(payload, db, validator)


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
