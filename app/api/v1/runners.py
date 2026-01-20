"""Runner management API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas import (
    DeprovisionResponse,
    ProvisionRunnerRequest,
    ProvisionRunnerResponse,
    RunnerListResponse,
    RunnerStatus,
)
from app.services.runner_service import RunnerService

router = APIRouter(prefix="/runners", tags=["Runners"])


@router.post(
    "/provision",
    response_model=ProvisionRunnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_runner(
    request: ProvisionRunnerRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Provision a new self-hosted runner.

    This endpoint generates a time-limited GitHub registration token that the third party
    can use to configure and register a self-hosted runner.

    **Required Authentication:** OIDC Bearer token

    **Workflow:**
    1. Third party authenticates with OIDC token
    2. Service generates GitHub registration token (expires in 1 hour)
    3. Third party uses token to configure runner with `./config.sh`
    4. Runner appears in GitHub and starts accepting jobs

    **Returns:**
    - Registration token (valid for 1 hour)
    - Configuration command for the runner
    - Runner metadata
    """
    service = RunnerService(settings, db)

    try:
        response = await service.provision_runner(request, user)
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision runner: {str(e)}",
        )


@router.get("", response_model=RunnerListResponse)
async def list_runners(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by runner status: active, offline, pending",
    ),
    ephemeral: Optional[bool] = Query(
        None,
        description="Filter by ephemeral flag (true/false)",
    ),
    limit: int = Query(50, ge=1, le=200, description="Limit results (1-200)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List all runners provisioned by the authenticated user.

    **Required Authentication:** OIDC Bearer token

    **Query Parameters:**
    - `status`: Filter by runner status (active, offline, pending)
    - `ephemeral`: Filter by ephemeral flag
    - `limit`: Results per page (1-200, default 50)
    - `offset`: Pagination offset (default 0)

    **Returns:**
    - List of runners with their current status
    - Total count
    """
    service = RunnerService(settings, db)

    all_runners = await service.list_runners(user)

    # Apply filters
    filtered_runners = all_runners
    if status_filter:
        filtered_runners = [r for r in filtered_runners if r.status == status_filter]
    if ephemeral is not None:
        filtered_runners = [r for r in filtered_runners if r.ephemeral == ephemeral]

    # Apply pagination
    total = len(filtered_runners)
    paginated_runners = filtered_runners[offset : offset + limit]

    # Convert to response schema
    runner_statuses = []
    for runner in paginated_runners:
        runner_statuses.append(
            RunnerStatus(
                runner_id=runner.id,
                runner_name=runner.runner_name,
                status=runner.status,
                github_runner_id=runner.github_runner_id,
                runner_group_id=runner.runner_group_id,
                labels=json.loads(runner.labels),
                ephemeral=runner.ephemeral,
                provisioned_by=runner.provisioned_by,
                created_at=runner.created_at,
                updated_at=runner.updated_at,
                registered_at=runner.registered_at,
                deleted_at=runner.deleted_at,
            )
        )

    return RunnerListResponse(runners=runner_statuses, total=total)


@router.get("/{runner_id}", response_model=RunnerStatus)
async def get_runner(
    runner_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Get status of a specific runner by ID.

    **Required Authentication:** OIDC Bearer token

    **Access Control:** Only the user who provisioned the runner can view it.

    **Returns:**
    - Runner status and metadata
    """
    service = RunnerService(settings, db)

    runner = await service.get_runner_by_id(runner_id, user)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runner with ID '{runner_id}' not found or not owned by you",
        )

    return RunnerStatus(
        runner_id=runner.id,
        runner_name=runner.runner_name,
        status=runner.status,
        github_runner_id=runner.github_runner_id,
        runner_group_id=runner.runner_group_id,
        labels=json.loads(runner.labels),
        ephemeral=runner.ephemeral,
        provisioned_by=runner.provisioned_by,
        created_at=runner.created_at,
        updated_at=runner.updated_at,
        registered_at=runner.registered_at,
        deleted_at=runner.deleted_at,
    )


@router.post("/{runner_id}/refresh", response_model=RunnerStatus)
async def refresh_runner_status(
    runner_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Refresh runner status from GitHub API.

    **Required Authentication:** OIDC Bearer token

    **Purpose:**
    - Sync local state with GitHub
    - Check if runner has been registered
    - Detect ephemeral runner deletion

    **Returns:**
    - Updated runner status
    """
    service = RunnerService(settings, db)

    runner = await service.update_runner_status(runner_id, user)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runner with ID '{runner_id}' not found or not owned by you",
        )

    return RunnerStatus(
        runner_id=runner.id,
        runner_name=runner.runner_name,
        status=runner.status,
        github_runner_id=runner.github_runner_id,
        runner_group_id=runner.runner_group_id,
        labels=json.loads(runner.labels),
        ephemeral=runner.ephemeral,
        provisioned_by=runner.provisioned_by,
        created_at=runner.created_at,
        updated_at=runner.updated_at,
        registered_at=runner.registered_at,
        deleted_at=runner.deleted_at,
    )


@router.delete("/{runner_id}", response_model=DeprovisionResponse)
async def deprovision_runner(
    runner_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Deprovision a runner by ID.

    **Required Authentication:** OIDC Bearer token

    **Access Control:** Only the user who provisioned the runner can delete it.

    **Actions:**
    1. Delete runner from GitHub
    2. Update local state to 'deleted'
    3. Log audit event

    **Note:** For ephemeral runners, this is usually not needed as they auto-delete
    after completing one job.

    **Returns:**
    - Deprovisioning confirmation
    """
    service = RunnerService(settings, db)

    runner = await service.get_runner_by_id(runner_id, user)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runner with ID '{runner_id}' not found or not owned by you",
        )

    try:
        await service.deprovision_runner(runner_id, user)

        return DeprovisionResponse(
            runner_id=runner.id,
            runner_name=runner.runner_name,
            success=True,
            message=f"Runner '{runner.runner_name}' successfully deprovisioned",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deprovision runner: {str(e)}",
        )
