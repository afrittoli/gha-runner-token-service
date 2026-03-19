"""Team management API endpoints."""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_db
from app.models import AuditLog, Runner, SecurityEvent, Team, User, UserTeamMembership
from app.schemas import (
    AddTeamMemberRequest,
    SecurityEventResponse,
    TeamAuditLogListResponse,
    TeamCreate,
    TeamDeactivate,
    TeamListResponse,
    TeamMemberResponse,
    TeamMembersListResponse,
    TeamResponse,
    TeamSecurityEventListResponse,
    TeamUpdate,
    UserTeamsResponse,
)
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])

# Stable virtual ID for the synthetic admins team (not stored in DB)
VIRTUAL_ADMIN_TEAM_ID = "00000000-0000-0000-0000-000000000001"
_VIRTUAL_ADMIN_TEAM_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _build_virtual_admin_team(db: Session) -> TeamResponse:
    """Build a synthetic TeamResponse for admins from is_admin users."""
    admin_users = (
        db.query(User)
        .filter(User.is_admin == True, User.is_active == True)  # noqa: E712
        .all()
    )
    return TeamResponse(
        id=VIRTUAL_ADMIN_TEAM_ID,
        name="admins",
        description="System team — all admin users",
        required_labels=[],
        optional_label_patterns=None,
        max_runners=None,
        is_active=True,
        created_at=_VIRTUAL_ADMIN_TEAM_EPOCH,
        updated_at=_VIRTUAL_ADMIN_TEAM_EPOCH,
        created_by="system",
        member_count=len(admin_users),
        active_runner_count=0,
    )


def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Require admin privileges for team management.

    Args:
        user: Authenticated user

    Returns:
        Authenticated user if admin

    Raises:
        HTTPException: If user is not admin
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for team management",
        )
    return user


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    team_data: TeamCreate,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new team.

    Requires admin privileges.

    Args:
        team_data: Team creation data
        admin: Authenticated admin user
        db: Database session

    Returns:
        Created team information

    Raises:
        HTTPException: If team name already exists or validation fails
    """
    service = TeamService(db)

    try:
        team = service.create_team(
            name=team_data.name,
            required_labels=team_data.required_labels,
            description=team_data.description,
            optional_label_patterns=team_data.optional_label_patterns,
            max_runners=team_data.max_runners,
            created_by=admin.identity,
        )

        return TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            required_labels=json.loads(team.required_labels),
            optional_label_patterns=(
                json.loads(team.optional_label_patterns)
                if team.optional_label_patterns
                else None
            ),
            max_runners=team.max_runners,
            is_active=team.is_active,
            created_at=team.created_at,
            updated_at=team.updated_at,
            created_by=team.created_by,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=TeamListResponse,
)
async def list_teams(
    include_inactive: bool = Query(
        default=False, description="Include deactivated teams"
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all teams.

    Regular users see only active teams they belong to.
    Admins can see all teams including inactive ones.

    Args:
        include_inactive: Include deactivated teams (admin only)
        limit: Maximum number of teams to return
        offset: Number of teams to skip
        user: Authenticated user
        db: Database session

    Returns:
        List of teams with metadata
    """
    service = TeamService(db)

    # Non-admins can only see active teams they belong to
    if not user.is_admin:
        if include_inactive:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can view inactive teams",
            )
        # Get user's teams only
        if user.db_user:
            teams = service.get_user_teams(user.db_user.id)
        else:
            teams = []
    else:
        # Admins see all teams
        teams = service.list_teams(
            include_inactive=include_inactive,
            limit=limit,
            offset=offset,
        )

    # Convert to response format with stats
    team_responses = []
    for team in teams:
        # Get member count
        members = service.get_team_members(team.id)
        member_count = len(members)

        # Get active runner count
        active_runners = (
            db.query(Runner)
            .filter(
                Runner.team_id == team.id,
                Runner.status.in_(["pending", "active"]),
            )
            .count()
        )

        team_responses.append(
            TeamResponse(
                id=team.id,
                name=team.name,
                description=team.description,
                required_labels=json.loads(team.required_labels),
                optional_label_patterns=(
                    json.loads(team.optional_label_patterns)
                    if team.optional_label_patterns
                    else None
                ),
                max_runners=team.max_runners,
                is_active=team.is_active,
                created_at=team.created_at,
                updated_at=team.updated_at,
                created_by=team.created_by,
                deactivated_at=team.deactivated_at,
                deactivated_by=team.deactivated_by,
                deactivation_reason=team.deactivation_reason,
                member_count=member_count,
                active_runner_count=active_runners,
            )
        )

    # Prepend virtual admin team for admins (only on first page)
    if user.is_admin and offset == 0:
        team_responses.insert(0, _build_virtual_admin_team(db))

    return TeamListResponse(
        teams=team_responses,
        total=len(team_responses),
    )


