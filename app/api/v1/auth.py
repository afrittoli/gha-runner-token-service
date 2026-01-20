"""Authentication endpoints for dashboard."""

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, AuthenticatedUser
from app.config import get_settings
from app.database import get_db
from app.models import Runner, SecurityEvent


router = APIRouter()


@router.get("/auth/me")
async def get_current_user_info(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current user information and roles.

    Returns:
        {
            "user_id": "user@example.com",
            "oidc_sub": "auth0|...",
            "is_admin": false,
            "roles": ["user"]
        }

    Raises:
        HTTPException: If user is not authenticated (401)
    """
    settings = get_settings()

    # Determine if user is admin
    admin_identities = [
        identity.strip()
        for identity in settings.admin_identities.split(",")
        if identity.strip()
    ]
    is_admin = current_user.identity in admin_identities

    return {
        "user_id": current_user.identity,
        "oidc_sub": current_user.sub or current_user.identity,
        "is_admin": is_admin,
        "roles": ["admin"] if is_admin else ["user"],
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
        runner_name = event.runner_name or "unknown"
        recent_events_list.append(
            {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "description": f"{event.event_type}: {runner_name}",
            }
        )

    return stats
