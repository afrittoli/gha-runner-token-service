"""Tests for user service."""

import pytest
from sqlalchemy.orm import Session

from app.services.user_service import UserService


class TestUserCreation:
    """Tests for user creation."""

    def test_create_user_with_email(self, test_db: Session):
        """Test creating a user with email."""
        service = UserService(test_db)

        user = service.create_user(
            email="test@example.com",
            display_name="Test User",
        )

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.is_active is True
        assert user.is_admin is False
        assert user.can_use_registration_token is True
        assert user.can_use_jit is True

    def test_create_user_with_oidc_sub(self, test_db: Session):
        """Test creating a user with OIDC sub."""
        service = UserService(test_db)

        user = service.create_user(
            oidc_sub="auth0|123456",
            display_name="OIDC User",
        )

        assert user.id is not None
        assert user.oidc_sub == "auth0|123456"
        assert user.email is None
        assert user.display_name == "OIDC User"

    def test_create_user_with_both_identifiers(self, test_db: Session):
        """Test creating a user with both email and OIDC sub."""
        service = UserService(test_db)

        user = service.create_user(
            email="both@example.com",
            oidc_sub="auth0|both123",
            display_name="Both User",
        )

        assert user.email == "both@example.com"
        assert user.oidc_sub == "auth0|both123"

    def test_create_user_requires_identifier(self, test_db: Session):
        """Test that creating a user requires at least one identifier."""
        service = UserService(test_db)

        with pytest.raises(ValueError) as exc_info:
            service.create_user(display_name="No Identifier")

        assert "email or oidc_sub must be provided" in str(exc_info.value)

    def test_create_admin_user(self, test_db: Session):
        """Test creating an admin user."""
        service = UserService(test_db)

        user = service.create_user(
            email="admin@example.com",
            is_admin=True,
        )

        assert user.is_admin is True

    def test_create_user_with_restricted_permissions(self, test_db: Session):
        """Test creating a user with restricted API access."""
        service = UserService(test_db)

        user = service.create_user(
            email="restricted@example.com",
            can_use_registration_token=False,
            can_use_jit=True,
        )

        assert user.can_use_registration_token is False
        assert user.can_use_jit is True

    def test_create_user_with_created_by(self, test_db: Session):
        """Test creating a user with created_by audit field."""
        service = UserService(test_db)

        user = service.create_user(
            email="created@example.com",
            created_by="admin@example.com",
        )

        assert user.created_by == "admin@example.com"

    def test_create_user_default_display_name(self, test_db: Session):
        """Test that display_name defaults to email or oidc_sub."""
        service = UserService(test_db)

        # Email as default
        user1 = service.create_user(email="default@example.com")
        assert user1.display_name == "default@example.com"

        # OIDC sub as default
        user2 = service.create_user(oidc_sub="auth0|default")
        assert user2.display_name == "auth0|default"


