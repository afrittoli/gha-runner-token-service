"""User management service."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import User


class UserService:
    """Service for user CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_user(
        self,
        email: Optional[str] = None,
        oidc_sub: Optional[str] = None,
        display_name: Optional[str] = None,
        is_admin: bool = False,
        can_use_registration_token: bool = True,
        can_use_jit: bool = True,
        created_by: Optional[str] = None,
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email (primary identifier)
            oidc_sub: OIDC subject claim (alternative identifier)
            display_name: Display name for dashboard
            is_admin: Whether user has admin privileges
            can_use_registration_token: Allow access to registration token API
            can_use_jit: Allow access to JIT API
            created_by: Admin who created this user

        Returns:
            Created User object

        Raises:
            ValueError: If neither email nor oidc_sub is provided
        """
        if not email and not oidc_sub:
            raise ValueError("Either email or oidc_sub must be provided")

        user = User(
            email=email,
            oidc_sub=oidc_sub,
            display_name=display_name or email or oidc_sub,
            is_admin=is_admin,
            is_active=True,
            can_use_registration_token=can_use_registration_token,
            can_use_jit=can_use_jit,
            created_by=created_by,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_oidc_sub(self, oidc_sub: str) -> Optional[User]:
        """
        Get user by OIDC subject claim.

        Args:
            oidc_sub: OIDC subject claim

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.oidc_sub == oidc_sub).first()

    def get_user_by_identity(
        self, email: Optional[str] = None, oidc_sub: Optional[str] = None
    ) -> Optional[User]:
        """
        Get user by email or OIDC sub.

        Args:
            email: User email
            oidc_sub: OIDC subject claim

        Returns:
            User if found by either identifier, None otherwise
        """
        conditions = []
        if email:
            conditions.append(User.email == email)
        if oidc_sub:
            conditions.append(User.oidc_sub == oidc_sub)

        if not conditions:
            return None

        return self.db.query(User).filter(or_(*conditions)).first()

    def list_users(
        self, limit: int = 100, offset: int = 0, include_inactive: bool = False
    ) -> List[User]:
        """
        List users with pagination.

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            include_inactive: Include deactivated users

        Returns:
            List of User objects
        """
        query = self.db.query(User)
        if not include_inactive:
            query = query.filter(User.is_active == True)  # noqa: E712
        return query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()

    def count_users(self, include_inactive: bool = False) -> int:
        """
        Count total users.

        Args:
            include_inactive: Include deactivated users

        Returns:
            Total number of users
        """
        query = self.db.query(User)
        if not include_inactive:
            query = query.filter(User.is_active == True)  # noqa: E712
        return query.count()

    def count_active_admins(self) -> int:
        """
        Count active admin users.

        Returns:
            Number of active admin users
        """
        return (
            self.db.query(User)
            .filter(User.is_admin == True, User.is_active == True)  # noqa: E712
            .count()
        )

    def update_user(self, user_id: str, **updates) -> Optional[User]:
        """
        Update user fields.

        Args:
            user_id: User UUID
            **updates: Fields to update (display_name, is_admin, is_active, etc.)

        Returns:
            Updated User if found, None otherwise
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        allowed_fields = {
            "display_name",
            "is_admin",
            "is_active",
            "can_use_registration_token",
            "can_use_jit",
        }

        for key, value in updates.items():
            if key in allowed_fields and value is not None:
                setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def deactivate_user(self, user_id: str) -> bool:
        """
        Soft-delete user by setting is_active=False.

        Args:
            user_id: User UUID

        Returns:
            True if user was deactivated, False if not found
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        self.db.commit()
        return True

    def activate_user(self, user_id: str) -> bool:
        """
        Reactivate a deactivated user.

        Args:
            user_id: User UUID

        Returns:
            True if user was activated, False if not found
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = True
        self.db.commit()
        return True

    def update_last_login(self, user_id: str) -> None:
        """
        Update user's last login timestamp.

        Args:
            user_id: User UUID
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            self.db.commit()
