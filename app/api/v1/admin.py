"""Admin API endpoints for label policy management."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models import LabelPolicy, SecurityEvent
from app.schemas import (
    LabelPolicyCreate,
    LabelPolicyListResponse,
    LabelPolicyResponse,
    SecurityEventListResponse,
    SecurityEventResponse,
)
from app.services.label_policy_service import LabelPolicyService

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    Require admin privileges.

    Checks if the user's identity is in the ADMIN_IDENTITIES environment variable.
    If ADMIN_IDENTITIES is empty, all authenticated users have admin access (dev mode).

    Args:
        user: Authenticated user
        settings: Application settings

    Returns:
        Authenticated user if admin

    Raises:
        HTTPException: If user is not admin
    """
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
