"""OIDC token validation.

Supports dual-issuer mode: Auth0 for user tokens (SPA / device-code) and an
optional Zitadel instance for M2M client_credentials tokens.  The correct
validator is selected by inspecting the unverified ``iss`` claim before
performing signature verification, so each token is always validated against
its own issuer's JWKS.
"""

from typing import Optional

import httpx
import structlog
from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.backends.base import Key

from app.config import Settings

logger = structlog.get_logger()


class OIDCValidator:
    """Validates OIDC tokens against a single issuer's JWKS."""

    def __init__(self, issuer: str, jwks_url: str, audience: str):
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self._jwks_cache: Optional[dict] = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "OIDCValidator":
        """Construct the Auth0 validator from application settings."""
        return cls(
            issuer=settings.oidc_issuer,
            jwks_url=settings.oidc_jwks_url,
            audience=settings.oidc_audience,
        )

    async def _fetch_jwks(self) -> dict:
        """Fetch JWKS from the OIDC provider (cached in memory).

        Returns:
            JWKS dictionary

        Raises:
            HTTPException: If JWKS cannot be fetched
        """
        if self._jwks_cache:
            return self._jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                return self._jwks_cache
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch JWKS: {str(e)}",
            )

    def _get_signing_key(self, token: str, jwks: dict) -> Key:
        """Get the signing key for a JWT token.

        Args:
            token: JWT token
            jwks: JWKS dictionary

        Returns:
            Signing key

        Raises:
            HTTPException: If signing key cannot be found
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token header missing 'kid'",
                )

            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    return key

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find matching key in JWKS",
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token header: {str(e)}",
            )

    async def validate_token(self, token: str) -> dict:
        """Validate an OIDC token.

        Args:
            token: JWT token string

        Returns:
            Token payload (claims)

        Raises:
            HTTPException: If token validation fails
        """
        try:
            jwks = await self._fetch_jwks()
            signing_key = self._get_signing_key(token, jwks)

            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )

            return payload

        except JWTError as e:
            logger.warning(
                "token_validation_failed",
                error=str(e),
                audience=self.audience,
                issuer=self.issuer,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.warning(
                "token_validation_error",
                error=str(e),
                audience=self.audience,
                issuer=self.issuer,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def get_user_identity(self, payload: dict) -> str:
        """Extract user identity from token payload.

        Args:
            payload: Token claims

        Returns:
            User identity string (email, preferred_username, or sub)
        """
        for claim in ["email", "preferred_username", "sub"]:
            if claim in payload:
                return payload[claim]

        return payload.get("sub", "unknown")


class MultiIssuerValidator:
    """Routes token validation to the correct OIDCValidator based on ``iss``.

    Two issuers are supported:

    * **Auth0** (always present): used for SPA and device-code user tokens.
    * **Zitadel** (optional): used for M2M ``client_credentials`` tokens.

    Routing is strict: a token from the wrong issuer for the wrong token type
    is rejected before the signature is even verified.  This prevents a
    Zitadel M2M token from being accepted on the individual-user path and vice
    versa.
    """

    def __init__(self, auth0_validator: OIDCValidator, zitadel_validator: Optional[OIDCValidator] = None):
        self._auth0 = auth0_validator
        self._zitadel = zitadel_validator

    @classmethod
    def from_settings(cls, settings: Settings) -> "MultiIssuerValidator":
        """Build the validator set from application settings."""
        auth0 = OIDCValidator.from_settings(settings)

        zitadel: Optional[OIDCValidator] = None
        if settings.zitadel_issuer and settings.zitadel_jwks_url:
            zitadel = OIDCValidator(
                issuer=settings.zitadel_issuer,
                jwks_url=settings.zitadel_jwks_url,
                audience=settings.oidc_audience,
            )

        return cls(auth0_validator=auth0, zitadel_validator=zitadel)

    def _peek_issuer(self, token: str) -> str:
        """Return the ``iss`` claim without verifying the signature.

        Raises:
            HTTPException: If the token is malformed or has no ``iss`` claim.
        """
        try:
            claims = jwt.get_unverified_claims(token)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Malformed token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        iss = claims.get("iss")
        if not iss:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'iss' claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return iss

    def _select_validator(self, token: str) -> OIDCValidator:
        """Choose the right OIDCValidator for this token.

        Raises:
            HTTPException: If the issuer is not trusted.
        """
        iss = self._peek_issuer(token)

        if self._zitadel and iss == self._zitadel.issuer:
            return self._zitadel

        if iss == self._auth0.issuer:
            return self._auth0

        logger.warning("token_unknown_issuer", issuer=iss)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token issuer '{iss}' is not trusted",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def validate_token(self, token: str) -> dict:
        """Validate a token against the appropriate issuer's JWKS.

        Args:
            token: JWT token string

        Returns:
            Verified token payload (claims)

        Raises:
            HTTPException: If validation fails or the issuer is unknown.
        """
        validator = self._select_validator(token)
        return await validator.validate_token(token)

    def get_user_identity(self, payload: dict) -> str:
        """Extract user identity from verified payload."""
        return self._auth0.get_user_identity(payload)
