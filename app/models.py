"""Database models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from app.database import Base


def utcnow() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class Runner(Base):
    """Runner registration and state tracking."""

    __tablename__ = "runners"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Runner information
    runner_name = Column(
        String, nullable=False, index=True
    )  # Not unique - allows reuse after deletion
    github_runner_id = Column(
        Integer, nullable=True, index=True
    )  # Set after registration
    runner_group_id = Column(Integer, nullable=False)
    labels = Column(Text, nullable=False)  # JSON array stored as text
    ephemeral = Column(Boolean, default=False, nullable=False)
    disable_update = Column(Boolean, default=False, nullable=False)

    # Ownership and authentication
    provisioned_by = Column(String, nullable=False, index=True)  # OIDC identity
    oidc_sub = Column(String, nullable=True)  # OIDC subject claim

    # Team association (nullable for backward compatibility)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True, index=True)
    team_name = Column(String, nullable=True)  # Denormalized for queries

    # State
    status = Column(
        String, nullable=False, default="pending", index=True
    )  # pending, active, offline, deleted

    # GitHub URL
    github_url = Column(String, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    registered_at = Column(DateTime, nullable=True)  # When runner appeared in GitHub
    deleted_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_runners_status_created", "status", "created_at"),
        Index("ix_runners_provisioned_by_status", "provisioned_by", "status"),
        Index("ix_runners_team_status", "team_id", "status"),
    )


class AuditLog(Base):
    """Audit log for all operations."""

    __tablename__ = "audit_log"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event information
    event_type = Column(
        String, nullable=False, index=True
    )  # provision, deprovision, update, etc.
    runner_id = Column(String, nullable=True, index=True)
    runner_name = Column(String, nullable=True, index=True)

    # User information
    user_identity = Column(String, nullable=False, index=True)
    oidc_sub = Column(String, nullable=True)

    # Request information
    request_ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Event data (JSON stored as text)
    event_data = Column(Text, nullable=True)

    # Result
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=utcnow, index=True)


class GitHubRunnerCache(Base):
    """Cache of GitHub runner data."""

    __tablename__ = "github_runners_cache"

    # Primary key
    github_runner_id = Column(Integer, primary_key=True)

    # Runner data
    runner_name = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)  # online, offline
    busy = Column(Boolean, nullable=False, default=False)
    labels = Column(Text, nullable=False)  # JSON array

    # Runner details
    os = Column(String, nullable=True)

    # Cache metadata
    cached_at = Column(DateTime, nullable=False, default=utcnow)
    last_seen_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_cache_name_status", "runner_name", "status"),)


class User(Base):
    """Authorized users for the runner token service."""

    __tablename__ = "users"

    # Primary key - auto-generated UUID
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # OIDC identity fields
    email = Column(String, nullable=True, unique=True, index=True)  # Primary identifier
    oidc_sub = Column(
        String, nullable=True, unique=True, index=True
    )  # OIDC subject claim

    # Display information
    display_name = Column(String, nullable=True)  # For dashboard display

    # Authorization flags
    is_admin = Column(
        Boolean, default=False, nullable=False
    )  # Replaces ADMIN_IDENTITIES
    is_active = Column(Boolean, default=True, nullable=False)  # Soft disable

    # API access controls
    can_use_jit = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    last_login_at = Column(DateTime, nullable=True)  # Track last authentication

    # Audit
    created_by = Column(String, nullable=True)  # Admin who created this user

    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
        Index("ix_users_oidc_sub_active", "oidc_sub", "is_active"),
    )


class SecurityEvent(Base):
    """Security violation events for monitoring and alerting."""

    __tablename__ = "security_events"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event classification
    event_type = Column(
        String, nullable=False, index=True
    )  # label_violation, quota_exceeded, etc.
    severity = Column(String, nullable=False, index=True)  # low, medium, high, critical

    # Runner information
    runner_id = Column(String, nullable=True, index=True)
    runner_name = Column(String, nullable=True)
    github_runner_id = Column(Integer, nullable=True)

    # User information
    user_identity = Column(String, nullable=False, index=True)
    oidc_sub = Column(String, nullable=True)

    # Violation details
    violation_data = Column(Text, nullable=False)  # JSON with violation specifics
    action_taken = Column(String, nullable=True)  # deleted, blocked, alerted

    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=utcnow, index=True)

    __table_args__ = (
        Index("ix_security_events_type_severity", "event_type", "severity"),
        Index("ix_security_events_user_timestamp", "user_identity", "timestamp"),
    )


class SyncState(Base):
    """Sync worker state and coordination.

    This table maintains a single row (id=1) that tracks the sync worker's
    status, heartbeat, and last sync results. Used for leader election
    coordination and monitoring.
    """

    __tablename__ = "sync_state"

    # Primary key - enforced to be exactly 1
    id = Column(Integer, primary_key=True, default=1)

    # Worker identification
    worker_hostname = Column(String, nullable=False)  # Current leader's hostname
    worker_heartbeat = Column(
        DateTime, nullable=False, index=True
    )  # Last heartbeat from leader

    # Sync execution tracking
    last_sync_time = Column(DateTime, nullable=True)  # When last sync completed
    last_sync_result = Column(Text, nullable=True)  # JSON with sync results
    last_sync_error = Column(Text, nullable=True)  # Last error message if any

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        # Ensure only one row can exist (id must be 1)
        # SQLite: Enforced at application level
        # PostgreSQL: Enforced by database constraint
        CheckConstraint("id = 1", name="sync_state_single_row"),
        Index("ix_sync_state_heartbeat", "worker_heartbeat"),
    )


class OAuthClient(Base):
    """OAuth M2M clients registered for team-level access.

    Each record links an Auth0 M2M ``client_id`` to a team. When gharts
    receives a JWT with a ``team`` claim it validates that the sub/client is
    known and active. This table also provides an audit trail for credential
    rotation and activity monitoring.
    """

    __tablename__ = "oauth_clients"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Auth0 client_id (matches ``sub`` claim in client_credentials tokens)
    client_id = Column(String, nullable=False, unique=True, index=True)

    # Team association
    team_id = Column(
        String,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Human-readable label
    description = Column(Text, nullable=True)

    # Soft disable
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=utcnow)
    created_by = Column(String, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_oauth_clients_team_active", "team_id", "is_active"),)


class Team(Base):
    """Team for organizing users and managing runner policies."""

    __tablename__ = "teams"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Team identification
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Label policy
    required_labels = Column(Text, nullable=False)  # JSON array: always included
    optional_label_patterns = Column(Text, nullable=True)  # JSON array: regex patterns

    # Quota
    max_runners = Column(Integer, nullable=True)  # Team-wide quota

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    deactivation_reason = Column(Text, nullable=True)
    deactivated_at = Column(DateTime, nullable=True)
    deactivated_by = Column(String, nullable=True)  # Admin who deactivated

    # Metadata
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=True)  # Admin who created team

    __table_args__ = (Index("ix_teams_name_active", "name", "is_active"),)


class UserTeamMembership(Base):
    """Many-to-many relationship between users and teams."""

    __tablename__ = "user_team_memberships"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign keys
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id = Column(
        String,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Membership metadata
    joined_at = Column(DateTime, nullable=False, default=utcnow)
    added_by = Column(String, nullable=True)  # Admin who added user to team

    __table_args__ = (
        Index("ix_user_team_user", "user_id"),
        Index("ix_user_team_team", "team_id"),
        Index("ix_user_team_unique", "user_id", "team_id", unique=True),
    )