@router.get(
    "/{team_id}",
    response_model=TeamResponse,
)
async def get_team(
    team_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get team details.

    Regular users can only view teams they belong to.
    Admins can view any team.

    Args:
        team_id: Team ID
        user: Authenticated user
        db: Database session

    Returns:
        Team information

    Raises:
        HTTPException: If team not found or access denied
    """
    service = TeamService(db)
    team = service.get_team(team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check access: admin or team member
    if not user.is_admin:
        if not user.db_user or not service.is_user_in_team(user.db_user.id, team_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: not a team member",
            )

    # Get stats
    members = service.get_team_members(team.id)
    member_count = len(members)

    active_runners = (
        db.query(Runner)
        .filter(
            Runner.team_id == team.id,
            Runner.status.in_(["pending", "active"]),
        )
        .count()
    )

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        required_labels=json.loads(team.required_labels),
        optional_label_patterns=(
            json.loads(team.optional_label_patterns)
            if team.optional_label_patterns
            else None
        ),
        max_runners=team.max_runners,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at,
        created_by=team.created_by,
        deactivated_at=team.deactivated_at,
        deactivated_by=team.deactivated_by,
        deactivation_reason=team.deactivation_reason,
        member_count=member_count,
        active_runner_count=active_runners,
    )


@router.patch(
    "/{team_id}",
    response_model=TeamResponse,
)
async def update_team(
    team_id: str,
    team_data: TeamUpdate,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update team configuration.

    Requires admin privileges.

    Args:
        team_id: Team ID
        team_data: Team update data
        admin: Authenticated admin user
        db: Database session

    Returns:
        Updated team information

    Raises:
        HTTPException: If team not found or validation fails
    """
    service = TeamService(db)

    try:
        team = service.update_team(
            team_id=team_id,
            description=team_data.description,
            required_labels=team_data.required_labels,
            optional_label_patterns=team_data.optional_label_patterns,
            max_runners=team_data.max_runners,
        )

        return TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            required_labels=json.loads(team.required_labels),
            optional_label_patterns=(
                json.loads(team.optional_label_patterns)
                if team.optional_label_patterns
                else None
            ),
            max_runners=team.max_runners,
            is_active=team.is_active,
            created_at=team.created_at,
            updated_at=team.updated_at,
            created_by=team.created_by,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{team_id}/deactivate",
    response_model=TeamResponse,
)
async def deactivate_team(
    team_id: str,
    deactivation_data: TeamDeactivate,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Deactivate a team.

    Requires admin privileges.

    Args:
        team_id: Team ID
        deactivation_data: Deactivation reason
        admin: Authenticated admin user
        db: Database session

    Returns:
        Deactivated team information

    Raises:
        HTTPException: If team not found or already deactivated
    """
    service = TeamService(db)

    try:
        team = service.deactivate_team(
            team_id=team_id,
            reason=deactivation_data.reason,
            deactivated_by=admin.identity,
        )

        return TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            required_labels=json.loads(team.required_labels),
            optional_label_patterns=(
                json.loads(team.optional_label_patterns)
                if team.optional_label_patterns
                else None
            ),
            max_runners=team.max_runners,
            is_active=team.is_active,
            created_at=team.created_at,
            updated_at=team.updated_at,
            created_by=team.created_by,
            deactivated_at=team.deactivated_at,
            deactivated_by=team.deactivated_by,
            deactivation_reason=team.deactivation_reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{team_id}/reactivate",
    response_model=TeamResponse,
)
async def reactivate_team(
    team_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Reactivate a deactivated team.

    Requires admin privileges.

    Args:
        team_id: Team ID
        admin: Authenticated admin user
        db: Database session

    Returns:
        Reactivated team information

    Raises:
        HTTPException: If team not found or already active
    """
    service = TeamService(db)

    try:
        team = service.reactivate_team(team_id=team_id)

        return TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            required_labels=json.loads(team.required_labels),
            optional_label_patterns=(
                json.loads(team.optional_label_patterns)
                if team.optional_label_patterns
                else None
            ),
            max_runners=team.max_runners,
            is_active=team.is_active,
            created_at=team.created_at,
            updated_at=team.updated_at,
            created_by=team.created_by,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Team Membership Endpoints


@router.get(
    "/{team_id}/members",
    response_model=TeamMembersListResponse,
)
async def get_team_members(
    team_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get team members.

    Regular users can only view members of teams they belong to.
    Admins can view members of any team.

    Args:
        team_id: Team ID
        user: Authenticated user
        db: Database session

    Returns:
        List of team members

    Raises:
        HTTPException: If team not found or access denied
    """
    # Handle virtual admin team
    if team_id == VIRTUAL_ADMIN_TEAM_ID:
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )
        admin_users = (
            db.query(User)
            .filter(User.is_admin == True, User.is_active == True)  # noqa: E712
            .all()
        )
        member_responses = [
            TeamMemberResponse(
                user_id=u.id,
                email=u.email,
                display_name=u.display_name,
                joined_at=u.created_at,
                added_by="system",
            )
            for u in admin_users
        ]
        return TeamMembersListResponse(
            team_id=VIRTUAL_ADMIN_TEAM_ID,
            team_name="admins",
            members=member_responses,
            total=len(member_responses),
        )

    service = TeamService(db)
    team = service.get_team(team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check access
    if not user.is_admin:
        if not user.db_user or not service.is_user_in_team(user.db_user.id, team_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: not a team member",
            )

    members = service.get_team_members(team_id)

    # Get membership details
    member_responses = []
    for member in members:
        # Get membership info
        membership = (
            db.query(UserTeamMembership)
            .filter(
                UserTeamMembership.user_id == member.id,
                UserTeamMembership.team_id == team_id,
            )
            .first()
        )

        member_responses.append(
            TeamMemberResponse(
                user_id=member.id,
                email=member.email,
                display_name=member.display_name,
                joined_at=membership.joined_at if membership else member.created_at,
                added_by=membership.added_by if membership else None,
            )
        )

    return TeamMembersListResponse(
        team_id=team.id,
        team_name=team.name,
        members=member_responses,
        total=len(member_responses),
    )


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    team_id: str,
    member_data: AddTeamMemberRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Add a user to a team.

    Requires admin privileges.

    Args:
        team_id: Team ID
        member_data: User to add
        admin: Authenticated admin user
        db: Database session

    Returns:
        Added member information

    Raises:
        HTTPException: If team/user not found or user already in team
    """
    if team_id == VIRTUAL_ADMIN_TEAM_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin team membership is managed via user is_admin flag",
        )

    service = TeamService(db)

    try:
        membership = service.add_user_to_team(
            user_id=member_data.user_id,
            team_id=team_id,
            added_by=admin.identity,
        )

        # Get user details
        user_obj = db.query(User).filter(User.id == member_data.user_id).first()

        return TeamMemberResponse(
            user_id=membership.user_id,
            email=user_obj.email if user_obj else None,
            display_name=user_obj.display_name if user_obj else None,
            joined_at=membership.joined_at,
            added_by=membership.added_by,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_team_member(
    team_id: str,
    user_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a user from a team.

    Requires admin privileges.

    Args:
        team_id: Team ID
        user_id: User ID to remove
        admin: Authenticated admin user
        db: Database session

    Raises:
        HTTPException: If membership not found
    """
    if team_id == VIRTUAL_ADMIN_TEAM_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin team membership is managed via user is_admin flag",
        )

    service = TeamService(db)

    try:
        service.remove_user_from_team(user_id=user_id, team_id=team_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/users/{user_id}/teams",
    response_model=UserTeamsResponse,
)
async def get_user_teams(
    user_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get teams a user belongs to.

    Users can only view their own teams unless they are admin.

    Args:
        user_id: User ID
        user: Authenticated user
        db: Database session

    Returns:
        List of teams user belongs to

    Raises:
        HTTPException: If access denied
    """
    # Check access: user can only see their own teams unless admin
    if not user.is_admin:
        if not user.db_user or user.db_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: can only view your own teams",
            )

    service = TeamService(db)
    teams = service.get_user_teams(user_id)

    team_responses = []
    for team in teams:
        # Get stats
        members = service.get_team_members(team.id)
        member_count = len(members)

        active_runners = (
            db.query(Runner)
            .filter(
                Runner.team_id == team.id,
                Runner.status.in_(["pending", "active"]),
            )
            .count()
        )

        team_responses.append(
            TeamResponse(
                id=team.id,
                name=team.name,
                description=team.description,
                required_labels=json.loads(team.required_labels),
                optional_label_patterns=(
                    json.loads(team.optional_label_patterns)
                    if team.optional_label_patterns
                    else None
                ),
                max_runners=team.max_runners,
                is_active=team.is_active,
                created_at=team.created_at,
                updated_at=team.updated_at,
                created_by=team.created_by,
                member_count=member_count,
                active_runner_count=active_runners,
            )
        )

    return UserTeamsResponse(
        user_id=user_id,
        teams=team_responses,
        total=len(team_responses),
    )


# ---------------------------------------------------------------------------
# Team-scoped audit log and security events endpoints (non-admin access)
# ---------------------------------------------------------------------------


def _check_team_access(
    team_id: str,
    user: AuthenticatedUser,
    service: TeamService,
) -> Team:
    """Resolve team and verify the caller has access.

    Returns the Team object if access is granted.
    Raises HTTPException 404 / 403 otherwise.
    """
    team = service.get_team(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if not user.is_admin:
        if not user.db_user or not service.is_user_in_team(user.db_user.id, team_id):
            # M2M tokens: check via user.team
            if not (user.team and user.team.id == team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: not a member of this team",
                )

    return team


@router.get(
    "/{team_id}/audit-logs",
    response_model=TeamAuditLogListResponse,
)
async def get_team_audit_logs(
    team_id: str,
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List audit logs scoped to a team.

    **Access Control:**
    - Team members (and admins) can access this endpoint.

    **Query Parameters:**
    - **event_type**: Filter by event type
    - **limit**: Maximum number of logs to return (1-200)
    - **offset**: Offset for pagination
    """
    import json as _json

    service = TeamService(db)
    team = _check_team_access(team_id, user, service)

    query = db.query(AuditLog).filter(AuditLog.team_id == team_id)

    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()

    from app.schemas import AuditLogResponse as _ALR

    log_responses = []
    for log in logs:
        event_data = None
        if log.event_data:
            try:
                event_data = _json.loads(log.event_data)
            except (ValueError, TypeError):
                event_data = {"raw": log.event_data}

        log_responses.append(
            _ALR(
                id=log.id,
                event_type=log.event_type,
                runner_id=log.runner_id,
                runner_name=log.runner_name,
                team_id=team.id,
                team_name=team.name,
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

    return TeamAuditLogListResponse(
        team_id=team.id,
        team_name=team.name,
        logs=log_responses,
        total=total,
    )


@router.get(
    "/{team_id}/security-events",
    response_model=TeamSecurityEventListResponse,
)
async def get_team_security_events(
    team_id: str,
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List security events scoped to a team.

    **Access Control:**
    - Team members (and admins) can access this endpoint.

    **Query Parameters:**
    - **event_type**: Filter by event type
    - **severity**: Filter by severity (low, medium, high, critical)
    - **limit**: Maximum number of events to return (1-200)
    - **offset**: Offset for pagination
    """
    import json as _json

    service = TeamService(db)
    team = _check_team_access(team_id, user, service)

    query = db.query(SecurityEvent).filter(SecurityEvent.team_id == team_id)

    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)

    total = query.count()
    events = (
        query.order_by(SecurityEvent.timestamp.desc()).limit(limit).offset(offset).all()
    )

    event_responses = []
    for ev in events:
        violation_data: dict = {}
        if ev.violation_data:
            try:
                violation_data = _json.loads(ev.violation_data)
            except (ValueError, TypeError):
                violation_data = {"raw": ev.violation_data}

        event_responses.append(
            SecurityEventResponse(
                id=ev.id,
                event_type=ev.event_type,
                severity=ev.severity,
                runner_id=ev.runner_id,
                runner_name=ev.runner_name,
                github_runner_id=ev.github_runner_id,
                team_id=team.id,
                team_name=team.name,
                user_identity=ev.user_identity,
                violation_data=violation_data,
                action_taken=ev.action_taken,
                timestamp=ev.timestamp,
            )
        )

    return TeamSecurityEventListResponse(
        team_id=team.id,
        team_name=team.name,
        events=event_responses,
        total=total,
    )
