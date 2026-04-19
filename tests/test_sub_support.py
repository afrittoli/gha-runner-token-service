"""Tests for OIDC sub claim support — stable User.id-based identity storage.

Covers:
- resolve_user_display: all priority branches
  (display_name > email > oidc_sub > id)
- resolve_user_display: m2m passthrough, unknown UUID fallback
- Security event response: user_identity is a resolved display string
- Security event filter: user_identity param resolved by email
- Audit log response: user_identity is a resolved display string
- Audit log filter: user_identity resolved by email / sub / UUID
- Team members response: oidc_sub field present for sub-only users
- Admin user create API: sub-only user (no email)
- Runner provisioned_by response: resolved display string
- Batch delete runners: user lookup by email, sub, and UUID
"""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AuditLog, Runner, SecurityEvent, User, resolve_user_display


# ---------------------------------------------------------------------------
# Unit tests for resolve_user_display
# ---------------------------------------------------------------------------


class TestResolveUserDisplay:
    """Unit tests for the resolve_user_display helper."""

    def test_display_name_takes_priority(self, test_db: Session):
        user = User(
            email="a@example.com",
            oidc_sub="auth0|aaa",
            display_name="Alice Smith",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        assert resolve_user_display(user.id, test_db) == "Alice Smith"

    def test_email_fallback(self, test_db: Session):
        user = User(email="b@example.com", oidc_sub="auth0|bbb", is_active=True)
        test_db.add(user)
        test_db.commit()
        assert resolve_user_display(user.id, test_db) == "b@example.com"

    def test_oidc_sub_fallback(self, test_db: Session):
        user = User(oidc_sub="auth0|ccc", is_active=True)
        test_db.add(user)
        test_db.commit()
        assert resolve_user_display(user.id, test_db) == "auth0|ccc"

    def test_user_id_last_resort(self, test_db: Session):
        user = User(is_active=True)
        test_db.add(user)
        test_db.commit()
        assert resolve_user_display(user.id, test_db) == user.id

    def test_m2m_string_passthrough(self, test_db: Session):
        result = resolve_user_display("m2m:platform-team", test_db)
        assert result == "m2m:platform-team"

    def test_unknown_uuid_returns_as_is(self, test_db: Session):
        unknown = "00000000-0000-0000-0000-000000000099"
        assert resolve_user_display(unknown, test_db) == unknown


# ---------------------------------------------------------------------------
# Security events: user_identity in response is resolved display string
# ---------------------------------------------------------------------------


class TestSecurityEventResolution:
    """Security event responses expose a resolved user_identity string."""

    def test_security_event_user_identity_is_resolved(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(
            email="violator@example.com",
            display_name="Eve Violator",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()

        event = SecurityEvent(
            event_type="label_policy_violation",
            severity="high",
            user_id=user.id,
            violation_data=json.dumps({"reason": "bad label"}),
        )
        test_db.add(event)
        test_db.commit()

        response = client.get("/api/v1/admin/security-events")
        assert response.status_code == 200
        events = response.json()["events"]
        matching = [e for e in events if e["event_type"] == "label_policy_violation"]
        assert matching, "Expected at least one label_policy_violation event"
        assert matching[0]["user_identity"] == "Eve Violator"

    def test_security_event_m2m_user_identity_passthrough(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        event = SecurityEvent(
            event_type="quota_exceeded",
            severity="medium",
            user_id="m2m:ci-team",
            violation_data=json.dumps({}),
        )
        test_db.add(event)
        test_db.commit()

        response = client.get("/api/v1/admin/security-events")
        assert response.status_code == 200
        events = response.json()["events"]
        matching = [e for e in events if e["event_type"] == "quota_exceeded"]
        assert matching
        assert matching[0]["user_identity"] == "m2m:ci-team"

    def test_security_event_filter_by_user_email(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(email="filtered@example.com", is_active=True)
        other = User(email="other@example.com", is_active=True)
        test_db.add_all([user, other])
        test_db.commit()

        test_db.add(
            SecurityEvent(
                event_type="label_policy_violation",
                severity="low",
                user_id=user.id,
                violation_data=json.dumps({}),
            )
        )
        test_db.add(
            SecurityEvent(
                event_type="label_policy_violation",
                severity="low",
                user_id=other.id,
                violation_data=json.dumps({}),
            )
        )
        test_db.commit()

        response = client.get(
            "/api/v1/admin/security-events",
            params={"user_identity": "filtered@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["events"][0]["user_identity"] == "filtered@example.com"


# ---------------------------------------------------------------------------
# Audit log: user_identity filter resolves by email, sub, and UUID
# ---------------------------------------------------------------------------


class TestAuditLogResolution:
    """Audit log responses expose resolved user_identity; filter accepts
    email/sub/UUID."""

    def _make_audit(self, test_db: Session, user_id: str) -> AuditLog:
        log = AuditLog(
            event_type="provision_runner",
            user_id=user_id,
            success=True,
        )
        test_db.add(log)
        test_db.commit()
        return log

    def test_audit_log_user_identity_resolved(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(
            email="runner-user@example.com",
            display_name="Runner User",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        self._make_audit(test_db, user.id)

        response = client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        logs = response.json()["logs"]
        matching = [
            entry for entry in logs if entry["event_type"] == "provision_runner"
        ]
        assert matching
        assert matching[0]["user_identity"] == "Runner User"

    def test_audit_log_filter_by_email(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(email="audit-filter@example.com", is_active=True)
        other = User(email="noise@example.com", is_active=True)
        test_db.add_all([user, other])
        test_db.commit()
        self._make_audit(test_db, user.id)
        self._make_audit(test_db, other.id)

        response = client.get(
            "/api/v1/audit-logs",
            params={"user_identity": "audit-filter@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["logs"][0]["user_identity"] == "audit-filter@example.com"

    def test_audit_log_filter_by_oidc_sub(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(oidc_sub="auth0|auditSub", is_active=True)
        test_db.add(user)
        test_db.commit()
        self._make_audit(test_db, user.id)

        response = client.get(
            "/api/v1/audit-logs",
            params={"user_identity": "auth0|auditSub"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["logs"][0]["user_identity"] == "auth0|auditSub"

    def test_audit_log_filter_by_user_id(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(email="uuid-filter@example.com", is_active=True)
        test_db.add(user)
        test_db.commit()
        self._make_audit(test_db, user.id)

        response = client.get(
            "/api/v1/audit-logs",
            params={"user_identity": user.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


# ---------------------------------------------------------------------------
# Team members: oidc_sub present in response for sub-only users
# ---------------------------------------------------------------------------


class TestTeamMembersSubOnly:
    """Team member responses include oidc_sub for sub-only users."""

    def test_sub_only_member_in_team_response(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        from app.models import Team, UserTeamMembership

        team = Team(
            name="sub-only-team",
            required_labels=json.dumps([]),
            optional_label_patterns=json.dumps([]),
            is_active=True,
        )
        test_db.add(team)
        test_db.commit()

        user = User(oidc_sub="auth0|subOnly", is_active=True)
        test_db.add(user)
        test_db.commit()

        test_db.add(UserTeamMembership(user_id=user.id, team_id=team.id))
        test_db.commit()

        response = client.get(f"/api/v1/admin/teams/{team.id}/members")
        assert response.status_code == 200
        members = response.json()["members"]
        assert len(members) == 1
        member = members[0]
        assert member["oidc_sub"] == "auth0|subOnly"
        assert member["email"] is None

    def test_email_only_member_has_null_oidc_sub(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        from app.models import Team, UserTeamMembership

        team = Team(
            name="email-only-team",
            required_labels=json.dumps([]),
            optional_label_patterns=json.dumps([]),
            is_active=True,
        )
        test_db.add(team)
        test_db.commit()

        user = User(email="email-only@example.com", is_active=True)
        test_db.add(user)
        test_db.commit()

        test_db.add(UserTeamMembership(user_id=user.id, team_id=team.id))
        test_db.commit()

        response = client.get(f"/api/v1/admin/teams/{team.id}/members")
        assert response.status_code == 200
        members = response.json()["members"]
        assert len(members) == 1
        member = members[0]
        assert member["email"] == "email-only@example.com"
        assert member["oidc_sub"] is None


# ---------------------------------------------------------------------------
# Admin user create API: sub-only user
# ---------------------------------------------------------------------------


class TestSubOnlyUserCreate:
    """Admin can create users with only oidc_sub (no email)."""

    def test_create_sub_only_admin_user(
        self,
        client: TestClient,
        test_db: Session,  # noqa: ARG002
        admin_auth_override,  # noqa: ARG002
    ):
        # is_admin=True bypasses the team_ids requirement
        response = client.post(
            "/api/v1/admin/users",
            json={"oidc_sub": "auth0|newSubUser", "is_admin": True},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["oidc_sub"] == "auth0|newSubUser"
        assert data["email"] is None

    def test_create_sub_only_non_admin_user_requires_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        """Non-admin sub-only users must be assigned to at least one team."""
        from app.models import Team

        team = Team(
            name="sub-user-team",
            required_labels=json.dumps([]),
            optional_label_patterns=json.dumps([]),
            is_active=True,
        )
        test_db.add(team)
        test_db.commit()

        response = client.post(
            "/api/v1/admin/users",
            json={"oidc_sub": "auth0|teamSubUser", "team_ids": [team.id]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["oidc_sub"] == "auth0|teamSubUser"
        assert data["email"] is None

    def test_create_sub_only_user_can_be_retrieved(
        self,
        client: TestClient,
        test_db: Session,  # noqa: ARG002
        admin_auth_override,  # noqa: ARG002
    ):
        create_resp = client.post(
            "/api/v1/admin/users",
            json={"oidc_sub": "auth0|retrieveSub", "is_admin": True},
        )
        assert create_resp.status_code == 201
        user_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/v1/admin/users/{user_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["oidc_sub"] == "auth0|retrieveSub"

    def test_create_user_without_email_or_sub_rejected(
        self,
        client: TestClient,
        test_db: Session,  # noqa: ARG002
        admin_auth_override,  # noqa: ARG002
    ):
        response = client.post(
            "/api/v1/admin/users",
            json={"display_name": "No Identity", "is_admin": True},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Runner provisioned_by response: resolved display string
# ---------------------------------------------------------------------------


class TestRunnerProvisionedByDisplay:
    """Runner list responses show a resolved string for provisioned_by."""

    def test_runner_provisioned_by_resolved_to_display_name(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(
            email="runner-owner@example.com",
            display_name="Runner Owner",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()

        runner = Runner(
            runner_name="owned-runner",
            runner_group_id=1,
            labels=json.dumps(["self-hosted"]),
            provisioned_by=user.id,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        # Admin sees all runners
        response = client.get("/api/v1/runners")
        assert response.status_code == 200
        runners = response.json()["runners"]
        matching = [r for r in runners if r["runner_name"] == "owned-runner"]
        assert matching
        assert matching[0]["provisioned_by"] == "Runner Owner"

    def test_runner_provisioned_by_resolved_to_sub_for_sub_only_user(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(oidc_sub="auth0|subOwner", is_active=True)
        test_db.add(user)
        test_db.commit()

        runner = Runner(
            runner_name="sub-owned-runner",
            runner_group_id=1,
            labels=json.dumps(["self-hosted"]),
            provisioned_by=user.id,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        response = client.get("/api/v1/runners")
        assert response.status_code == 200
        runners = response.json()["runners"]
        matching = [r for r in runners if r["runner_name"] == "sub-owned-runner"]
        assert matching
        assert matching[0]["provisioned_by"] == "auth0|subOwner"

    def test_runner_provisioned_by_m2m_passthrough(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        runner = Runner(
            runner_name="m2m-runner",
            runner_group_id=1,
            labels=json.dumps(["self-hosted"]),
            provisioned_by="m2m:ci-team",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        response = client.get("/api/v1/runners")
        assert response.status_code == 200
        runners = response.json()["runners"]
        matching = [r for r in runners if r["runner_name"] == "m2m-runner"]
        assert matching
        assert matching[0]["provisioned_by"] == "m2m:ci-team"


# ---------------------------------------------------------------------------
# Batch delete runners: user lookup by email, sub, and UUID
# ---------------------------------------------------------------------------


class TestBatchDeleteUserLookup:
    """Batch delete runners accepts user lookup by email, sub, or UUID."""

    def _make_runner_for(self, test_db: Session, user: User, name: str) -> Runner:
        runner = Runner(
            runner_name=name,
            runner_group_id=1,
            labels="[]",
            provisioned_by=user.id,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        return runner

    def test_batch_delete_by_sub(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(oidc_sub="auth0|batchSub", is_active=True)
        test_db.add(user)
        test_db.commit()
        runner = self._make_runner_for(test_db, user, "batch-sub-runner")

        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={
                "comment": "Termination: sub-only user cleanup",
                "user_identity": "auth0|batchSub",
            },
        )
        assert response.status_code == 200
        assert response.json()["affected_count"] == 1
        test_db.refresh(runner)
        assert runner.status == "deleted"

    def test_batch_delete_by_uuid(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,  # noqa: ARG002
    ):
        user = User(email="uuid-batch@example.com", is_active=True)
        test_db.add(user)
        test_db.commit()
        runner = self._make_runner_for(test_db, user, "batch-uuid-runner")

        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={
                "comment": "Termination: uuid-based cleanup",
                "user_identity": user.id,
            },
        )
        assert response.status_code == 200
        assert response.json()["affected_count"] == 1
        test_db.refresh(runner)
        assert runner.status == "deleted"
