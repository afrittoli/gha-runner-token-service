"""Bootstrap admin account creation for initial deployment."""

import json
import structlog
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.models import User, Team, UserTeamMembership
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def bootstrap_admins_team(db: Session) -> Team:
    """
    Create or get the "admins" team.

    Args:
        db: Database session

    Returns:
        The admins team (existing or newly created)
    """
    # Check if admins team already exists
    admins_team = db.query(Team).filter(Team.name == "admins").first()

    if admins_team:
        logger.info("admins_team_exists", team_id=admins_team.id)
        return admins_team

    # Create admins team with permissive policy
    admins_team = Team(
        name="admins",
        description="System administrators team",
        required_labels=json.dumps([]),  # No required labels
        optional_label_patterns=json.dumps([".*"]),  # Allow all labels
        max_runners=None,  # No quota limit
        is_active=True,
        created_by="system",
    )

    db.add(admins_team)
    db.commit()
    db.refresh(admins_team)

    logger.info("admins_team_created", team_id=admins_team.id)
    return admins_team


def bootstrap_admin_user(db: Session) -> bool:
    """
    Create bootstrap admin user and add to admins team if doesn't exist.

    This function is idempotent and safe to run multiple times.
    It will only create the admin user on first run.

    Args:
        db: Database session

    Returns:
        True if admin was created, False if already exists

    Raises:
        ValueError: If required environment variables are missing
        Exception: If database operation fails
    """
    try:
        # Get bootstrap configuration from environment
        username = settings.bootstrap_admin_username
        password = settings.bootstrap_admin_password
        email = settings.bootstrap_admin_email

        # Validate required fields
        if not username:
            logger.warning(
                "bootstrap_admin_skipped",
                reason="username_not_configured",
            )
            return False

        if not password:
            logger.warning(
                "bootstrap_admin_skipped",
                reason="password_not_configured",
            )
            return False

        # Check if admin user already exists
        existing_admin = db.query(User).filter(User.username == username).first()

        if existing_admin:
            logger.info(
                "bootstrap_admin_exists",
                username=username,
                user_id=existing_admin.id,
            )
            # Ensure admin is in admins team
            admins_team = bootstrap_admins_team(db)
            existing_membership = (
                db.query(UserTeamMembership)
                .filter(
                    UserTeamMembership.user_id == existing_admin.id,
                    UserTeamMembership.team_id == admins_team.id,
                )
                .first()
            )
            if not existing_membership:
                membership = UserTeamMembership(
                    user_id=existing_admin.id,
                    team_id=admins_team.id,
                    role="admin",
                    added_by="system",
                )
                db.add(membership)
                db.commit()
                logger.info(
                    "admin_added_to_team",
                    user_id=existing_admin.id,
                    team_id=admins_team.id,
                )
            return False

        # Create admin user
        hashed_password = hash_password(password)

        admin_user = User(
            username=username,
            email=email or f"{username}@localhost",
            hashed_password=hashed_password,
            is_admin=True,
            is_active=True,
            can_use_registration_token=True,
            can_use_jit=True,
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        logger.info(
            "bootstrap_admin_created",
            username=username,
            user_id=admin_user.id,
            email=admin_user.email,
        )

        # Create admins team and add admin to it
        admins_team = bootstrap_admins_team(db)

        membership = UserTeamMembership(
            user_id=admin_user.id,
            team_id=admins_team.id,
            role="admin",
            added_by="system",
        )
        db.add(membership)
        db.commit()

        logger.info(
            "admin_added_to_team",
            user_id=admin_user.id,
            team_id=admins_team.id,
        )

        return True

    except Exception as e:
        logger.error(
            "bootstrap_admin_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        db.rollback()
        raise


def ensure_bootstrap_admin(db: Session) -> None:
    """
    Ensure bootstrap admin exists (wrapper for startup).

    This is the main entry point called during application startup.
    It handles all errors gracefully and logs appropriately.

    Args:
        db: Database session
    """
    try:
        created = bootstrap_admin_user(db)
        if created:
            logger.info("bootstrap_admin_initialization_complete", status="created")
        else:
            logger.info("bootstrap_admin_initialization_complete", status="exists")
    except ValueError as e:
        logger.warning(
            "bootstrap_admin_configuration_error",
            error=str(e),
            message="Bootstrap admin not configured properly",
        )
    except Exception as e:
        logger.error(
            "bootstrap_admin_initialization_failed",
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to create bootstrap admin user",
        )
        # Don't raise - allow application to start even if bootstrap fails


# Made with Bob