class TestUserLookup:
    """Tests for user lookup methods."""

    def test_get_user_by_id(self, test_db: Session):
        """Test getting a user by ID."""
        service = UserService(test_db)

        created = service.create_user(email="byid@example.com")
        found = service.get_user_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.email == "byid@example.com"

    def test_get_user_by_id_not_found(self, test_db: Session):
        """Test getting a non-existent user by ID."""
        service = UserService(test_db)

        found = service.get_user_by_id("nonexistent-uuid")
        assert found is None

    def test_get_user_by_email(self, test_db: Session):
        """Test getting a user by email."""
        service = UserService(test_db)

        service.create_user(email="byemail@example.com")
        found = service.get_user_by_email("byemail@example.com")

        assert found is not None
        assert found.email == "byemail@example.com"

    def test_get_user_by_email_not_found(self, test_db: Session):
        """Test getting a non-existent user by email."""
        service = UserService(test_db)

        found = service.get_user_by_email("nonexistent@example.com")
        assert found is None

    def test_get_user_by_oidc_sub(self, test_db: Session):
        """Test getting a user by OIDC sub."""
        service = UserService(test_db)

        service.create_user(oidc_sub="auth0|bysub123")
        found = service.get_user_by_oidc_sub("auth0|bysub123")

        assert found is not None
        assert found.oidc_sub == "auth0|bysub123"

    def test_get_user_by_oidc_sub_not_found(self, test_db: Session):
        """Test getting a non-existent user by OIDC sub."""
        service = UserService(test_db)

        found = service.get_user_by_oidc_sub("auth0|nonexistent")
        assert found is None

    def test_get_user_by_identity_with_email(self, test_db: Session):
        """Test getting a user by identity (email)."""
        service = UserService(test_db)

        service.create_user(email="identity@example.com")
        found = service.get_user_by_identity(email="identity@example.com")

        assert found is not None
        assert found.email == "identity@example.com"

    def test_get_user_by_identity_with_oidc_sub(self, test_db: Session):
        """Test getting a user by identity (OIDC sub)."""
        service = UserService(test_db)

        service.create_user(oidc_sub="auth0|identity123")
        found = service.get_user_by_identity(oidc_sub="auth0|identity123")

        assert found is not None
        assert found.oidc_sub == "auth0|identity123"

    def test_get_user_by_identity_matches_either(self, test_db: Session):
        """Test that get_user_by_identity matches on either email or oidc_sub."""
        service = UserService(test_db)

        # Create user with both identifiers
        service.create_user(
            email="either@example.com",
            oidc_sub="auth0|either123",
        )

        # Find by email
        found1 = service.get_user_by_identity(email="either@example.com")
        assert found1 is not None

        # Find by OIDC sub
        found2 = service.get_user_by_identity(oidc_sub="auth0|either123")
        assert found2 is not None

        # Both should return the same user
        assert found1.id == found2.id

    def test_get_user_by_identity_no_params(self, test_db: Session):
        """Test that get_user_by_identity returns None when no params provided."""
        service = UserService(test_db)

        found = service.get_user_by_identity()
        assert found is None


