"""Database models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, Index

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

    # State
    status = Column(
        String, nullable=False, default="pending", index=True
    )  # pending, active, offline, deleted

    # Provisioning method (registration_token or jit)
    provisioning_method = Column(
        String, nullable=False, default="registration_token"
    )  # "registration_token" or "jit"
    provisioned_labels = Column(
        Text, nullable=True
    )  # Original labels at provisioning time (JSON array)

    # Tokens (masked in logs)
    registration_token = Column(Text, nullable=True)  # Cleared after use
    registration_token_expires_at = Column(DateTime, nullable=True)

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


class LabelPolicy(Base):
    """Label policy enforcement for runner provisioning."""

    __tablename__ = "label_policies"

    # Primary key
    user_identity = Column(String, primary_key=True, index=True)

    # Policy configuration
    allowed_labels = Column(Text, nullable=False)  # JSON array of allowed labels
    label_patterns = Column(Text, nullable=True)  # JSON array of regex patterns

    # Additional constraints
    max_runners = Column(Integer, nullable=True)  # Maximum concurrent runners
    require_approval = Column(
        Boolean, default=False, nullable=False
    )  # Require admin approval

    # Metadata
    description = Column(Text, nullable=True)  # Policy description
    created_by = Column(String, nullable=True)  # Admin who created policy

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


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

    # API access controls (per-method authorization)
    can_use_registration_token = Column(Boolean, default=True, nullable=False)
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


class ImpersonationSession(Base):
    """Track active impersonation sessions for admin oversight."""

    __tablename__ = "impersonation_sessions"

    # Primary key - JWT token ID (jti claim)
    id = Column(String, primary_key=True)

    # Admin who is impersonating
    admin_identity = Column(String, nullable=False, index=True)
    admin_oidc_sub = Column(String, nullable=True)

    # Target user being impersonated
    target_user_id = Column(String, nullable=False, index=True)
    target_user_email = Column(String, nullable=False)
    target_user_oidc_sub = Column(String, nullable=True)

    # Session details
    created_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        Index("ix_impersonation_admin_active", "admin_identity", "is_active"),
        Index("ix_impersonation_target_active", "target_user_id", "is_active"),
    )
