"""Test dashboard counter accuracy with deleted runners."""

from app.models import Runner


class TestDashboardCounters:
    """Test that dashboard counters correctly exclude deleted runners."""

    def test_dashboard_stats_excludes_deleted_runners_via_api(self, client, test_db):
        """Test that dashboard stats API excludes deleted runners."""
        # Create runners with different statuses
        runners_data = [
            {"runner_name": "active-1", "status": "active"},
            {"runner_name": "active-2", "status": "active"},
            {"runner_name": "offline-1", "status": "offline"},
            {"runner_name": "pending-1", "status": "pending"},
            {"runner_name": "deleted-1", "status": "deleted"},
            {"runner_name": "deleted-2", "status": "deleted"},
        ]

        for data in runners_data:
            runner = Runner(
                runner_name=data["runner_name"],
                status=data["status"],
                labels="[]",
                ephemeral=False,
                provisioned_by="test@example.com",
                github_url="https://github.com/test-org",
                runner_group_id=1,
            )
            test_db.add(runner)

        test_db.commit()

        # Verify via API endpoint
        stats_response = client.get("/api/v1/dashboard/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()

        # Verify counts (should exclude 2 deleted runners)
        expected_total = 4
        assert stats["total"] == expected_total, (
            f"Expected {expected_total} total runners (excluding deleted), "
            f"got {stats['total']}"
        )
        assert stats["active"] == 2
        assert stats["offline"] == 1
        assert stats["pending"] == 1

    def test_api_dashboard_stats_excludes_deleted_runners(self, client, test_db):
        """Test API dashboard stats endpoint excludes deleted runners."""
        # Create runners with different statuses
        runners_data = [
            {"runner_name": "test-active", "status": "active"},
            {"runner_name": "test-deleted", "status": "deleted"},
        ]

        for data in runners_data:
            runner = Runner(
                runner_name=data["runner_name"],
                status=data["status"],
                labels="[]",
                ephemeral=False,
                provisioned_by="test@example.com",
                github_url="https://github.com/test-org",
                runner_group_id=1,
            )
            test_db.add(runner)

        test_db.commit()

        # Get stats
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        stats = response.json()

        # Should only count the active runner, not the deleted one
        assert stats["total"] == 1
        assert stats["active"] == 1
        assert stats["offline"] == 0
        assert stats["pending"] == 0

    def test_dashboard_stats_with_no_runners(self, client, test_db):
        """Test dashboard stats with no runners."""
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        stats = response.json()

        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["offline"] == 0
        assert stats["pending"] == 0

    def test_dashboard_stats_with_only_deleted_runners(self, client, test_db):
        """Test dashboard stats when all runners are deleted."""
        # Create only deleted runners
        for i in range(3):
            runner = Runner(
                runner_name=f"deleted-{i}",
                status="deleted",
                labels="[]",
                ephemeral=False,
                provisioned_by="test@example.com",
                github_url="https://github.com/test-org",
                runner_group_id=1,
            )
            test_db.add(runner)

        test_db.commit()

        # Get stats
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        stats = response.json()

        # All counters should be 0 since all runners are deleted
        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["offline"] == 0
        assert stats["pending"] == 0


# Made with Bob
