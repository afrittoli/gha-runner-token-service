"""Token type detection for OIDC tokens.

M2M authentication (Proposal B-1) is handled before JWT decoding via the
``gharts_`` prefix in ``app.auth.api_keys``.  ``detect_token_type`` is only
called for JWTs that have already passed signature validation.
"""

from enum import Enum


class TokenType(Enum):
    """Types of bearer tokens accepted by GHARTS."""

    M2M_TEAM = "m2m_team"
    """GHARTS-native opaque API key (``Bearer gharts_…``).

    Issued to M2M clients (CI/CD pipelines, automation tools) via the admin API.
    Validated by bcrypt hash lookup — no JWT involved.
    Team is resolved directly from the ``OAuthClient`` row.
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
    """Detect the token type from decoded JWT claims.

    This function is only called for JWTs (SPA, device flow, impersonation).
    GHARTS-native API keys (M2M_TEAM) are detected earlier by the
    ``gharts_`` bearer prefix and never reach this function.

    Rules (evaluated in order):
    1. If ``is_impersonation`` claim is truthy → :attr:`TokenType.IMPERSONATION`
    2. Otherwise → :attr:`TokenType.INDIVIDUAL`

    Args:
        claims: Decoded JWT payload (dict of claims).

    Returns:
        The detected :class:`TokenType`.
    """
    if claims.get("is_impersonation"):
        return TokenType.IMPERSONATION
    return TokenType.INDIVIDUAL
