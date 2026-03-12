"""Tests for GitHub webhook handlers."""

import hashlib
import hmac
import json
import unittest.mock as mock
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Runner


def _make_runner(
    db: Session,
    name: str = "test-runner",
    status: str = "pending",
    team_id: str = "team-1",
) -> Runner:
    """Create and persist a runner for testing."""
    runner = Runner(
        runner_name=name,
        runner_group_id=1,
        github_url=("https://github.com/test-org/test-repo/actions/runners/42"),
        labels=json.dumps(["self-hosted"]),
        provisioned_by="user@example.com",
        status=status,
        team_id=team_id,
    )
    db.add(runner)
    db.commit()
    db.refresh(runner)
    return runner


def _sign(body: bytes, secret: str) -> str:
    """Compute GitHub webhook signature."""
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _post_webhook(
    client: TestClient,
    payload: dict,
    event: str = "workflow_job",
    secret: str = "",
) -> object:
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "test-delivery-id",
        "Content-Type": "application/json",
    }
    if secret:
        headers["X-Hub-Signature-256"] = _sign(body, secret)
    return client.post("/api/v1/webhooks/github", content=body, headers=headers)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


class TestWebhookSignatureVerification:
    def test_valid_signature_accepted(self, webhook_client_with_secret):
        client, secret = webhook_client_with_secret
        payload = {"action": "queued", "workflow_job": {}, "repository": {}}
        response = _post_webhook(client, payload, secret=secret)
        assert response.status_code == 200

    def test_invalid_signature_rejected(self, webhook_client_with_secret):
        client, _ = webhook_client_with_secret
        payload = {"action": "queued", "workflow_job": {}, "repository": {}}
        body = json.dumps(payload).encode()
        response = client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "workflow_job",
                "X-Hub-Signature-256": "sha256=invalidsig",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401

    def test_no_secret_configured_skips_verification(self, webhook_client: TestClient):
        """When no secret is configured, all requests are accepted."""
        payload = {"action": "queued", "workflow_job": {}, "repository": {}}
        response = _post_webhook(webhook_client, payload)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Event routing
# ---------------------------------------------------------------------------


class TestWebhookEventRouting:
    def test_non_workflow_job_event_ignored(self, webhook_client: TestClient):
        payload = {"action": "created"}
        response = _post_webhook(webhook_client, payload, event="ping")
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_queued_action_ignored(self, webhook_client: TestClient):
        payload = {
            "action": "queued",
            "workflow_job": {
                "runner_name": None,
                "runner_id": None,
                "run_id": 1,
            },
            "repository": {"name": "repo", "full_name": "org/repo"},
        }
        response = _post_webhook(webhook_client, payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_unknown_runner_ignored(self, webhook_client: TestClient):
        payload = {
            "action": "in_progress",
            "workflow_job": {
                "runner_name": "unknown-runner",
                "runner_id": 99,
                "run_id": 1,
            },
            "repository": {"name": "repo", "full_name": "org/repo"},
        }
        response = _post_webhook(webhook_client, payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert "not managed" in response.json()["reason"]


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


class TestWebhookStatusTransitions:
    def test_in_progress_marks_runner_active(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="pending")

        with mock.patch(
            "app.api.v1.webhooks.validate_runner_labels",
            new=AsyncMock(return_value=(runner, None)),
        ):
            payload = {
                "action": "in_progress",
                "workflow_job": {
                    "runner_name": runner.runner_name,
                    "runner_id": 42,
                    "run_id": 1,
                },
                "repository": {"name": "repo", "full_name": "org/repo"},
            }
            response = _post_webhook(webhook_client, payload)

        assert response.status_code == 200
        test_db.refresh(runner)
        assert runner.status == "active"

    def test_completed_marks_runner_offline(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="active")

        payload = {
            "action": "completed",
            "workflow_job": {
                "runner_name": runner.runner_name,
                "runner_id": 42,
                "run_id": 1,
            },
            "repository": {"name": "repo", "full_name": "org/repo"},
        }
        response = _post_webhook(webhook_client, payload)

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "action": "completed"}
        test_db.refresh(runner)
        assert runner.status == "offline"

    def test_completed_skips_update_if_already_offline(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="offline")
        original_updated_at = runner.updated_at

        payload = {
            "action": "completed",
            "workflow_job": {
                "runner_name": runner.runner_name,
                "runner_id": 42,
                "run_id": 1,
            },
            "repository": {"name": "repo", "full_name": "org/repo"},
        }
        response = _post_webhook(webhook_client, payload)

        assert response.status_code == 200
        test_db.refresh(runner)
        assert runner.status == "offline"
        assert runner.updated_at == original_updated_at

    def test_completed_skips_update_if_deleted(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="deleted")

        payload = {
            "action": "completed",
            "workflow_job": {
                "runner_name": runner.runner_name,
                "runner_id": 42,
                "run_id": 1,
            },
            "repository": {"name": "repo", "full_name": "org/repo"},
        }
        response = _post_webhook(webhook_client, payload)

        assert response.status_code == 200
        test_db.refresh(runner)
        assert runner.status == "deleted"

    def test_in_progress_skips_update_if_already_active(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="active")
        original_updated_at = runner.updated_at

        with mock.patch(
            "app.api.v1.webhooks.validate_runner_labels",
            new=AsyncMock(return_value=(runner, None)),
        ):
            payload = {
                "action": "in_progress",
                "workflow_job": {
                    "runner_name": runner.runner_name,
                    "runner_id": 42,
                    "run_id": 1,
                },
                "repository": {"name": "repo", "full_name": "org/repo"},
            }
            _post_webhook(webhook_client, payload)

        test_db.refresh(runner)
        assert runner.status == "active"
        assert runner.updated_at == original_updated_at
