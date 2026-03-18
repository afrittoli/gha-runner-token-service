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
    """Return the list of team IDs accessible to the authenticated user.

    - M2M token: exactly one team (from JWT claim).
    - Individual user: all teams the user is a member of.
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
    return [r.team_id for r in rows]


def _resolve_team_names(team_ids: list[str], db: Session) -> dict[str, str]:
    """Return a mapping of team_id → team_name for the given IDs."""
    if not team_ids:
        return {}
    rows = db.query(Team.id, Team.name).filter(Team.id.in_(team_ids)).all()
    return {row.id: row.name for row in rows}


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    event_type: Optional[str] = Query(default=None),
    user_identity: Optional[str] = Query(default=None),
    team: Optional[str] = Query(
        default=None,
        description=(
            "Filter by team name. "
            "Non-admins: must be a member of that team. "
            "Admins: any team."
        ),
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
    - Non-admin users see logs for all their teams (default) or a single
      team they belong to (when ``?team=<name>`` is supplied)

    **Query Parameters:**
    - **event_type**: Filter by event type
    - **team**: Filter by team name (non-admin: must be a member)
    - **user_identity**: Filter by user identity (Admin only)
    - **limit**: Maximum number of logs to return (1-200)
    - **offset**: Offset for pagination
    """
    query = db.query(AuditLog)

    # Apply RBAC
    if not user.is_admin:
        if team:
            # Verify the caller is a member of the requested team
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
            # Default: all teams the user belongs to
            user_team_ids = _get_user_team_ids(user, db)
            if not user_team_ids:
                # User has no teams — return empty
                return AuditLogListResponse(logs=[], total=0)
            query = query.filter(AuditLog.team_id.in_(user_team_ids))
    else:
        # Admin: optional team filter
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

    # Apply event_type filter
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    # Get total count
    total = query.count()

    # Apply pagination and sorting
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()

    # Pre-fetch team names for enrichment
    team_id_set = {log.team_id for log in logs if log.team_id}
    team_name_map = _resolve_team_names(list(team_id_set), db)

    log_responses = []
    for log in logs:
        # Parse event_data JSON if it's a string
        event_data = None
        if log.event_data:
            try:
                event_data = json.loads(log.event_data)
            except (json.JSONDecodeError, TypeError):
                event_data = {"raw": log.event_data}

        log_responses.append(
            AuditLogResponse(
                id=log.id,
                event_type=log.event_type,
                runner_id=log.runner_id,
                runner_name=log.runner_name,
                team_id=log.team_id,
                team_name=(team_name_map.get(log.team_id) if log.team_id else None),
                user_identity=log.user_identity,
                oidc_sub=log.oidc_sub,
                request_ip=log.request_ip,
                user_agent=log.user_agent,
                event_data=event_data,
                success=log.success,
                error_message=log.error_message,
                timestamp=log.timestamp,
            )
        )

    return AuditLogListResponse(logs=log_responses, total=total)
