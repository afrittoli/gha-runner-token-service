"""GitHub API client for runner operations."""

from datetime import datetime
from typing import List, Optional

import httpx

from app.config import Settings
from app.github.app_auth import GitHubAppAuth


class GitHubRunnerInfo:
    """GitHub runner information."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.name = data["name"]
        self.os = data.get("os")
        self.status = data.get("status")
        self.busy = data.get("busy", False)
        self.labels = [label["name"] for label in data.get("labels", [])]


class GitHubClient:
    """Client for GitHub API operations related to runners."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.auth = GitHubAppAuth(settings)
        self.org = settings.github_org
        self.api_url = settings.github_api_url

    async def generate_registration_token(self) -> tuple[str, datetime]:
        """
        Generate a runner registration token.

        Returns:
            Tuple of (token, expires_at)

        Raises:
            httpx.HTTPError: If token generation fails
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runners/registration-token"
        headers = await self.auth.get_authenticated_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            token = data["token"]
            expires_at = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            )

            return token, expires_at

    async def generate_removal_token(self) -> tuple[str, datetime]:
        """
        Generate a runner removal token.

        Returns:
            Tuple of (token, expires_at)

        Raises:
            httpx.HTTPError: If token generation fails
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runners/remove-token"
        headers = await self.auth.get_authenticated_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            token = data["token"]
            expires_at = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            )

            return token, expires_at

    async def list_runners(self, per_page: int = 100) -> List[GitHubRunnerInfo]:
        """
        List all runners in the organization.

        Args:
            per_page: Number of results per page

        Returns:
            List of GitHubRunnerInfo objects

        Raises:
            httpx.HTTPError: If API call fails
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runners"
        headers = await self.auth.get_authenticated_headers()
        params = {"per_page": per_page}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            runners = [GitHubRunnerInfo(r) for r in data.get("runners", [])]
            return runners

    async def get_runner_by_name(self, name: str) -> Optional[GitHubRunnerInfo]:
        """
        Get a runner by name.

        Note: GitHub API does not support filtering by name, so we fetch all
        runners and filter client-side.

        Args:
            name: Runner name

        Returns:
            GitHubRunnerInfo if found, None otherwise

        Raises:
            httpx.HTTPError: If API call fails
        """
        runners = await self.list_runners()
        for runner in runners:
            if runner.name == name:
                return runner
        return None

    async def get_runner_by_id(self, runner_id: int) -> Optional[GitHubRunnerInfo]:
        """
        Get a runner by ID.

        Args:
            runner_id: GitHub runner ID

        Returns:
            GitHubRunnerInfo if found, None otherwise

        Raises:
            httpx.HTTPError: If API call fails (including 404)
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runners/{runner_id}"
        headers = await self.auth.get_authenticated_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return GitHubRunnerInfo(response.json())
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

    async def delete_runner(self, runner_id: int) -> bool:
        """
        Delete a runner from GitHub.

        Args:
            runner_id: GitHub runner ID

        Returns:
            True if deleted successfully, False if runner not found

        Raises:
            httpx.HTTPError: If API call fails (except 404)
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runners/{runner_id}"
        headers = await self.auth.get_authenticated_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=headers)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return False
                raise

    async def get_runner_groups(self) -> List[dict]:
        """
        List runner groups in the organization.

        Returns:
            List of runner group dictionaries

        Raises:
            httpx.HTTPError: If API call fails
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runner-groups"
        headers = await self.auth.get_authenticated_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            return data.get("runner_groups", [])

    async def cancel_workflow_run(self, repo: str, run_id: int) -> bool:
        """
        Cancel a workflow run.

        Args:
            repo: Repository name (without org prefix)
            run_id: Workflow run ID

        Returns:
            True if cancelled successfully, False if not found

        Raises:
            httpx.HTTPError: If API call fails (except 404)
        """
        url = f"{self.api_url}/repos/{self.org}/{repo}/actions/runs/{run_id}/cancel"
        headers = await self.auth.get_authenticated_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers)
                # 202 Accepted is success for cancel
                if response.status_code == 202:
                    return True
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return False
                raise
