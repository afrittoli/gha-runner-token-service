"""Demo-only API endpoints: user impersonation for demo and troubleshooting."""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session

from app.api.v1.admin import require_admin
from app.auth.dependencies import AuthenticatedUser
from app.database import get_db
from app.demo.models import ImpersonationSession
from app.models import AuditLog
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Demo"])

_IMPERSONATION_SECRET = os.environ.get(
    "DEMO_IMPERSONATION_SECRET", "demo-impersonation-secret"
)


@router.post("/impersonate/{user_id}")
async def impersonate_user(
    user_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Impersonate another user for demo purposes.

    **Required Authentication:** Admin privileges

    Allow admins to temporarily impersonate other users to test their view
    and permissions. Impersonation is logged in the audit trail and the
    original admin identity is preserved in logs.
    """
    from app.config import get_settings

    settings = get_settings()

    service = UserService(db)
    target_user = service.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )

    if not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate inactive user",
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    session_id = str(uuid.uuid4())

    payload = {
        "sub": target_user.oidc_sub or target_user.email,
        "email": target_user.email,
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "iat": now,
        "exp": expires_at,
        "jti": session_id,
        "impersonated_by": admin.identity,
        "is_impersonation": True,
    }

    impersonation_token = jwt.encode(payload, _IMPERSONATION_SECRET, algorithm="HS256")

    session = ImpersonationSession(
        id=session_id,
        admin_identity=admin.identity,
        admin_oidc_sub=admin.sub,
        target_user_id=target_user.id,
        target_user_email=target_user.email,
        target_user_oidc_sub=target_user.oidc_sub,
        expires_at=expires_at,
    )
    db.add(session)

    audit_entry = AuditLog(
        event_type="user_impersonation_started",
        runner_id=None,
        runner_name=None,
        user_identity=admin.identity,
        oidc_sub=admin.sub,
        success=True,
        error_message=None,
        event_data=json.dumps(
            {
                "target_user_id": user_id,
                "target_user_email": target_user.email,
                "target_user_oidc_sub": target_user.oidc_sub,
            }
        ),
    )
    db.add(audit_entry)
    db.commit()

    return {
        "impersonation_token": impersonation_token,
        "user": {
            "id": target_user.id,
            "email": target_user.email,
            "oidc_sub": target_user.oidc_sub,
            "display_name": target_user.display_name,
            "is_admin": target_user.is_admin,
            "is_active": target_user.is_active,
        },
        "original_admin": admin.identity,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/stop-impersonation")
async def stop_impersonation(
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Stop impersonating and return to admin identity.

    **Required Authentication:** Admin privileges
    """
    audit_entry = AuditLog(
        event_type="user_impersonation_stopped",
        runner_id=None,
        runner_name=None,
        user_identity=admin.identity,
        oidc_sub=admin.sub,
        success=True,
        error_message=None,
        event_data=json.dumps({}),
    )
    db.add(audit_entry)
    db.commit()

    return {
        "message": "Impersonation stopped",
        "admin_identity": admin.identity,
    }


@router.get("/impersonation-sessions")
async def list_impersonation_sessions(
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all active impersonation sessions.

    **Required Authentication:** Admin privileges
    """
    now = datetime.now(timezone.utc)
    sessions = (
        db.query(ImpersonationSession)
        .filter(
            ImpersonationSession.is_active.is_(True),
            ImpersonationSession.expires_at > now,
            ImpersonationSession.revoked_at.is_(None),
        )
        .order_by(ImpersonationSession.created_at.desc())
        .all()
    )

    return {
        "sessions": [
            {
                "id": session.id,
                "admin_identity": session.admin_identity,
                "target_user_id": session.target_user_id,
                "target_user_email": session.target_user_email,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
            }
            for session in sessions
        ]
    }


@router.post("/impersonation-sessions/{session_id}/revoke")
async def revoke_impersonation_session(
    session_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke a specific impersonation session.

    **Required Authentication:** Admin privileges
    """
    session = (
        db.query(ImpersonationSession)
        .filter(ImpersonationSession.id == session_id)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    session.is_active = False
    session.revoked_at = datetime.now(timezone.utc)

    audit_entry = AuditLog(
        event_type="impersonation_session_revoked",
        runner_id=None,
        runner_name=None,
        user_identity=admin.identity,
        oidc_sub=admin.sub,
        success=True,
        error_message=None,
        event_data=json.dumps(
            {
                "session_id": session_id,
                "target_user_email": session.target_user_email,
                "revoked_by": admin.identity,
            }
        ),
    )
    db.add(audit_entry)
    db.commit()

    return {"message": "Session revoked", "session_id": session_id}


@router.post("/impersonation-sessions/revoke-all")
async def revoke_all_impersonation_sessions(
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke all active impersonation sessions.

    **Required Authentication:** Admin privileges
    """
    now = datetime.now(timezone.utc)
    sessions = (
        db.query(ImpersonationSession)
        .filter(
            ImpersonationSession.is_active.is_(True),
            ImpersonationSession.revoked_at.is_(None),
        )
        .all()
    )

    count = len(sessions)
    for session in sessions:
        session.is_active = False
        session.revoked_at = now

    audit_entry = AuditLog(
        event_type="impersonation_sessions_bulk_revoked",
        runner_id=None,
        runner_name=None,
        user_identity=admin.identity,
        oidc_sub=admin.sub,
        success=True,
        error_message=None,
        event_data=json.dumps({"count": count, "revoked_by": admin.identity}),
    )
    db.add(audit_entry)
    db.commit()

    return {"message": "All sessions revoked", "count": count}
