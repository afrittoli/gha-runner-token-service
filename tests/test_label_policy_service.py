"""Tests for label policy service."""

import json

import pytest
from sqlalchemy.orm import Session

from app.models import LabelPolicy, SecurityEvent
from app.services.label_policy_service import LabelPolicyService, LabelPolicyViolation


class TestLabelPolicyValidation:
    """Tests for label policy validation."""

    def test_validate_labels_no_policy_permissive(self, test_db: Session):
        """Test that labels are allowed when no policy exists (permissive default)."""
        service = LabelPolicyService(test_db)

        # Should not raise - permissive default allows all labels
        service.validate_labels("user@example.com", ["any-label", "another"])

    def test_validate_labels_exact_match(self, test_db: Session):
        """Test label validation with exact label matching."""
        # Create policy
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["team-a", "linux", "docker"]),
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Valid labels - should not raise
        service.validate_labels("user@example.com", ["team-a", "linux"])

        # Invalid label - should raise
        with pytest.raises(LabelPolicyViolation) as exc_info:
            service.validate_labels("user@example.com", ["team-a", "unauthorized"])

        assert "unauthorized" in exc_info.value.invalid_labels

    def test_validate_labels_wildcard_allows_all(self, test_db: Session):
        """Test that wildcard (*) allows all labels."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["*"]),  # Wildcard
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Any labels should be allowed
        service.validate_labels("user@example.com", ["any", "label", "whatsoever"])

    def test_validate_labels_with_patterns(self, test_db: Session):
        """Test label validation with regex patterns."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["base-label"]),
            label_patterns=json.dumps(["team-a-.*", "env-(dev|staging)"]),
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Pattern matches
        service.validate_labels("user@example.com", ["team-a-runner-1"])
        service.validate_labels("user@example.com", ["env-dev"])
        service.validate_labels("user@example.com", ["env-staging"])

        # Pattern doesn't match
        with pytest.raises(LabelPolicyViolation):
            service.validate_labels("user@example.com", ["team-b-runner"])

        with pytest.raises(LabelPolicyViolation):
            service.validate_labels("user@example.com", ["env-prod"])

    def test_validate_labels_violation_contains_invalid_labels(self, test_db: Session):
        """Test that LabelPolicyViolation contains the invalid labels."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["allowed"]),
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        with pytest.raises(LabelPolicyViolation) as exc_info:
            service.validate_labels(
                "user@example.com", ["allowed", "forbidden1", "forbidden2"]
            )

        assert "forbidden1" in exc_info.value.invalid_labels
        assert "forbidden2" in exc_info.value.invalid_labels
        assert "allowed" not in exc_info.value.invalid_labels


class TestRunnerQuota:
    """Tests for runner quota checking."""

    def test_check_quota_no_policy(self, test_db: Session):
        """Test that quota check passes when no policy exists."""
        service = LabelPolicyService(test_db)

        # Should not raise - no quota configured
        service.check_runner_quota("user@example.com", 100)

    def test_check_quota_within_limit(self, test_db: Session):
        """Test quota check when within limit."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["label"]),
            max_runners=5,
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Should not raise - under quota
        service.check_runner_quota("user@example.com", 4)

    def test_check_quota_at_limit(self, test_db: Session):
        """Test quota check when at limit."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["label"]),
            max_runners=5,
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Should raise - at quota
        with pytest.raises(ValueError) as exc_info:
            service.check_runner_quota("user@example.com", 5)

        assert "quota exceeded" in str(exc_info.value).lower()

    def test_check_quota_over_limit(self, test_db: Session):
        """Test quota check when over limit."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["label"]),
            max_runners=5,
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Should raise - over quota
        with pytest.raises(ValueError):
            service.check_runner_quota("user@example.com", 10)


class TestSystemLabelDetection:
    """Tests for system label detection."""

    def test_is_user_label_detects_all_system_labels(self, test_db: Session):
        """Test that all system label prefixes are correctly detected."""
        service = LabelPolicyService(test_db)

        system_labels = [
            "self-hosted",
            "linux",
            "macos",
            "windows",
            "x64",
            "arm64",
            # Case variations should also be detected
            "Self-Hosted",
            "LINUX",
            "MacOS",
            "Windows",
            "X64",
            "ARM64",
        ]

        for label in system_labels:
            assert service._is_user_label(label) is False, (
                f"Label '{label}' should be detected as system label"
            )

    def test_is_user_label_allows_custom_labels(self, test_db: Session):
        """Test that custom labels are not mistaken for system labels."""
        service = LabelPolicyService(test_db)

        user_labels = [
            "team-a",
            "gpu",
            "custom-runner",
            "my-linux-app",  # Contains 'linux' but doesn't start with it
            "production",
        ]

        for label in user_labels:
            assert service._is_user_label(label) is True, (
                f"Label '{label}' should be detected as user label"
            )

    def test_validate_labels_ignores_system_labels(self, test_db: Session):
        """Test that system labels are not subject to policy validation."""
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["team-a"]),  # Only team-a allowed
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Should pass because system labels are ignored even though only team-a is allowed
        service.validate_labels(
            "user@example.com",
            ["self-hosted", "linux", "x64", "team-a"],  # System labels + team-a
        )


