"""Demo-only database models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
