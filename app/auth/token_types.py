"""Token type detection for M2M and individual OIDC tokens."""

from enum import Enum


class TokenType(Enum):
    """Types of JWT tokens accepted by gharts."""

    M2M_TEAM = "m2m_team"
    """OAuth client_credentials token identified by the standard ``gty`` claim.

    Issued to M2M applications (CI/CD pipelines, automation tools).
    Auth0 sets ``gty="client-credentials"`` on all ``client_credentials``
    grants without requiring a custom Action.  Team resolution is performed
    exclusively via the ``OAuthClient`` table using the ``sub`` claim.
    """

    INDIVIDUAL = "individual"
    """Standard OIDC user token (device flow or SPA authorization code).

    Contains ``email`` / ``sub`` claims. User is looked up in the DB and
    team memberships are fetched from ``user_team_memberships``.
    """


def detect_token_type(claims: dict) -> TokenType:
    """Detect the token type from JWT claims.

    Rules (evaluated in order):
    1. If ``gty`` == ``"client-credentials"`` → :attr:`TokenType.M2M_TEAM`
    2. Otherwise → :attr:`TokenType.INDIVIDUAL`

    The ``gty`` (grant type) claim is set by Auth0 on all tokens and does not
    require a custom Action.  SPA tokens have ``gty="authorization_code"`` or
    no ``gty``; device-flow tokens have ``gty="device_code"``.  Only
    ``client_credentials`` grants produce M2M tokens.

    Args:
        claims: Decoded JWT payload (dict of claims).

    Returns:
        The detected :class:`TokenType`.
    """
    if claims.get("gty") == "client-credentials":
        return TokenType.M2M_TEAM
    return TokenType.INDIVIDUAL
