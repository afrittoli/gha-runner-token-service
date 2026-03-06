"""Token type detection for M2M and individual OIDC tokens."""

from enum import Enum


class TokenType(Enum):
    """Types of JWT tokens accepted by gharts."""

    M2M_TEAM = "m2m_team"
    """OAuth client_credentials token with a 'team' claim.

    Issued to M2M applications (CI/CD pipelines, automation tools).
    Contains a ``team`` claim set by an Auth0 Action from M2M app metadata.
    Bypasses per-user DB lookup — team is resolved directly from the claim.
    """

    INDIVIDUAL = "individual"
    """Standard OIDC user token (device flow or SPA authorization code).

    Contains ``email`` / ``sub`` claims. User is looked up in the DB and
    team memberships are fetched from ``user_team_memberships``.
    """

    IMPERSONATION = "impersonation"
    """Admin impersonation token for demo purposes (HS256).

    Signed with a shared secret. Only valid when issued by an admin via
    the ``POST /api/v1/admin/impersonate/{id}`` endpoint.
    """


def detect_token_type(claims: dict) -> TokenType:
    """Detect the token type from JWT claims.

    Rules (evaluated in order):
    1. If ``is_impersonation`` claim is truthy → :attr:`TokenType.IMPERSONATION`
    2. If ``team`` claim is present (non-empty string) → :attr:`TokenType.M2M_TEAM`
    3. Otherwise → :attr:`TokenType.INDIVIDUAL`

    Args:
        claims: Decoded JWT payload (dict of claims).

    Returns:
        The detected :class:`TokenType`.
    """
    if claims.get("is_impersonation"):
        return TokenType.IMPERSONATION
    if claims.get("team"):
        return TokenType.M2M_TEAM
    return TokenType.INDIVIDUAL
