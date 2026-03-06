"""Admin API for managing OAuth M2M clients (team credentials)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_db
from app.models import OAuthClient, Team
from app.schemas import (
    OAuthClientCreate,
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
    response_model=OAuthClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an OAuth M2M client for a team",
)
async def create_oauth_client(
    data: OAuthClientCreate,
    admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Register an Auth0 M2M client_id as authorized for a team.

    The ``client_id`` must match the ``sub`` claim that Auth0 puts in
    ``client_credentials`` tokens for that application.
    """
    # Verify team exists
    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{data.team_id}' not found.",
        )

    # Check for duplicate client_id
    existing = (
        db.query(OAuthClient).filter(OAuthClient.client_id == data.client_id).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"OAuth client '{data.client_id}' already registered.",
        )

    client = OAuthClient(
        client_id=data.client_id,
        team_id=data.team_id,
        description=data.description,
        created_by=admin.identity,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get(
    "",
    response_model=OAuthClientListResponse,
    summary="List registered OAuth M2M clients",
)
async def list_oauth_clients(
    team_id: str = Query(None, description="Filter by team ID"),
    active_only: bool = Query(True, description="Only return active clients"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """List OAuth M2M clients, optionally filtered by team."""
    query = db.query(OAuthClient)
    if team_id:
        query = query.filter(OAuthClient.team_id == team_id)
    if active_only:
        query = query.filter(OAuthClient.is_active.is_(True))
    total = query.count()
    clients = query.offset(skip).limit(limit).all()
    return OAuthClientListResponse(clients=clients, total=total)


@router.get(
    "/{client_id}",
    response_model=OAuthClientResponse,
    summary="Get an OAuth M2M client by ID",
)
async def get_oauth_client(
    client_id: str,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve a single OAuth client record by its internal UUID."""
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
    summary="Update an OAuth M2M client",
)
async def update_oauth_client(
    client_id: str,
    data: OAuthClientUpdate,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Update description or active status of an OAuth M2M client."""
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
    summary="Delete an OAuth M2M client",
)
async def delete_oauth_client(
    client_id: str,
    _admin: AuthenticatedUser = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Permanently remove an OAuth M2M client registration."""
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

    Called from the auth middleware after a successful M2M token validation.
    Best-effort — failures are silently ignored to avoid blocking requests.

    Args:
        db: Database session
        client_sub: The ``sub`` claim from the M2M JWT (== Auth0 client_id)
    """
    try:
        client = (
            db.query(OAuthClient).filter(OAuthClient.client_id == client_sub).first()
        )
        if client:
            client.last_used_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:  # noqa: BLE001
        pass
