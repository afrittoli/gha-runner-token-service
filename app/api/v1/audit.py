"""Audit log API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_db
from app.models import AuditLog
from app.schemas import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    event_type: Optional[str] = Query(default=None),
    user_identity: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List audit logs.

    **Required Authentication:** OIDC Bearer token

    **Access Control:**
    - Admins can see all logs and filter by user
    - Standard users can only see their own logs

    **Query Parameters:**
    - **event_type**: Filter by event type
    - **user_identity**: Filter by user identity (Admin only)
    - **limit**: Maximum number of logs to return (1-200)
    - **offset**: Offset for pagination
    """
    query = db.query(AuditLog)

    # Apply RBAC
    if not user.is_admin:
        # Standard users only see their own logs
        query = query.filter(AuditLog.user_identity == user.identity)
    elif user_identity:
        # Admins can filter by user
        query = query.filter(AuditLog.user_identity == user_identity)

    # Apply filters
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
            )
        )

    return AuditLogListResponse(logs=log_responses, total=total)