class TestUserListing:
    """Tests for user listing."""

    def test_list_users(self, test_db: Session):
        """Test listing users."""
        service = UserService(test_db)

        # Create some users
        service.create_user(email="list1@example.com")
        service.create_user(email="list2@example.com")
        service.create_user(email="list3@example.com")

        users = service.list_users()

        assert len(users) == 3

    def test_list_users_with_pagination(self, test_db: Session):
        """Test listing users with pagination."""
        service = UserService(test_db)

        # Create 5 users
        for i in range(5):
            service.create_user(email=f"page{i}@example.com")

        # Get first page
        page1 = service.list_users(limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = service.list_users(limit=2, offset=2)
        assert len(page2) == 2

        # Get last page
        page3 = service.list_users(limit=2, offset=4)
        assert len(page3) == 1

    def test_list_users_excludes_inactive_by_default(self, test_db: Session):
        """Test that inactive users are excluded by default."""
        service = UserService(test_db)

        # Create active and inactive users
        service.create_user(email="active@example.com")
        inactive = service.create_user(email="inactive@example.com")
        service.deactivate_user(inactive.id)

        users = service.list_users()

        assert len(users) == 1
        assert users[0].email == "active@example.com"

    def test_list_users_includes_inactive_when_requested(self, test_db: Session):
        """Test that inactive users can be included."""
        service = UserService(test_db)

        # Create active and inactive users
        service.create_user(email="active2@example.com")
        inactive = service.create_user(email="inactive2@example.com")
        service.deactivate_user(inactive.id)

        users = service.list_users(include_inactive=True)

        assert len(users) == 2

    def test_count_users(self, test_db: Session):
        """Test counting users."""
        service = UserService(test_db)

        # Create some users
        service.create_user(email="count1@example.com")
        service.create_user(email="count2@example.com")

        count = service.count_users()
        assert count == 2

    def test_count_users_excludes_inactive_by_default(self, test_db: Session):
        """Test that count excludes inactive users by default."""
        service = UserService(test_db)

        service.create_user(email="countactive@example.com")
        inactive = service.create_user(email="countinactive@example.com")
        service.deactivate_user(inactive.id)

        count = service.count_users()
        assert count == 1

        count_all = service.count_users(include_inactive=True)
        assert count_all == 2


class TestUserUpdate:
    """Tests for user updates."""

    def test_update_user_display_name(self, test_db: Session):
        """Test updating user display name."""
        service = UserService(test_db)

        user = service.create_user(email="update@example.com", display_name="Old Name")
        updated = service.update_user(user.id, display_name="New Name")

        assert updated is not None
        assert updated.display_name == "New Name"

    def test_update_user_admin_status(self, test_db: Session):
        """Test updating user admin status."""
        service = UserService(test_db)

        user = service.create_user(email="makeadmin@example.com", is_admin=False)
        updated = service.update_user(user.id, is_admin=True)

        assert updated is not None
        assert updated.is_admin is True

    def test_update_user_api_permissions(self, test_db: Session):
        """Test updating user API permissions."""
        service = UserService(test_db)

        user = service.create_user(
            email="perms@example.com",
            can_use_registration_token=True,
            can_use_jit=True,
        )

        updated = service.update_user(
            user.id,
            can_use_registration_token=False,
            can_use_jit=False,
        )

        assert updated is not None
        assert updated.can_use_registration_token is False
        assert updated.can_use_jit is False

    def test_update_user_not_found(self, test_db: Session):
        """Test updating a non-existent user."""
        service = UserService(test_db)

        updated = service.update_user("nonexistent-uuid", display_name="New Name")
        assert updated is None

    def test_update_user_ignores_disallowed_fields(self, test_db: Session):
        """Test that update ignores fields not in allowed list."""
        service = UserService(test_db)

        user = service.create_user(email="nochange@example.com")

        # Try to update email (not in allowed_fields)
        updated = service.update_user(user.id, email="changed@example.com")

        assert updated is not None
        assert updated.email == "nochange@example.com"  # Unchanged


class TestUserActivation:
    """Tests for user activation/deactivation."""

    def test_deactivate_user(self, test_db: Session):
        """Test deactivating a user."""
        service = UserService(test_db)

        user = service.create_user(email="deactivate@example.com")
        result = service.deactivate_user(user.id)

        assert result is True

        # Verify user is inactive
        found = service.get_user_by_id(user.id)
        assert found.is_active is False

    def test_deactivate_user_not_found(self, test_db: Session):
        """Test deactivating a non-existent user."""
        service = UserService(test_db)

        result = service.deactivate_user("nonexistent-uuid")
        assert result is False

    def test_activate_user(self, test_db: Session):
        """Test activating a user."""
        service = UserService(test_db)

        user = service.create_user(email="activate@example.com")
        service.deactivate_user(user.id)

        result = service.activate_user(user.id)

        assert result is True

        # Verify user is active
        found = service.get_user_by_id(user.id)
        assert found.is_active is True

    def test_activate_user_not_found(self, test_db: Session):
        """Test activating a non-existent user."""
        service = UserService(test_db)

        result = service.activate_user("nonexistent-uuid")
        assert result is False


class TestLastLogin:
    """Tests for last login tracking."""

    def test_update_last_login(self, test_db: Session):
        """Test updating last login timestamp."""
        service = UserService(test_db)

        user = service.create_user(email="login@example.com")
        assert user.last_login_at is None

        service.update_last_login(user.id)

        # Refresh from database
        found = service.get_user_by_id(user.id)
        assert found.last_login_at is not None

    def test_update_last_login_nonexistent_user(self, test_db: Session):
        """Test updating last login for non-existent user (no error)."""
        service = UserService(test_db)

        # Should not raise
        service.update_last_login("nonexistent-uuid")
