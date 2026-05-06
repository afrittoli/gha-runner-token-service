"""OIDC token validation."""

import time


import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.backends.base import Key

# Module-level JWKS cache: {jwks_url: (jwks_dict, fetch_timestamp)}
_jwks_cache: dict[str, tuple[dict, float]] = {}
_JWKS_TTL = 300.0  # 5 minutes


class OIDCValidator:
    """Validates OIDC tokens."""

    def __init__(self, issuer: str, audience: str, jwks_url: str):
        """Initialize OIDC validator with explicit parameters.

        Args:
            issuer: Expected token issuer (iss claim)
            audience: Expected token audience (aud claim)
            jwks_url: URL to fetch JWKS from
        """
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url

    async def _fetch_jwks(self, force_refresh: bool = False) -> dict:
        """
        Fetch JWKS from the OIDC provider with module-level caching.

        Args:
            force_refresh: If True, bypass cache and fetch fresh JWKS

        Returns:
            JWKS dictionary

        Raises:
            HTTPException: If JWKS cannot be fetched
        """
        now = time.monotonic()

        # Check module-level cache (unless force refresh)
        if not force_refresh and self.jwks_url in _jwks_cache:
            jwks, fetch_time = _jwks_cache[self.jwks_url]
            if now - fetch_time < _JWKS_TTL:
                return jwks

        # Cache miss or expired - fetch fresh JWKS
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url, timeout=10.0)
                response.raise_for_status()
                jwks = response.json()
                _jwks_cache[self.jwks_url] = (jwks, now)
                return jwks
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
            # Fetch JWKS (uses module-level cache)
            jwks = await self._fetch_jwks()

            # Get signing key
            try:
                signing_key = self._get_signing_key(token, jwks)
            except HTTPException as e:
                # If kid not found, invalidate cache and retry once (handles key rotation)
                if "Unable to find matching key" in str(e.detail):
                    jwks = await self._fetch_jwks(force_refresh=True)
                    signing_key = self._get_signing_key(token, jwks)
                else:
                    raise

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
                token_audience = token_claims.get("aud", "unknown")
            except Exception:
                token_issuer = "unknown"
                token_audience = "unknown"

            structlog.get_logger().warning(
                "token_validation_failed",
                error=str(e),
                expected_audience=self.audience,
                expected_issuer=self.issuer,
                token_issuer=token_issuer,
                token_audience=token_audience,
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

    def get_user_identity(self, payload: dict) -> str:
        """
        Extract user identity from token payload.

        Args:
            payload: Token claims

        Returns:
            User identity string (email, sub, or preferred_username)
        """
        # Try common identity claims in order of preference
        for claim in ["email", "preferred_username", "sub"]:
            if claim in payload:
                return payload[claim]

        # Fallback to sub claim
        return payload.get("sub", "unknown")
