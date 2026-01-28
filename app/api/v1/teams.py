"""Team management API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_db
from app.models import Runner, User, UserTeamMembership
from app.schemas import (
    AddTeamMemberRequest,
    TeamCreate,
    TeamDeactivate,
    TeamListResponse,
    TeamMemberResponse,
    TeamMembersListResponse,
    TeamResponse,
    TeamUpdate,
    UserTeamsResponse,
)
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


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


# Made with Bob
