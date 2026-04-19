"""OIDC token validation."""

from typing import Optional

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.backends.base import Key

from app.config import Settings


class OIDCValidator:
    """Validates OIDC tokens."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.issuer = settings.oidc_issuer
        self.audience = settings.oidc_audience
        self.jwks_url = settings.oidc_jwks_url
        self._jwks_cache: Optional[dict] = None

    async def _fetch_jwks(self) -> dict:
        """
        Fetch JWKS from the OIDC provider.

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
        """
        Get the signing key for a JWT token.

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

            # Find the matching key
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
        """
        Validate an OIDC token.

        Args:
            token: JWT token string

        Returns:
            Token payload (claims)

        Raises:
            HTTPException: If token validation fails
        """
        try:
            # Fetch JWKS
            jwks = await self._fetch_jwks()

            # Get signing key
            signing_key = self._get_signing_key(token, jwks)

            # Validate and decode token
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
            import structlog

            try:
                token_claims = jwt.get_unverified_claims(token)
                token_issuer = token_claims.get("iss", "unknown")
            except Exception:
                token_issuer = "unknown"

            structlog.get_logger().warning(
                "token_validation_failed",
                error=str(e),
                expected_audience=self.audience,
                expected_issuer=self.issuer,
                token_issuer=token_issuer,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            import structlog

            structlog.get_logger().warning(
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
