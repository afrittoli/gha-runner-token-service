"""GitHub App authentication using JWT."""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt

from app.config import Settings


class GitHubAppAuth:
    """Handles GitHub App authentication and token generation."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.app_id = settings.github_app_id
        self.installation_id = settings.github_app_installation_id
        self.private_key = settings.github_app_private_key
        self.api_url = settings.github_api_url

        self._installation_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _generate_jwt(self) -> str:
        """
        Generate a JWT for GitHub App authentication.

        Returns:
            JWT token string valid for 10 minutes
        """
        now = int(time.time())
        # JWT expires after 10 minutes (max allowed by GitHub)
        expiration = now + (10 * 60)

        payload = {
            "iat": now - 60,  # Issued 60 seconds in the past to allow for clock drift
            "exp": expiration,
            "iss": str(self.app_id),
        }

        # Sign the JWT with the private key
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token

    async def get_installation_token(self, force_refresh: bool = False) -> str:
        """
        Get a GitHub App installation access token.

        Args:
            force_refresh: Force token refresh even if cached token is valid

        Returns:
            Installation access token

        Raises:
            httpx.HTTPError: If token generation fails
        """
        # Return cached token if still valid
        if not force_refresh and self._installation_token and self._token_expires_at:
            # Refresh if token expires in less than 5 minutes
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(
                minutes=5
            ):
                return self._installation_token

        # Generate new installation token
        jwt_token = self._generate_jwt()

        url = f"{self.api_url}/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            self._installation_token = data["token"]
            self._token_expires_at = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            )

            return self._installation_token

    async def get_authenticated_headers(self) -> dict:
        """
        Get HTTP headers with GitHub App authentication.

        Returns:
            Dictionary of headers including Bearer token
        """
        token = await self.get_installation_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
