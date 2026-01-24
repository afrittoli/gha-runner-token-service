"""Admin API endpoints for label policy and user management."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models import AuditLog, LabelPolicy, SecurityEvent
from app.schemas import (
    BatchActionResponse,
    BatchDeleteRunnersRequest,
    BatchDisableUsersRequest,
    BatchRestoreUsersRequest,
    LabelPolicyCreate,
    LabelPolicyListResponse,
    LabelPolicyResponse,
    SecurityEventListResponse,
    SecurityEventResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services.label_policy_service import LabelPolicyService
from app.services.sync_service import SyncService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    Require admin privileges.

    Checks admin status in the following order:
    1. If user has is_admin=True in the User table, grant access
    2. If no users exist in database (bootstrap mode), check ADMIN_IDENTITIES env var
    3. Otherwise, deny access

    Args:
        user: Authenticated user
        settings: Application settings

    Returns:
        Authenticated user if admin

    Raises:
        HTTPException: If user is not admin
    """
    # Check database-backed admin status
    if user.is_admin:
        return user

    # Bootstrap mode: if no db_user (no users in database), fall back to env var
    if user.db_user is None:
        admin_list = [
            identity.strip()
            for identity in settings.admin_identities.split(",")
            if identity.strip()
        ]

        # If no admin list configured, allow all authenticated users (dev mode)
        if not admin_list:
            return user

        # Check if user identity or sub is in admin list
        if user.identity in admin_list or (user.sub and user.sub in admin_list):
            return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin privileges required",
    )


