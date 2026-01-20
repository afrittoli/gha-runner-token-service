"""GitHub API client for runner operations."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import httpx

from app.config import Settings
from app.github.app_auth import GitHubAppAuth


@dataclass
class JitConfigResponse:
    """Response from GitHub JIT config generation API."""

    runner_id: int
    runner_name: str
    encoded_jit_config: str
    os: Optional[str] = None
    labels: Optional[List[str]] = None


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

    async def generate_jit_config(
        self,
        name: str,
        runner_group_id: int,
        labels: List[str],
        work_folder: str = "_work",
    ) -> JitConfigResponse:
        """
        Generate JIT configuration for a runner.

        Creates a runner registration with pre-configured labels and ephemeral mode.
        The returned config is passed to `./run.sh --jitconfig <config>`.

        Args:
            name: Runner name (1-64 characters)
            runner_group_id: ID of the runner group to add the runner to
            labels: List of custom labels (1-100 labels, system labels added automatically)
            work_folder: Relative path to the work directory (default: "_work")

        Returns:
            JitConfigResponse with encoded config and runner details

        Raises:
            httpx.HTTPStatusError: If API call fails
                - 404: Runner group not found
                - 409: Runner name already exists
                - 422: Invalid parameters (e.g., too many labels)
        """
        url = f"{self.api_url}/orgs/{self.org}/actions/runners/generate-jitconfig"
        headers = await self.auth.get_authenticated_headers()

        payload = {
            "name": name,
            "runner_group_id": runner_group_id,
            "labels": labels,
            "work_folder": work_folder,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            runner_data = data.get("runner", {})

            return JitConfigResponse(
                runner_id=runner_data.get("id"),
                runner_name=runner_data.get("name", name),
                encoded_jit_config=data.get("encoded_jit_config"),
                os=runner_data.get("os"),
                labels=[label["name"] for label in runner_data.get("labels", [])],
            )
