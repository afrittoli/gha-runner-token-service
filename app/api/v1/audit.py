"""Audit log API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.auth.token_types import TokenType
from app.database import get_db
from app.models import AuditLog, Team, UserTeamMembership
from app.schemas import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


def _get_user_team_ids(user: AuthenticatedUser, db: Session) -> list[str]:
    """Return the list of team IDs the user is a member of.

    - M2M token: single team from JWT claim.
    - Individual user: all teams from DB membership.
    """
    if user.token_type == TokenType.M2M_TEAM and user.team:
        return [user.team.id]

    if user.user_id is None:
        return []

    rows = (
        db.query(UserTeamMembership.team_id)
        .filter(UserTeamMembership.user_id == user.user_id)
        .all()
    )
    return [row.team_id for row in rows]


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    event_type: Optional[str] = Query(default=None),
    user_identity: Optional[str] = Query(default=None),
    team: Optional[str] = Query(
        default=None,
        description=("Filter by team name. Non-admins must be a member of that team."),
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List audit logs.

    **Required Authentication:** OIDC Bearer token

    **Access Control:**
    - Admins can see all logs and filter by user or team
    - Standard users see logs for all their teams (or a specific team)

    **Query Parameters:**
    - **event_type**: Filter by event type
    - **user_identity**: Filter by user identity (Admin only)
    - **team**: Filter by team name
    - **limit**: Maximum number of logs to return (1-200)
    - **offset**: Offset for pagination
    """
    query = db.query(AuditLog)

    # Apply RBAC
    if not user.is_admin:
        if team:
            # Validate the requested team and membership
            team_obj = db.query(Team).filter(Team.name == team).first()
            if team_obj is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Team '{team}' not found",
                )
            user_team_ids = _get_user_team_ids(user, db)
            if team_obj.id not in user_team_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not a member of that team",
                )
            query = query.filter(AuditLog.team_id == team_obj.id)
        else:
            # Default: show logs for all teams the caller belongs to
            user_team_ids = _get_user_team_ids(user, db)
            if user_team_ids:
                query = query.filter(AuditLog.team_id.in_(user_team_ids))
            else:
                # User has no team memberships — return empty
                query = query.filter(False)
    else:
        # Admin path
        if team:
            team_obj = db.query(Team).filter(Team.name == team).first()
            if team_obj is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Team '{team}' not found",
                )
            query = query.filter(AuditLog.team_id == team_obj.id)
        elif user_identity:
            # Admins can filter by user
            query = query.filter(AuditLog.user_identity == user_identity)
        # else: admin without filters — no restriction (all logs)

    # Apply event type filter
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    # Get total count
    total = query.count()

    # Apply pagination and sorting
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()

    log_responses = []
    for log in logs:
        # Parse event_data JSON if it's a string
        event_data = None
        if log.event_data:
            try:
                event_data = json.loads(log.event_data)
            except (json.JSONDecodeError, TypeError):
                event_data = {"raw": log.event_data}

        # Resolve team name from team_id if present
        team_name: Optional[str] = None
        if log.team_id:
            team_row = db.query(Team.name).filter(Team.id == log.team_id).first()
            if team_row:
                team_name = team_row.name

        log_responses.append(
            AuditLogResponse(
                id=log.id,
                event_type=log.event_type,
                runner_id=log.runner_id,
                runner_name=log.runner_name,
                user_identity=log.user_identity,
                oidc_sub=log.oidc_sub,
                request_ip=log.request_ip,
                user_agent=log.user_agent,
                event_data=event_data,
                success=log.success,
                error_message=log.error_message,
                timestamp=log.timestamp,
                team_id=log.team_id,
                team_name=team_name,
            )
        )

    return AuditLogListResponse(logs=log_responses, total=total)