@router.post(
    "/label-policies",
    response_model=LabelPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_label_policy(
    policy: LabelPolicyCreate,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Create or update a label policy for a user.

    **Required Authentication:** Admin privileges

    **Purpose:**
    Define which labels a user is permitted to use when provisioning runners.
    Policies enforce security boundaries and prevent unauthorized label usage.

    **Policy Components:**
    - **allowed_labels**: Explicit list of permitted labels
    - **label_patterns**: Regex patterns for dynamic label matching
    - **max_runners**: Maximum concurrent runners
    - **require_approval**: Whether provisioning requires manual approval

    **Returns:**
    Created or updated label policy

    **Example:**
    ```json
    {
      "user_identity": "alice@example.com",
      "allowed_labels": ["team-a", "linux", "docker"],
      "label_patterns": ["team-a-.*"],
      "max_runners": 10,
      "description": "Team A development runners"
    }
    ```
    """
    service = LabelPolicyService(db)

    try:
        db_policy = service.create_policy(
            user_identity=policy.user_identity,
            allowed_labels=policy.allowed_labels,
            label_patterns=policy.label_patterns,
            max_runners=policy.max_runners,
            require_approval=policy.require_approval,
            description=policy.description,
            created_by=admin.identity,
        )

        return LabelPolicyResponse(
            user_identity=db_policy.user_identity,
            allowed_labels=json.loads(db_policy.allowed_labels),
            label_patterns=json.loads(db_policy.label_patterns)
            if db_policy.label_patterns
            else None,
            max_runners=db_policy.max_runners,
            require_approval=db_policy.require_approval,
            description=db_policy.description,
            created_by=db_policy.created_by,
            created_at=db_policy.created_at,
            updated_at=db_policy.updated_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create policy: {str(e)}",
        )


@router.get("/label-policies", response_model=LabelPolicyListResponse)
async def list_label_policies(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all label policies.

    **Required Authentication:** Admin privileges

    **Query Parameters:**
    - **limit**: Maximum number of policies to return (1-1000)
    - **offset**: Offset for pagination

    **Returns:**
    Paginated list of label policies
    """
    service = LabelPolicyService(db)
    policies = service.list_policies(limit=limit, offset=offset)

    policy_responses = []
    for policy in policies:
        policy_responses.append(
            LabelPolicyResponse(
                user_identity=policy.user_identity,
                allowed_labels=json.loads(policy.allowed_labels),
                label_patterns=json.loads(policy.label_patterns)
                if policy.label_patterns
                else None,
                max_runners=policy.max_runners,
                require_approval=policy.require_approval,
                description=policy.description,
                created_by=policy.created_by,
                created_at=policy.created_at,
                updated_at=policy.updated_at,
            )
        )

    total = db.query(LabelPolicy).count()

    return LabelPolicyListResponse(policies=policy_responses, total=total)


@router.get("/label-policies/{user_identity}", response_model=LabelPolicyResponse)
async def get_label_policy(
    user_identity: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get label policy for a specific user.

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_identity**: User identity (email or OIDC subject)

    **Returns:**
    Label policy if exists

    **Raises:**
    - 404: Policy not found
    """
    service = LabelPolicyService(db)
    policy = service.get_policy(user_identity)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No policy found for user: {user_identity}",
        )

    return LabelPolicyResponse(
        user_identity=policy.user_identity,
        allowed_labels=json.loads(policy.allowed_labels),
        label_patterns=json.loads(policy.label_patterns)
        if policy.label_patterns
        else None,
        max_runners=policy.max_runners,
        require_approval=policy.require_approval,
        description=policy.description,
        created_by=policy.created_by,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.delete(
    "/label-policies/{user_identity}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_label_policy(
    user_identity: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete label policy for a user.

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_identity**: User identity

    **Returns:**
    204 No Content on success

    **Raises:**
    - 404: Policy not found
    """
    service = LabelPolicyService(db)
    deleted = service.delete_policy(user_identity)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No policy found for user: {user_identity}",
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
    query = db.query(SecurityEvent)

    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    if user_identity:
        query = query.filter(SecurityEvent.user_identity == user_identity)

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
                user_identity=event.user_identity,
                violation_data=json.loads(event.violation_data),
                action_taken=event.action_taken,
                timestamp=event.timestamp,
            )
        )

    # Get total count with same filters
    total_query = db.query(SecurityEvent)
    if event_type:
        total_query = total_query.filter(SecurityEvent.event_type == event_type)
    if severity:
        total_query = total_query.filter(SecurityEvent.severity == severity)
    if user_identity:
        total_query = total_query.filter(SecurityEvent.user_identity == user_identity)

    total = total_query.count()

    return SecurityEventListResponse(events=event_responses, total=total)


@router.get("/sync/status")
async def get_sync_status(
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
):
    """
    Get sync service status.

    **Required Authentication:** Admin privileges

    **Returns:**
    Current sync configuration and last sync result
    """
    from app.main import get_sync_status

    return get_sync_status()


@router.post("/sync/trigger")
async def trigger_sync(
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Manually trigger a sync with GitHub.

    **Required Authentication:** Admin privileges

    **Returns:**
    Sync result with counts of updated, deleted, unchanged runners
    """
    sync_service = SyncService(settings, db)

    try:
        result = await sync_service.sync_all_runners()
        return {
            "status": "completed",
            "result": result.to_dict(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


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
      "can_use_registration_token": true,
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
            can_use_registration_token=user_data.can_use_registration_token,
            can_use_jit=user_data.can_use_jit,
            created_by=admin.identity,
        )

        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            oidc_sub=db_user.oidc_sub,
            display_name=db_user.display_name,
            is_admin=db_user.is_admin,
            is_active=db_user.is_active,
            can_use_registration_token=db_user.can_use_registration_token,
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
            can_use_registration_token=user.can_use_registration_token,
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
        can_use_registration_token=user.can_use_registration_token,
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
        can_use_registration_token=user.can_use_registration_token,
        can_use_jit=user.can_use_jit,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        created_by=user.created_by,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Deactivate a user (soft delete).

    **Required Authentication:** Admin privileges

    **Parameters:**
    - **user_id**: User UUID

    **Returns:**
    204 No Content on success

    **Raises:**
    - 404: User not found

    **Note:**
    This performs a soft delete by setting `is_active=False`.
    The user can be reactivated using the `/users/{user_id}/activate` endpoint.
    """
    service = UserService(db)
    deactivated = service.deactivate_user(user_id)

    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )


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
        can_use_registration_token=user.can_use_registration_token,
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

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Security incident: disabling all contractor accounts pending review",
      "user_ids": ["uuid1", "uuid2"],
      "exclude_admins": true
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
        user_identity=admin.identity,
        oidc_sub=admin.sub,
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
        user_identity=admin.identity,
        oidc_sub=admin.sub,
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

    **Returns:**
    Batch operation result with affected count and details

    **Example:**
    ```json
    {
      "comment": "Security incident resolved: restoring access for all affected users",
      "user_ids": null
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
        user_identity=admin.identity,
        oidc_sub=admin.sub,
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
    - **runner_ids**: Optional list of specific runner IDs to delete
    - **user_identity**: Optional user identity to delete all runners for

    **Priority:**
    1. If runner_ids provided, delete only those runners
    2. Else if user_identity provided, delete all runners for that user
    3. Else delete ALL non-deleted runners (dangerous!)

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
    from app.models import Runner
    from app.github.client import GitHubClient

    label_policy_service = LabelPolicyService(db)
    github = GitHubClient(settings)

    # Determine which runners to delete
    query = db.query(Runner).filter(Runner.status != "deleted")

    if request.runner_ids:
        # Specific runners
        query = query.filter(Runner.id.in_(request.runner_ids))
    elif request.user_identity:
        # All runners for a specific user
        query = query.filter(Runner.provisioned_by == request.user_identity)
    # else: all non-deleted runners

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
        user_identity=admin.identity,
        oidc_sub=admin.sub,
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
        user_identity=admin.identity,
        oidc_sub=admin.sub,
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


@router.get("/stats")
async def get_admin_stats(
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    """
    Get comprehensive system statistics for the admin console.

    **Required Authentication:** Admin privileges
    """
    from app.models import Runner, User, SecurityEvent, AuditLog, LabelPolicy

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
        "policies": {
            "total": db.query(LabelPolicy).count(),
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


@router.get("/config")
async def get_admin_config(
    admin: AuthenticatedUser = Depends(require_admin),  # noqa: ARG001
    settings: Settings = Depends(get_settings),
):
    """
    Get system configuration (sanitized).

    **Required Authentication:** Admin privileges
    """
    # Define sensitive fields to mask
    sensitive_fields = {
        "github_token",
        "app_key",
        "oidc_client_secret",
        "database_url",
        "admin_identities",
    }

    config = {}
    for field in settings.model_fields:
        value = getattr(settings, field)
        if field in sensitive_fields and value:
            config[field] = "********"
        else:
            config[field] = value

    return config
