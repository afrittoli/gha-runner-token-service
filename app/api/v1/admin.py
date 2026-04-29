"""Admin API endpoints for user and team management."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models import (
    AuditLog,
    Runner,
    SecurityEvent,
    User,
    resolve_user_display,
)
from app.schemas import (
    BatchActionResponse,
    BatchDeactivateTeamsRequest,
    BatchDeleteRunnersRequest,
    BatchDisableUsersRequest,
    BatchReactivateTeamsRequest,
    BatchRestoreUsersRequest,
    DeactivateUserRequest,
    SecurityEventListResponse,
    SecurityEventResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services.label_policy_service import LabelPolicyService
from app.services.team_service import TeamService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Require admin privileges.

    Grants access only if the user has is_admin=True in the User table.
    Use the CLI command `python -m app.cli create-admin` to bootstrap the first admin.

    Args:
        user: Authenticated user

    Returns:
        Authenticated user if admin

    Raises:
        HTTPException: If user is not admin
    """
    if user.is_admin:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin privileges required",
    )


@router.get("/security-events", response_model=SecurityEventListResponse)
async def list_security_events(
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    user_identity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List security events for monitoring and alerting.

    **Required Authentication:** Admin privileges

    **Query Parameters:**
    - **event_type**: Filter by event type (e.g., 'label_policy_violation')
    - **severity**: Filter by severity (low, medium, high, critical)
    - **user_identity**: Filter by user identity
    - **limit**: Maximum number of events to return (1-1000)
    - **offset**: Offset for pagination

    **Returns:**
    Paginated list of security events

    **Event Types:**
    - `label_policy_violation`: Label policy was violated
    - `quota_exceeded`: Runner quota was exceeded
    - `unauthorized_access`: Unauthorized access attempt

    **Severities:**
    - `low`: Informational event
    - `medium`: Potential security concern
    - `high`: Security violation detected and mitigated
    - `critical`: Severe security violation
    """
    # Resolve user_identity filter to a user_id if supplied
    resolved_user_id: Optional[str] = None
    if user_identity:
        resolved_user = (
            db.query(User)
            .filter(
                (User.id == user_identity)
                | (User.email == user_identity)
                | (User.oidc_sub == user_identity)
            )
            .first()
        )
        if resolved_user:
            resolved_user_id = resolved_user.id
        else:
            return SecurityEventListResponse(events=[], total=0)

    query = db.query(SecurityEvent)

    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    if resolved_user_id:
        query = query.filter(SecurityEvent.user_id == resolved_user_id)

    events = (
        query.order_by(SecurityEvent.timestamp.desc()).limit(limit).offset(offset).all()
    )

    event_responses = []
    for event in events:
        event_responses.append(
            SecurityEventResponse(
                id=event.id,
                event_type=event.event_type,
                severity=event.severity,
                runner_id=event.runner_id,
                runner_name=event.runner_name,
                github_runner_id=event.github_runner_id,
                user_identity=resolve_user_display(event.user_id, db),
                violation_data=json.loads(event.violation_data),
                action_taken=event.action_taken,
                timestamp=event.timestamp,
            )
        )

    total = query.count()

    return SecurityEventListResponse(events=event_responses, total=total)


@router.get("/sync/status")
async def get_sync_status_endpoint(
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Get sync service status.

    **Required Authentication:** Admin privileges

    **Returns:**
    Current sync configuration and last sync result
    """
    from app.main import get_sync_status

    return get_sync_status(db=db)


# User Management Endpoints


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new user.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Add a user to the authorization table. Users must exist in this table
    to access the API (explicit allowlist approach).

    **Required Fields:**
    At least one of `email` or `oidc_sub` must be provided.

    **Returns:**
    Created user

    **Example:**
    ```json
    {
      "email": "alice@example.com",
      "display_name": "Alice Smith",
      "is_admin": false,
      "can_use_jit": true
    }
    ```
    """
    service = UserService(db)

    # Check for existing user with same email or oidc_sub
    if user_data.email:
        existing = service.get_user_by_email(user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{user_data.email}' already exists",
            )
    if user_data.oidc_sub:
        existing = service.get_user_by_oidc_sub(user_data.oidc_sub)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with oidc_sub '{user_data.oidc_sub}' already exists",
            )

    try:
        db_user = service.create_user(
            email=user_data.email,
            oidc_sub=user_data.oidc_sub,
            display_name=user_data.display_name,
            is_admin=user_data.is_admin,
            can_use_jit=user_data.can_use_jit,
            created_by=admin.identity,
        )

        # Add user to requested teams
        if user_data.team_ids:
            team_service = TeamService(db)
            for team_id in user_data.team_ids:
                try:
                    team_service.add_user_to_team(
                        user_id=db_user.id,
                        team_id=team_id,
                        added_by=admin.identity,
                    )
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to add user to team '{team_id}': {e}",
                    )

        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            oidc_sub=db_user.oidc_sub,
            display_name=db_user.display_name,
            is_admin=db_user.is_admin,
            is_active=db_user.is_active,
            can_use_jit=db_user.can_use_jit,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
            last_login_at=db_user.last_login_at,
            created_by=db_user.created_by,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = Query(default=False),
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    List all users.

    **Required Authentication:** Admin privileges

    **Query Parameters:**
    - **limit**: Maximum number of users to return (1-1000)
    - **offset**: Offset for pagination
    - **include_inactive**: Include deactivated users (default: false)

    **Returns:**
    Paginated list of users
    """
    service = UserService(db)
    users = service.list_users(
        limit=limit, offset=offset, include_inactive=include_inactive
    )

    user_responses = [
        UserResponse(
            id=user.id,
            email=user.email,
            oidc_sub=user.oidc_sub,
            display_name=user.display_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
            can_use_jit=user.can_use_jit,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            created_by=user.created_by,
        )
        for user in users
    ]

    total = service.count_users(include_inactive=include_inactive)

    return UserListResponse(users=user_responses, total=total)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Get a specific user by ID.

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_id**: User UUID

    **Returns:**
    User information

    **Raises:**
    - 404: User not found
    """
    service = UserService(db)
    user = service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        oidc_sub=user.oidc_sub,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        can_use_jit=user.can_use_jit,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        created_by=user.created_by,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Update a user.

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_id**: User UUID

    **Request Body:**
    Only include fields to update. All fields are optional.

    **Returns:**
    Updated user

    **Raises:**
    - 404: User not found

    **Example:**
    ```json
    {
      "is_admin": true,
      "can_use_jit": false
    }
    ```
    """
    service = UserService(db)

    # Build updates dict from non-None fields
    updates = {k: v for k, v in user_data.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    user = service.update_user(user_id, **updates)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        oidc_sub=user.oidc_sub,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        can_use_jit=user.can_use_jit,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        created_by=user.created_by,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    request: DeactivateUserRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Deactivate a user (soft delete).

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_id**: User UUID

    **Request Body:**
    - **comment**: Required reason for deactivation (10-500 chars)

    **Returns:**
    204 No Content on success

    **Raises:**
    - 404: User not found

    **Note:**
    This performs a soft delete by setting `is_active=False`.
    The user can be reactivated using the `/users/{user_id}/activate` endpoint.

    **Example:**
    ```json
    {
      "comment": "User left the organization"
    }
    ```
    """
    service = UserService(db)
    label_policy_service = LabelPolicyService(db)

    # Get user info before deactivation for logging
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )

    # Prevent deactivation of the last admin user
    if user.is_admin and user.is_active:
        active_admin_count = service.count_active_admins()
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot deactivate the last active admin user. "
                    "At least one admin must remain active."
                ),
            )

    # Deactivate the user
    deactivated = service.deactivate_user(user_id)

    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )

    # Log security event
    label_policy_service.log_security_event(
        event_type="user_deactivated",
        severity="medium",
        user_id=admin.identity,
        runner_id=None,
        runner_name=None,
        violation_data={
            "comment": request.comment,
            "deactivated_user_id": user_id,
            "deactivated_user_email": user.email,
            "deactivated_user_oidc_sub": user.oidc_sub,
        },
        action_taken=f"deactivated user {user.email or user.oidc_sub}",
    )

    # Log to audit log for compliance tracking
    audit_entry = AuditLog(
        event_type="user_deactivated",
        runner_id=None,
        runner_name=None,
        user_id=admin.identity,
        success=True,
        error_message=None,
        event_data=json.dumps(
            {
                "comment": request.comment,
                "deactivated_user_id": user_id,
                "deactivated_user_email": user.email,
                "deactivated_user_oidc_sub": user.oidc_sub,
            }
        ),
    )
    db.add(audit_entry)
    db.commit()


@router.post("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Reactivate a deactivated user.

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_id**: User UUID

    **Returns:**
    Activated user

    **Raises:**
    - 404: User not found
    """
    service = UserService(db)
    activated = service.activate_user(user_id)

    if not activated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )

    user = service.get_user_by_id(user_id)
    return UserResponse(
        id=user.id,
        email=user.email,
        oidc_sub=user.oidc_sub,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        can_use_jit=user.can_use_jit,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        created_by=user.created_by,
    )


# Batch Admin Actions


@router.post("/batch/disable-users", response_model=BatchActionResponse)
async def batch_disable_users(
    request: BatchDisableUsersRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Disable multiple users in a single operation.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Quickly disable access for multiple users, e.g., during security incidents
    or organizational changes.

    **Request Body:**
    - **comment**: Required audit trail comment (10-500 chars)
    - **user_ids**: Optional list of user IDs. If null/empty, disables all non-admin users.
    - **exclude_admins**: Safety flag to exclude admin users (default: true)
    - **dry_run**: If true, preview affected users without making any changes.

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Security incident: disabling all contractor accounts pending review",
      "user_ids": ["uuid1", "uuid2"],
      "exclude_admins": true,
      "dry_run": false
    }
    ```
    """
    service = UserService(db)
    label_policy_service = LabelPolicyService(db)

    # Determine which users to disable
    if request.user_ids:
        # Specific users
        users_to_disable = [service.get_user_by_id(uid) for uid in request.user_ids]
        users_to_disable = [u for u in users_to_disable if u is not None]
    else:
        # All users
        users_to_disable = service.list_users(include_inactive=False)

    # Filter out admins if requested
    if request.exclude_admins:
        users_to_disable = [u for u in users_to_disable if not u.is_admin]

    # Filter out the current admin (can't disable yourself)
    users_to_disable = [
        u
        for u in users_to_disable
        if not (u.email == admin.email or u.oidc_sub == admin.sub)
    ]

    # Check if we're trying to deactivate all admin users
    admin_users_to_disable = [u for u in users_to_disable if u.is_admin]
    if admin_users_to_disable:
        active_admin_count = service.count_active_admins()
        if len(admin_users_to_disable) >= active_admin_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot deactivate all active admin users. "
                    "At least one admin must remain active."
                ),
            )

    if request.dry_run:
        preview = [
            {"user_id": u.id, "email": u.email, "status": "would_be_disabled"}
            for u in users_to_disable
        ]
        return BatchActionResponse(
            success=True,
            action="disable_users",
            affected_count=len(preview),
            failed_count=0,
            comment=request.comment,
            dry_run=True,
            details=preview if preview else None,
        )

    affected = []
    failed = []

    for user in users_to_disable:
        try:
            service.deactivate_user(user.id)
            affected.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "status": "disabled",
                }
            )
        except Exception as e:
            failed.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "status": "failed",
                    "error": str(e),
                }
            )

    # Log security event for audit trail
    label_policy_service.log_security_event(
        event_type="batch_disable_users",
        severity="high",
        user_id=admin.identity,
        runner_id=None,
        runner_name=None,
        violation_data={
            "comment": request.comment,
            "affected_count": len(affected),
            "failed_count": len(failed),
            "user_ids": [u["user_id"] for u in affected],
            "exclude_admins": request.exclude_admins,
        },
        action_taken=f"disabled {len(affected)} users",
    )

    # Also log to audit log for compliance tracking
    audit_entry = AuditLog(
        event_type="batch_disable_users",
        runner_id=None,
        runner_name=None,
        user_id=admin.identity,
        success=len(failed) == 0,
        error_message=f"{len(failed)} failures" if failed else None,
        event_data=json.dumps(
            {
                "comment": request.comment,
                "affected_count": len(affected),
                "failed_count": len(failed),
                "user_ids": [u["user_id"] for u in affected],
                "exclude_admins": request.exclude_admins,
            }
        ),
    )
    db.add(audit_entry)
    db.commit()

    return BatchActionResponse(
        success=len(failed) == 0,
        action="disable_users",
        affected_count=len(affected),
        failed_count=len(failed),
        comment=request.comment,
        details=affected + failed if affected or failed else None,
    )


@router.post("/batch/restore-users", response_model=BatchActionResponse)
async def batch_restore_users(
    request: BatchRestoreUsersRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Restore (reactivate) multiple users in a single operation.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Quickly restore access for multiple users after a security incident has been
    resolved or for organizational changes.

    **Request Body:**
    - **comment**: Required audit trail comment (10-500 chars)
    - **user_ids**: Optional list of user IDs. If null/empty, restores all inactive users.
    - **dry_run**: If true, preview affected users without making any changes.

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Security incident resolved: restoring access for all affected users",
      "user_ids": null,
      "dry_run": false
    }
    ```
    """
    service = UserService(db)
    label_policy_service = LabelPolicyService(db)

    # Determine which users to restore
    if request.user_ids:
        # Specific users
        users_to_restore = [service.get_user_by_id(uid) for uid in request.user_ids]
        users_to_restore = [
            u for u in users_to_restore if u is not None and not u.is_active
        ]
    else:
        # All inactive users
        users_to_restore = service.list_users(include_inactive=True)
        users_to_restore = [u for u in users_to_restore if not u.is_active]

    if request.dry_run:
        preview = [
            {"user_id": u.id, "email": u.email, "status": "would_be_restored"}
            for u in users_to_restore
        ]
        return BatchActionResponse(
            success=True,
            action="restore_users",
            affected_count=len(preview),
            failed_count=0,
            comment=request.comment,
            dry_run=True,
            details=preview if preview else None,
        )

    affected = []
    failed = []

    for user in users_to_restore:
        try:
            service.activate_user(user.id)
            affected.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "status": "restored",
                }
            )
        except Exception as e:
            failed.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "status": "failed",
                    "error": str(e),
                }
            )

    # Log security event for audit trail
    label_policy_service.log_security_event(
        event_type="batch_restore_users",
        severity="medium",
        user_id=admin.identity,
        runner_id=None,
        runner_name=None,
        violation_data={
            "comment": request.comment,
            "affected_count": len(affected),
            "failed_count": len(failed),
            "user_ids": [u["user_id"] for u in affected],
        },
        action_taken=f"restored {len(affected)} users",
    )

    return BatchActionResponse(
        success=len(failed) == 0,
        action="restore_users",
        affected_count=len(affected),
        failed_count=len(failed),
        comment=request.comment,
        details=affected + failed if affected or failed else None,
    )


@router.post("/batch/delete-runners", response_model=BatchActionResponse)
async def batch_delete_runners(
    request: BatchDeleteRunnersRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Delete multiple runners in a single operation.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Quickly remove runners, e.g., during security incidents, cleanup operations,
    or when deprovisioning a user's resources.

    **Request Body:**
    - **comment**: Required audit trail comment (10-500 chars)
    - **runner_ids**: List of specific runner IDs to delete
    - **user_identity**: Delete all runners for this user identity

    At least one of `runner_ids` or `user_identity` must be provided.

    **Priority:**
    1. If runner_ids provided, delete only those runners
    2. Else delete all runners for the given user_identity

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Cleanup: removing all runners for terminated employee alice@example.com",
      "user_identity": "alice@example.com"
    }
    ```
    """
    from app.github.client import GitHubClient

    label_policy_service = LabelPolicyService(db)
    github = GitHubClient(settings)

    # Determine which runners to delete
    query = db.query(Runner).filter(Runner.status != "deleted")

    if request.runner_ids:
        # Specific runners
        query = query.filter(Runner.id.in_(request.runner_ids))
    else:
        # All runners for the specified user — resolve identity to user_id
        target_user = (
            db.query(User)
            .filter(
                (User.id == request.user_identity)
                | (User.email == request.user_identity)
                | (User.oidc_sub == request.user_identity)
            )
            .first()
        )
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {request.user_identity}",
            )
        query = query.filter(Runner.provisioned_by == target_user.id)

    runners_to_delete = query.all()

    affected = []
    failed = []

    for runner in runners_to_delete:
        try:
            # Delete from GitHub if it has a GitHub ID
            if runner.github_runner_id:
                try:
                    await github.delete_runner(runner.github_runner_id)
                except Exception:
                    # Continue even if GitHub deletion fails
                    pass

            # Update local state
            runner.status = "deleted"
            runner.deleted_at = runner.deleted_at or datetime.utcnow()
            db.commit()

            affected.append(
                {
                    "runner_id": runner.id,
                    "runner_name": runner.runner_name,
                    "provisioned_by": runner.provisioned_by,
                    "status": "deleted",
                }
            )
        except Exception as e:
            failed.append(
                {
                    "runner_id": runner.id,
                    "runner_name": runner.runner_name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    # Log security event for audit trail
    label_policy_service.log_security_event(
        event_type="batch_delete_runners",
        severity="high",
        user_id=admin.identity,
        runner_id=None,
        runner_name=None,
        violation_data={
            "comment": request.comment,
            "affected_count": len(affected),
            "failed_count": len(failed),
            "runner_ids": [r["runner_id"] for r in affected],
            "target_user": request.user_identity,
            "scope": "specific"
            if request.runner_ids
            else ("user" if request.user_identity else "all"),
        },
        action_taken=f"deleted {len(affected)} runners",
    )

    # Also log to audit log for compliance tracking
    audit_entry = AuditLog(
        event_type="batch_delete_runners",
        runner_id=None,
        runner_name=None,
        user_id=admin.identity,
        success=len(failed) == 0,
        error_message=f"{len(failed)} failures" if failed else None,
        event_data=json.dumps(
            {
                "comment": request.comment,
                "affected_count": len(affected),
                "failed_count": len(failed),
                "runner_ids": [r["runner_id"] for r in affected],
                "runner_names": [r["runner_name"] for r in affected],
                "target_user": request.user_identity,
                "scope": "specific"
                if request.runner_ids
                else ("user" if request.user_identity else "all"),
            }
        ),
    )
    db.add(audit_entry)
    db.commit()

    return BatchActionResponse(
        success=len(failed) == 0,
        action="delete_runners",
        affected_count=len(affected),
        failed_count=len(failed),
        comment=request.comment,
        details=affected + failed if affected or failed else None,
    )


@router.post("/batch/deactivate-teams", response_model=BatchActionResponse)
async def batch_deactivate_teams(
    request: BatchDeactivateTeamsRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Deactivate multiple teams in a single operation.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Quickly block runner provisioning for multiple teams, e.g., during
    security incidents or organisational restructuring.

    **Request Body:**
    - **comment**: Required audit trail comment (10-500 chars)
    - **team_ids**: Optional list of team IDs. If null/empty, deactivates
      all currently active teams.
    - **reason**: Required reason stored on each team record.
    - **dry_run**: If true, preview affected teams without making any changes.

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Security incident: suspending contractor teams",
      "team_ids": ["uuid1", "uuid2"],
      "reason": "Security audit Q1-2026",
      "dry_run": false
    }
    ```
    """
    service = TeamService(db)
    label_policy_service = LabelPolicyService(db)

    if request.team_ids:
        teams_to_deactivate = [service.get_team(tid) for tid in request.team_ids]
        teams_to_deactivate = [
            t for t in teams_to_deactivate if t is not None and t.is_active
        ]
    else:
        teams_to_deactivate = service.list_teams(include_inactive=False)

    if request.dry_run:
        preview = [
            {"team_id": t.id, "team_name": t.name, "status": "would_be_deactivated"}
            for t in teams_to_deactivate
        ]
        return BatchActionResponse(
            success=True,
            action="deactivate_teams",
            affected_count=len(preview),
            failed_count=0,
            comment=request.comment,
            dry_run=True,
            details=preview if preview else None,
        )

    affected = []
    failed = []

    for team in teams_to_deactivate:
        try:
            service.deactivate_team(
                team_id=team.id,
                reason=request.reason,
                deactivated_by=admin.identity,
            )
            affected.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "status": "deactivated",
                }
            )
        except Exception as e:  # noqa: BLE001
            failed.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    label_policy_service.log_security_event(
        event_type="batch_deactivate_teams",
        severity="high",
        user_id=admin.identity,
        runner_id=None,
        runner_name=None,
        violation_data={
            "comment": request.comment,
            "reason": request.reason,
            "affected_count": len(affected),
            "failed_count": len(failed),
            "team_ids": [t["team_id"] for t in affected],
        },
        action_taken=f"deactivated {len(affected)} teams",
    )

    audit_entry = AuditLog(
        event_type="batch_deactivate_teams",
        runner_id=None,
        runner_name=None,
        user_id=admin.identity,
        success=len(failed) == 0,
        error_message=f"{len(failed)} failures" if failed else None,
        event_data=json.dumps(
            {
                "comment": request.comment,
                "reason": request.reason,
                "affected_count": len(affected),
                "failed_count": len(failed),
                "team_ids": [t["team_id"] for t in affected],
                "team_names": [t["team_name"] for t in affected],
            }
        ),
    )
    db.add(audit_entry)
    db.commit()

    return BatchActionResponse(
        success=len(failed) == 0,
        action="deactivate_teams",
        affected_count=len(affected),
        failed_count=len(failed),
        comment=request.comment,
        details=affected + failed if affected or failed else None,
    )


@router.post("/batch/reactivate-teams", response_model=BatchActionResponse)
async def batch_reactivate_teams(
    request: BatchReactivateTeamsRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Reactivate multiple teams in a single operation.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Restore runner provisioning for multiple teams after a security incident
    is resolved or following organisational changes.

    **Request Body:**
    - **comment**: Required audit trail comment (10-500 chars)
    - **team_ids**: Optional list of team IDs. If null/empty, reactivates
      all currently inactive teams.

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Security incident resolved: restoring all team access",
      "team_ids": null
    }
    ```
    """
    service = TeamService(db)
    label_policy_service = LabelPolicyService(db)

    if request.team_ids:
        teams_to_reactivate = [service.get_team(tid) for tid in request.team_ids]
        teams_to_reactivate = [
            t for t in teams_to_reactivate if t is not None and not t.is_active
        ]
    else:
        all_teams = service.list_teams(include_inactive=True)
        teams_to_reactivate = [t for t in all_teams if not t.is_active]

    affected = []
    failed = []

    for team in teams_to_reactivate:
        try:
            service.reactivate_team(team_id=team.id)
            affected.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "status": "reactivated",
                }
            )
        except Exception as e:  # noqa: BLE001
            failed.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    label_policy_service.log_security_event(
        event_type="batch_reactivate_teams",
        severity="medium",
        user_id=admin.identity,
        runner_id=None,
        runner_name=None,
        violation_data={
            "comment": request.comment,
            "affected_count": len(affected),
            "failed_count": len(failed),
            "team_ids": [t["team_id"] for t in affected],
        },
        action_taken=f"reactivated {len(affected)} teams",
    )

    return BatchActionResponse(
        success=len(failed) == 0,
        action="reactivate_teams",
        affected_count=len(affected),
        failed_count=len(failed),
        comment=request.comment,
        details=affected + failed if affected or failed else None,
    )


@router.get("/stats")
async def get_admin_stats(
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Get comprehensive system statistics for the admin console.

    **Required Authentication:** Admin privileges
    """
    from app.models import Runner, User, SecurityEvent, AuditLog, Team

    return {
        "runners": {
            "total": db.query(Runner).filter(Runner.status != "deleted").count(),
            "active": db.query(Runner).filter(Runner.status == "active").count(),
            "offline": db.query(Runner).filter(Runner.status == "offline").count(),
            "pending": db.query(Runner).filter(Runner.status == "pending").count(),
        },
        "users": {
            "total": db.query(User).count(),
            "active": db.query(User).filter(User.is_active).count(),
            "admins": db.query(User).filter(User.is_admin).count(),
        },
        "teams": {
            "total": db.query(Team).count(),
            "active": db.query(Team).filter(Team.is_active).count(),
        },
        "security": {
            "total_events": db.query(SecurityEvent).count(),
            "critical_events": db.query(SecurityEvent)
            .filter(SecurityEvent.severity == "critical")
            .count(),
            "high_events": db.query(SecurityEvent)
            .filter(SecurityEvent.severity == "high")
            .count(),
        },
        "audit": {
            "total_logs": db.query(AuditLog).count(),
            "failed_operations": db.query(AuditLog)
            .filter(not AuditLog.success)
            .count(),
        },
    }
