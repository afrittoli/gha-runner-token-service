"""Authentication endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.auth.token_types import TokenType
from app.database import get_db
from app.models import Team, UserTeamMembership


router = APIRouter()


def _get_user_teams(current_user: AuthenticatedUser, db: Session) -> list[dict]:
    """Return team summaries visible to the authenticated user.

    - M2M token: the single team from the JWT claim.
    - Individual user: all teams the user is a member of.
    - Admin with no team memberships: empty list (use admin team endpoint).
    """
    if current_user.token_type == TokenType.M2M_TEAM and current_user.team:
        t = current_user.team
        return [{"id": t.id, "name": t.name}]

    if current_user.user_id is None:
        return []

    rows = (
        db.query(Team.id, Team.name)
        .join(
            UserTeamMembership,
            UserTeamMembership.team_id == Team.id,
        )
        .filter(
            UserTeamMembership.user_id == current_user.user_id,
            Team.is_active.is_(True),
        )
        .all()
    )
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/auth/me")
async def get_current_user_info(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get current user information, roles, and team memberships.

    Returns user information from the User table, including admin status,
    API permissions, and the list of teams the user belongs to.

    Returns:
        {
            "user_id": "uuid",
            "email": "user@example.com",
            "display_name": "User Name",
            "oidc_sub": "auth0|...",
            "is_admin": false,
            "can_use_jit": true,
            "roles": ["user"],
            "teams": [{"id": "...", "name": "platform-team"}, ...]
        }

    Raises:
        HTTPException: If user is not authenticated (401) or not authorized (403)
    """
    roles = ["admin"] if current_user.is_admin else ["user"]
    teams = _get_user_teams(current_user, db)

    return {
        "user_id": current_user.user_id or current_user.identity,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "oidc_sub": current_user.sub or current_user.identity,
        "is_admin": current_user.is_admin,
        "can_use_jit": current_user.can_use_jit,
        "roles": roles,
        "teams": teams,
    }