class TestLabelVerification:
    """Tests for post-registration label verification."""

    def test_verify_labels_match_success(self, test_db: Session):
        """Test that matching labels return empty set."""
        service = LabelPolicyService(test_db)

        result = service.verify_labels_match(
            expected_labels=["team-a", "custom"],
            actual_labels=["self-hosted", "linux", "x64", "team-a", "custom"],
        )

        assert result == set()  # No mismatches

    def test_verify_labels_ignores_system_labels(self, test_db: Session):
        """Test that system labels are ignored in comparison."""
        service = LabelPolicyService(test_db)

        # System labels (self-hosted, linux, x64) should be ignored
        result = service.verify_labels_match(
            expected_labels=["custom"],
            actual_labels=["self-hosted", "linux", "x64", "custom"],
        )

        assert result == set()

    def test_verify_labels_detects_missing(self, test_db: Session):
        """Test detection of missing labels."""
        service = LabelPolicyService(test_db)

        result = service.verify_labels_match(
            expected_labels=["expected-label", "another"],
            actual_labels=["self-hosted", "linux", "expected-label"],
        )

        assert "another" in result

    def test_verify_labels_detects_unexpected(self, test_db: Session):
        """Test detection of unexpected labels."""
        service = LabelPolicyService(test_db)

        result = service.verify_labels_match(
            expected_labels=["expected"],
            actual_labels=["self-hosted", "expected", "unexpected-extra"],
        )

        assert "unexpected-extra" in result


class TestSecurityEventLogging:
    """Tests for security event logging."""

    def test_log_security_event(self, test_db: Session):
        """Test logging a security event."""
        service = LabelPolicyService(test_db)

        event = service.log_security_event(
            event_type="label_policy_violation",
            severity="high",
            user_identity="violator@example.com",
            oidc_sub="auth0|123",
            runner_id="runner-uuid",
            runner_name="bad-runner",
            violation_data={"invalid_labels": ["forbidden"]},
            action_taken="rejected",
        )

        assert event.id is not None
        assert event.event_type == "label_policy_violation"
        assert event.severity == "high"
        assert event.user_identity == "violator@example.com"
        assert event.action_taken == "rejected"

        # Verify it's in the database
        saved = (
            test_db.query(SecurityEvent).filter(SecurityEvent.id == event.id).first()
        )
        assert saved is not None


class TestPolicyCRUD:
    """Tests for policy CRUD operations."""

    def test_create_policy(self, test_db: Session):
        """Test creating a new policy."""
        service = LabelPolicyService(test_db)

        policy = service.create_policy(
            user_identity="new-user@example.com",
            allowed_labels=["label1", "label2"],
            max_runners=10,
            description="Test policy",
            created_by="admin@example.com",
        )

        assert policy.user_identity == "new-user@example.com"
        assert json.loads(policy.allowed_labels) == ["label1", "label2"]
        assert policy.max_runners == 10

    def test_update_policy(self, test_db: Session):
        """Test updating an existing policy."""
        # Create initial policy
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["old-label"]),
            max_runners=5,
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # Update policy
        updated = service.create_policy(
            user_identity="user@example.com",
            allowed_labels=["new-label1", "new-label2"],
            max_runners=20,
        )

        assert json.loads(updated.allowed_labels) == ["new-label1", "new-label2"]
        assert updated.max_runners == 20

    def test_delete_policy(self, test_db: Session):
        """Test deleting a policy."""
        policy = LabelPolicy(
            user_identity="delete-me@example.com",
            allowed_labels=json.dumps(["label"]),
        )
        test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        result = service.delete_policy("delete-me@example.com")
        assert result is True

        # Verify deleted
        assert service.get_policy("delete-me@example.com") is None

    def test_delete_nonexistent_policy(self, test_db: Session):
        """Test deleting a non-existent policy."""
        service = LabelPolicyService(test_db)

        result = service.delete_policy("nonexistent@example.com")
        assert result is False

    def test_list_policies(self, test_db: Session):
        """Test listing policies with pagination."""
        # Create multiple policies
        for i in range(5):
            policy = LabelPolicy(
                user_identity=f"user{i}@example.com",
                allowed_labels=json.dumps([f"label{i}"]),
            )
            test_db.add(policy)
        test_db.commit()

        service = LabelPolicyService(test_db)

        # List with limit
        policies = service.list_policies(limit=3)
        assert len(policies) == 3

        # List with offset
        policies = service.list_policies(limit=10, offset=3)
        assert len(policies) == 2
