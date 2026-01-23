"""Authentication endpoints for dashboard."""

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_db
from app.models import Runner, SecurityEvent


router = APIRouter()


@router.get("/auth/me")
async def get_current_user_info(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current user information and roles.

    Returns user information from the User table, including admin status
    and API permissions.

    Returns:
        {
            "user_id": "uuid",
            "email": "user@example.com",
            "display_name": "User Name",
            "oidc_sub": "auth0|...",
            "is_admin": false,
            "can_use_registration_token": true,
            "can_use_jit": true,
            "roles": ["user"]
        }

    Raises:
        HTTPException: If user is not authenticated (401) or not authorized (403)
    """
    # Use the database-backed authorization from AuthenticatedUser
    roles = ["admin"] if current_user.is_admin else ["user"]

    return {
        "user_id": current_user.user_id or current_user.identity,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "oidc_sub": current_user.sub or current_user.identity,
        "is_admin": current_user.is_admin,
        "can_use_registration_token": current_user.can_use_registration_token,
        "can_use_jit": current_user.can_use_jit,
        "roles": roles,
    }


@router.get("/dashboard/stats", status_code=status.HTTP_200_OK)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get dashboard statistics for home page.

    Returns runner counts and recent activity for dashboard display.

    Returns:
        {
            "total": 5,
            "active": 3,
            "offline": 1,
            "pending": 1,
            "recent_events": [
                {
                    "timestamp": "2026-01-20T...",
                    "event_type": "label_violation",
                    "severity": "high",
                    "description": "..."
                }
            ]
        }
    """
    # Get runner counts by status
    runners = db.query(Runner).filter(Runner.status != "deleted").all()

    stats: dict[str, Any] = {
        "total": len(runners),
        "active": sum(1 for r in runners if r.status == "active"),
        "offline": sum(1 for r in runners if r.status == "offline"),
        "pending": sum(1 for r in runners if r.status == "pending"),
        "recent_events": [],
    }

    # Get recent security events (last 10)
    recent_events = (
        db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).limit(10).all()
    )

    for event in recent_events:
        recent_events_list: list[dict[str, Any]] = stats["recent_events"]
        recent_events_list.append(
            {
                "id": str(event.id),
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "user_identity": event.user_identity,
                "runner_id": event.runner_id,
                "runner_name": event.runner_name,
                "action_taken": event.action_taken,
            }
        )

    return stats
