"""Admin API for managing GHARTS-native M2M API-key clients."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.api_keys import generate_api_key
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_db
from app.models import OAuthClient, Team
from app.schemas import (
    OAuthClientCreate,
    OAuthClientCreateResponse,
    OAuthClientListResponse,
    OAuthClientResponse,
    OAuthClientUpdate,
)

router = APIRouter(prefix="/admin/oauth-clients", tags=["OAuth Clients"])


def _require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require admin privileges."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


@router.post(
    "",
    response_model=OAuthClientCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new M2M API-key client for a team",
)
async def create_oauth_client(
    data: OAuthClientCreate,
    admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Register a new M2M client for a team and issue its initial API key.

    The response contains ``api_key`` — the raw bearer token value.  This is
    shown **exactly once** and cannot be retrieved again.  Store it in your
    CI/CD secret store immediately.

    Usage in CI/CD pipelines::

        Authorization: Bearer <api_key>

    The ``client_id`` field is a human-readable label (e.g. ``"ci-pipeline"``)
    unique across all clients.
    """
    # Verify team exists
    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{data.team_id}' not found.",
        )

    # Check for duplicate client_id (globally unique)
    existing = (
        db.query(OAuthClient).filter(OAuthClient.client_id == data.client_id).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"OAuth client '{data.client_id}' already registered.",
        )

    # Enforce one active machine member per team.
    existing_for_team = (
        db.query(OAuthClient)
        .filter(
            OAuthClient.team_id == data.team_id,
            OAuthClient.is_active.is_(True),
        )
        .first()
    )
    if existing_for_team:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Team '{data.team_id}' already has an active M2M client "
                f"(client_id='{existing_for_team.client_id}'). "
                "Disable or delete the existing registration before "
                "adding a new one."
            ),
        )

    raw_key, hashed_key = generate_api_key()

    client = OAuthClient(
        client_id=data.client_id,
        hashed_key=hashed_key,
        team_id=data.team_id,
        description=data.description,
        created_by=admin.identity,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    return OAuthClientCreateResponse(
        client=OAuthClientResponse.model_validate(client),
        api_key=raw_key,
    )


@router.post(
    "/{client_id}/rotate",
    response_model=OAuthClientCreateResponse,
    summary="Rotate the API key for an M2M client",
)
async def rotate_oauth_client_key(
    client_id: str,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Generate and store a new API key for the given client, invalidating the old one.

    The response contains ``api_key`` — the new raw bearer token value.  This is
    shown **exactly once**.  The previous key stops working immediately.

    Args:
        client_id: Internal UUID of the OAuthClient record.
    """
    client = db.query(OAuthClient).filter(OAuthClient.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth client not found.",
        )

    raw_key, hashed_key = generate_api_key()
    client.hashed_key = hashed_key
    db.commit()
    db.refresh(client)

    return OAuthClientCreateResponse(
        client=OAuthClientResponse.model_validate(client),
        api_key=raw_key,
    )


@router.get(
    "",
    response_model=OAuthClientListResponse,
    summary="List registered M2M clients",
)
async def list_oauth_clients(
    team_id: str = Query(None, description="Filter by team ID"),
    active_only: bool = Query(True, description="Only return active clients"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """List M2M clients, optionally filtered by team."""
    query = db.query(OAuthClient)
    if team_id:
        query = query.filter(OAuthClient.team_id == team_id)
    if active_only:
        query = query.filter(OAuthClient.is_active.is_(True))
    total = query.count()
    clients = query.offset(skip).limit(limit).all()
    client_responses = [
        OAuthClientResponse.model_validate(client) for client in clients
    ]
    return OAuthClientListResponse(clients=client_responses, total=total)


@router.get(
    "/{client_id}",
    response_model=OAuthClientResponse,
    summary="Get an M2M client by ID",
)
async def get_oauth_client(
    client_id: str,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve a single M2M client record by its internal UUID."""
    client = db.query(OAuthClient).filter(OAuthClient.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth client not found.",
        )
    return client


@router.patch(
    "/{client_id}",
    response_model=OAuthClientResponse,
    summary="Update an M2M client",
)
async def update_oauth_client(
    client_id: str,
    data: OAuthClientUpdate,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Update description or active status of an M2M client."""
    client = db.query(OAuthClient).filter(OAuthClient.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth client not found.",
        )
    if data.description is not None:
        client.description = data.description
    if data.is_active is not None:
        client.is_active = data.is_active
    db.commit()
    db.refresh(client)
    return client


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an M2M client",
)
async def delete_oauth_client(
    client_id: str,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Permanently remove an M2M client registration."""
    client = db.query(OAuthClient).filter(OAuthClient.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth client not found.",
        )
    db.delete(client)
    db.commit()


def record_m2m_usage(db: Session, client_sub: str) -> None:
    """Update ``last_used_at`` for the OAuth client matching ``client_sub``.

    Kept for backward compatibility; the new API-key auth path stamps
    ``last_used_at`` directly in ``_authenticate_api_key``.

    Args:
        db: Database session
        client_sub: The client identifier (client_id column value)
    """
    client = db.query(OAuthClient).filter(OAuthClient.client_id == client_sub).first()
    if client:
        client.last_used_at = datetime.now(timezone.utc)
        db.commit()
