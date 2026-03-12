"""Tests for Prometheus metrics instrumentation."""

import asyncio
import json
import unittest.mock as mock
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy.orm import Session

from app.models import Runner
from app.services.sync_service import SyncService

_TRANSITIONS = "gharts_runner_state_transitions_total"
_BY_STATUS = "gharts_runners_by_status"


def _counter_value(name: str, labels: dict) -> float:
    """Read a counter sample value from the registry (0.0 if not yet set).

    Pass the full sample name including the _total suffix,
    e.g. 'gharts_runner_state_transitions_total'.
    """
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


def _gauge_value(name: str, labels: dict) -> float:
    """Read a gauge value from the registry (0.0 if not yet set)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


def _post_webhook(client: TestClient, payload: dict) -> object:
    body = json.dumps(payload).encode()
    return client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "workflow_job",
            "X-GitHub-Delivery": "test-delivery-id",
            "Content-Type": "application/json",
        },
    )


def _make_runner(
    db: Session,
    name: str = "test-runner",
    status: str = "pending",
    team_id: str = "team-1",
    team_name: str = "test-team",
) -> Runner:
    runner = Runner(
        runner_name=name,
        runner_group_id=1,
        github_url=("https://github.com/test-org/test-repo/actions/runners/42"),
        labels=json.dumps(["self-hosted"]),
        provisioned_by="user@example.com",
        status=status,
        team_id=team_id,
        team_name=team_name,
    )
    db.add(runner)
    db.commit()
    db.refresh(runner)
    return runner


# ---------------------------------------------------------------------------
# Webhook transition metrics
# ---------------------------------------------------------------------------


class TestWebhookTransitionMetrics:
    """Webhook handler increments runner_state_transitions_total."""

    def test_in_progress_records_transition(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="pending")
        lbls = {
            "from_status": "pending",
            "to_status": "active",
            "source": "webhook",
        }
        before = _counter_value(_TRANSITIONS, lbls)

        with mock.patch(
            "app.api.v1.webhooks.validate_runner_labels",
            new=AsyncMock(return_value=(runner, None)),
        ):
            _post_webhook(
                webhook_client,
                {
                    "action": "in_progress",
                    "workflow_job": {
                        "runner_name": runner.runner_name,
                        "runner_id": 42,
                        "run_id": 1,
                    },
                    "repository": {
                        "name": "repo",
                        "full_name": "org/repo",
                    },
                },
            )

        assert _counter_value(_TRANSITIONS, lbls) - before == 1.0

    def test_completed_records_transition(
        self, webhook_client: TestClient, test_db: Session
    ):
        runner = _make_runner(test_db, status="active")
        lbls = {
            "from_status": "active",
            "to_status": "offline",
            "source": "webhook",
        }
        before = _counter_value(_TRANSITIONS, lbls)

        _post_webhook(
            webhook_client,
            {
                "action": "completed",
                "workflow_job": {
                    "runner_name": runner.runner_name,
                    "runner_id": 42,
                    "run_id": 1,
                },
                "repository": {"name": "repo", "full_name": "org/repo"},
            },
        )

        assert _counter_value(_TRANSITIONS, lbls) - before == 1.0

    def test_idempotent_transition_not_recorded(
        self, webhook_client: TestClient, test_db: Session
    ):
        """No metric increment when status is already at target."""
        runner = _make_runner(test_db, status="offline")
        lbls = {
            "from_status": "offline",
            "to_status": "offline",
            "source": "webhook",
        }
        before = _counter_value(_TRANSITIONS, lbls)

        _post_webhook(
            webhook_client,
            {
                "action": "completed",
                "workflow_job": {
                    "runner_name": runner.runner_name,
                    "runner_id": 42,
                    "run_id": 1,
                },
                "repository": {"name": "repo", "full_name": "org/repo"},
            },
        )

        assert _counter_value(_TRANSITIONS, lbls) - before == 0.0


# ---------------------------------------------------------------------------
# Sync service transition metrics
# ---------------------------------------------------------------------------


class TestSyncTransitionMetrics:
    """SyncService increments runner_state_transitions_total source=sync."""

    def test_status_update_records_transition(self, test_db: Session, mock_settings):
        runner = _make_runner(test_db, status="pending")
        lbls = {
            "from_status": "pending",
            "to_status": "online",
            "source": "sync",
        }
        before = _counter_value(_TRANSITIONS, lbls)

        github_runner = MagicMock()
        github_runner.id = 42
        github_runner.name = runner.runner_name
        github_runner.status = "online"
        github_runner.busy = False
        github_runner.labels = ["self-hosted"]

        with mock.patch("app.services.sync_service.GitHubClient") as MockClient:
            MockClient.return_value.list_runners = AsyncMock(
                return_value=[github_runner]
            )
            service = SyncService(mock_settings, test_db)
            asyncio.get_event_loop().run_until_complete(service.sync_all_runners())

        assert _counter_value(_TRANSITIONS, lbls) - before == 1.0

    def test_mark_deleted_records_transition(self, test_db: Session, mock_settings):
        _make_runner(test_db, status="online")
        lbls = {
            "from_status": "online",
            "to_status": "deleted",
            "source": "sync",
        }
        before = _counter_value(_TRANSITIONS, lbls)

        with mock.patch("app.services.sync_service.GitHubClient") as MockClient:
            MockClient.return_value.list_runners = AsyncMock(return_value=[])
            service = SyncService(mock_settings, test_db)
            asyncio.get_event_loop().run_until_complete(service.sync_all_runners())

        assert _counter_value(_TRANSITIONS, lbls) - before == 1.0


# ---------------------------------------------------------------------------
# runners_by_status gauge
# ---------------------------------------------------------------------------


class TestRunnersByStatusGauge:
    """SyncService updates the runners_by_status gauge after each sync."""

    def test_gauge_reflects_current_counts(self, test_db: Session, mock_settings):
        _make_runner(test_db, name="r1", status="pending", team_name="t-a")
        _make_runner(test_db, name="r2", status="pending", team_name="t-a")
        _make_runner(test_db, name="r3", status="online", team_name="t-b")

        github_runner = MagicMock()
        github_runner.id = 99
        github_runner.name = "r3"
        github_runner.status = "online"
        github_runner.busy = False
        github_runner.labels = ["self-hosted"]

        with mock.patch("app.services.sync_service.GitHubClient") as MockClient:
            MockClient.return_value.list_runners = AsyncMock(
                return_value=[github_runner]
            )
            service = SyncService(mock_settings, test_db)
            asyncio.get_event_loop().run_until_complete(service.sync_all_runners())

        assert _gauge_value(_BY_STATUS, {"status": "pending", "team": "t-a"}) == 2.0
        assert _gauge_value(_BY_STATUS, {"status": "online", "team": "t-b"}) == 1.0

    def test_gauge_excludes_deleted_runners(self, test_db: Session, mock_settings):
        _make_runner(test_db, name="rd", status="deleted", team_name="t-a")

        with mock.patch("app.services.sync_service.GitHubClient") as MockClient:
            MockClient.return_value.list_runners = AsyncMock(return_value=[])
            service = SyncService(mock_settings, test_db)
            asyncio.get_event_loop().run_until_complete(service.sync_all_runners())

        assert _gauge_value(_BY_STATUS, {"status": "deleted", "team": "t-a"}) == 0.0
