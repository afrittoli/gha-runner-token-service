"""Token type detection for M2M and individual OIDC tokens."""

from enum import Enum


class TokenType(Enum):
    """Types of JWT tokens accepted by gharts."""

    M2M_TEAM = "m2m_team"
    """OAuth client_credentials token (gty='client-credentials').

    Issued to M2M applications (CI/CD pipelines, automation tools) by either
    Auth0 or Zitadel.  Team context is resolved from the ``OAuthClient`` table
    using the ``sub`` claim — no custom ``team`` claim is required.
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
    2. If ``gty`` claim equals ``"client-credentials"`` → :attr:`TokenType.M2M_TEAM`
    3. Otherwise → :attr:`TokenType.INDIVIDUAL`

    The ``gty`` (grant type) claim is set by both Auth0 and Zitadel on all
    tokens issued via the OAuth2 client_credentials grant.  It is a standard
    claim that does not require a custom Action or metadata, making it
    compatible with the Zitadel M2M issuer as well as legacy Auth0 M2M apps.

    SPA tokens have ``gty`` absent or set to ``"authorization_code"``.
    Device-code tokens have ``gty="device_code"``.
    Neither will be misidentified as M2M.

    Args:
        claims: Decoded JWT payload (dict of claims).

    Returns:
        The detected :class:`TokenType`.
    """
    if claims.get("is_impersonation"):
        return TokenType.IMPERSONATION
    if claims.get("gty") == "client-credentials":
        return TokenType.M2M_TEAM
    return TokenType.INDIVIDUAL
