"""Tests for OIDC JWKS caching behavior."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.oidc import OIDCValidator, _jwks_cache, _JWKS_TTL


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the module-level cache before each test."""
    _jwks_cache.clear()
    yield
    _jwks_cache.clear()


@pytest.fixture
def mock_jwks():
    """Sample JWKS response."""
    return {
        "keys": [
            {
                "kid": "test-key-1",
                "kty": "RSA",
                "use": "sig",
                "n": "test-n",
                "e": "AQAB",
            }
        ]
    }


@pytest.fixture
def mock_jwks_rotated():
    """JWKS response after key rotation."""
    return {
        "keys": [
            {
                "kid": "test-key-2",
                "kty": "RSA",
                "use": "sig",
                "n": "test-n-new",
                "e": "AQAB",
            }
        ]
    }


class TestJWKSCacheSharing:
    """Test that JWKS cache is shared across OIDCValidator instances."""

    @pytest.mark.asyncio
    async def test_cache_shared_across_instances(self, mock_jwks):
        """Verify cache is shared for same JWKS URL."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # First validator instance fetches JWKS
            validator1 = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )
            jwks1 = await validator1._fetch_jwks()

            # Second validator instance should use cached JWKS
            validator2 = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )
            jwks2 = await validator2._fetch_jwks()

            # Verify HTTP call was made only once
            assert mock_client.get.call_count == 1
            assert jwks1 == jwks2 == mock_jwks

    @pytest.mark.asyncio
    async def test_different_urls_have_separate_caches(self, mock_jwks):
        """Verify different JWKS URLs maintain separate cache entries."""
        jwks_url1 = "https://provider1.com/.well-known/jwks.json"
        jwks_url2 = "https://provider2.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            validator1 = OIDCValidator(
                issuer="https://provider1.com",
                audience="test-audience",
                jwks_url=jwks_url1,
            )
            await validator1._fetch_jwks()

            validator2 = OIDCValidator(
                issuer="https://provider2.com",
                audience="test-audience",
                jwks_url=jwks_url2,
            )
            await validator2._fetch_jwks()

            # Verify HTTP call was made twice (once per URL)
            assert mock_client.get.call_count == 2


class TestJWKSTTLExpiry:
    """Test that JWKS cache respects TTL and re-fetches when expired."""

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self, mock_jwks):
        """Verify cache is re-fetched after TTL expires."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            validator = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )

            # First fetch
            await validator._fetch_jwks()
            assert mock_client.get.call_count == 1

            # Simulate TTL expiry by manipulating cache timestamp
            if jwks_url in _jwks_cache:
                jwks_data, _ = _jwks_cache[jwks_url]
                # Set timestamp to past (beyond TTL)
                _jwks_cache[jwks_url] = (jwks_data, time.monotonic() - _JWKS_TTL - 1)

            # Second fetch should trigger HTTP call due to expired cache
            await validator._fetch_jwks()
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_not_expired_within_ttl(self, mock_jwks):
        """Verify cache is reused within TTL window."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            validator = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )

            # First fetch
            await validator._fetch_jwks()
            assert mock_client.get.call_count == 1

            # Second fetch within TTL should use cache
            await validator._fetch_jwks()
            assert mock_client.get.call_count == 1


class TestKeyRotationHandling:
    """Test that unknown kid triggers cache invalidation and re-fetch."""

    @pytest.mark.asyncio
    async def test_unknown_kid_triggers_cache_refresh(
        self, mock_jwks, mock_jwks_rotated
    ):
        """Verify unknown kid invalidates cache and re-fetches once."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            # First response has old key
            mock_response1 = MagicMock()
            mock_response1.json.return_value = mock_jwks
            mock_response1.raise_for_status = MagicMock()

            # Second response has rotated key
            mock_response2 = MagicMock()
            mock_response2.json.return_value = mock_jwks_rotated
            mock_response2.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.side_effect = [mock_response1, mock_response2]
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            validator = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )

            # Initial fetch populates cache
            jwks1 = await validator._fetch_jwks()
            assert jwks1 == mock_jwks
            assert mock_client.get.call_count == 1

            # Simulate unknown kid scenario by forcing refresh
            jwks2 = await validator._fetch_jwks(force_refresh=True)
            assert jwks2 == mock_jwks_rotated
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, mock_jwks):
        """Verify force_refresh parameter bypasses cache."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            validator = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )

            # First fetch
            await validator._fetch_jwks()
            assert mock_client.get.call_count == 1

            # Force refresh should bypass cache
            await validator._fetch_jwks(force_refresh=True)
            assert mock_client.get.call_count == 2


class TestCacheErrorHandling:
    """Test error handling in JWKS caching."""

    @pytest.mark.asyncio
    async def test_fetch_failure_raises_http_exception(self):
        """Verify HTTP errors are properly raised."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            validator = OIDCValidator(
                issuer="https://example.com",
                audience="test-audience",
                jwks_url=jwks_url,
            )

            with pytest.raises(HTTPException) as exc_info:
                await validator._fetch_jwks()

            assert exc_info.value.status_code == 503
            assert "Failed to fetch JWKS" in str(exc_info.value.detail)
