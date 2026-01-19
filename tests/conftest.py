"""Pytest configuration and fixtures."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


# Create a temporary private key file BEFORE importing app modules
# This is necessary because app.config validates the key path on import
_TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7AFPBDM8MBx8v9IKV
sHPQoWXCaJz8F/hGe2A/K1DKdP1r9LqJrfKvvl1MslU4mYh+HZy5C7Z3xJKZfT1L
hV7C/sT1j/EkQGG9mB2xLPNbNvSoV3rvDH3WLnH7RkVUQeO/FZk7C6CZdVvRlVmY
FmCu5BQZR9WQfzFj3Q9Y8pPCf9hF7kH7NKkZ3SX7fLoVewxvz/8Lj4CjQgvYK7M1
sHOTcP3cQM6gcD3h/K9K1YiuQfvWYvvL+WmRmyE7VgHvJ/rH5PRTB3JFNvSn8tKM
eCxEYpYKZxPrKQIDAQABAoIBADf/0Q0fJfP3AxPonKXhqu3AOHX1MCnNfNKvqxkI
wJa/K+bD2F7dNvYJAC8l2B3YmPRXeyYT8J7+heEW2bQqFvGgVvRom9z3HfhaO3Pq
L7rX0CFM/M10Y66PAKz7C8BSr57iN0bVOYe9Wf3yjEnxCmCmEXyMdC/jqSHC/Bmj
kd6FNkI/mYOGK2uPPOAfErNgqprF3VNmUXXQ+nStStTt7ENZAV0Bz8n7HnbNfLBD
8H4v8Q8SuN3S5u+P/TAMNaK7V6pSe/R7LqgOYQFCBwSRfHOmVmaLbSP8nVOmP/d5
SqB5P/0ECwYm7SMX5HHN7U0mNQNRx7a7ICy8MRELfEkCgYEA7AAGhj2m1w1f3B7F
Gf2g0VFCfPT0UMFQ0f9aP/I6sTOwOLFbHUu8JP9r3QVq1mDJrqCX6H/JUFX0rr8g
I/xvf1U00GVCny3T5FMhvHhdklPnaD9yPbNqkN/7k0SD/i5JNmJYU7zb3nF8svYB
QD9qzjqbW4RYLqvAeOLwPVb7IUUCgYEA5B3xF/v/jF1qYqJXPD0gb6H+h4MJIef1
f0bQN5S3X7f9Bk0xa1d4fZ1XC7fb2fLQD3gLJNH1l4S2+EzKB9Z+2SPRLL/RH6n2
j8PbPNhYH81F3qXD9wZ3TKF8MdO7P8bevbLzQl0dLnfe+rW/WAPFcj5qlPxiuNkJ
MJkXvTaH5g0CgYEAqV5SCwP0M3AbTwBP7M5J4MdO4hZb9LGz/CnMdvJHNpTbJdmK
XP/qi4D0wg2FVw+h/h/TXI+hVWPoF9g2H+cPfMIJBFnQ8YmMqyYQV1Rwu3N7L3kL
E0Q1JAwPvfXdJFZf7hDuP/5FVrYMwYlGXCxEMqRmxE0YbWUP1ckJfnvT+R0CgYBD
jUQcXQSUINv8n/h7/Tt0vJJMn7lGMV9l3AffSXQ9fL+lQZX3XGff0RSlCYK+jhWe
sS+AvW1DDgMsvVJNYqPiO7j4kS1yDJKptvmhY/8+kCdqm7VW0y1M9GKsHvtBKzVl
RNv4Mzf2GNAFNC4/M2CfHnAdb1k9Jg/R8a1fKqPVaQKBgH/E3P1NLv7BZfD2GSSY
PWqRz6OC5VdPWCVVNCRTDu2hfJW3xZN7p5M/K5qPw9nOKsaZNqFkBBVXjpL7LVXL
JHk8XLNK6dD0F5m2TOdK1QVKBA2Y79QD+mp/16akN9kP7KOCaV8S3kciNabAcPMD
mWJkVcmXvqNpEfPo9pZxBwGp
-----END RSA PRIVATE KEY-----"""


def _setup_test_environment():
    """Set up test environment variables before app import."""
    # Create temporary key file
    key_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".pem", delete=False, prefix="test_github_key_"
    )
    key_file.write(_TEST_PRIVATE_KEY)
    key_file.flush()
    key_file.close()

    # Set environment variables for testing
    os.environ.setdefault("GITHUB_APP_ID", "123456")
    os.environ.setdefault("GITHUB_APP_INSTALLATION_ID", "12345678")
    os.environ.setdefault("GITHUB_APP_PRIVATE_KEY_PATH", key_file.name)
    os.environ.setdefault("GITHUB_ORG", "test-org")
    os.environ.setdefault("OIDC_ISSUER", "https://test-issuer.example.com/")
    os.environ.setdefault("OIDC_AUDIENCE", "test-audience")
    os.environ.setdefault(
        "OIDC_JWKS_URL", "https://test-issuer.example.com/.well-known/jwks.json"
    )
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("ENABLE_OIDC_AUTH", "true")

    return key_file.name


# Set up environment before any app imports
_temp_key_path = _setup_test_environment()


# Now we can safely import app modules
from app.auth.dependencies import AuthenticatedUser  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Clean up temporary files after test session."""
    try:
        if _temp_key_path and os.path.exists(_temp_key_path):
            os.unlink(_temp_key_path)
    except Exception:
        pass


# Test database setup
@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a fresh test database for each test."""
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator:
    """Create a test client with test database."""
    from fastapi.testclient import TestClient

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# Mock user fixtures
@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create a mock authenticated user."""
    return AuthenticatedUser(
        identity="test-user@example.com",
        claims={
            "sub": "auth0|test123",
            "email": "test-user@example.com",
            "aud": "runner-token-service",
        },
    )


@pytest.fixture
def mock_admin_user() -> AuthenticatedUser:
    """Create a mock admin user."""
    return AuthenticatedUser(
        identity="admin@example.com",
        claims={
            "sub": "auth0|admin123",
            "email": "admin@example.com",
            "aud": "runner-token-service",
        },
    )


@pytest.fixture
def mock_other_user() -> AuthenticatedUser:
    """Create a mock user different from the default test user."""
    return AuthenticatedUser(
        identity="other-user@example.com",
        claims={
            "sub": "auth0|other456",
            "email": "other-user@example.com",
            "aud": "runner-token-service",
        },
    )


# Mock settings fixture
@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.github_app_id = 12345
    settings.github_app_installation_id = 67890
    settings.github_org = "test-org"
    settings.github_api_url = "https://api.github.com"
    settings.database_url = "sqlite:///:memory:"
    settings.default_runner_group_id = 1
    settings.admin_identities = "admin@example.com"
    settings.enable_oidc_auth = True
    return settings


# Mock GitHub client fixtures
@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client."""
    mock = AsyncMock()
    mock.generate_registration_token = AsyncMock(
        return_value=(
            "ATEST_REGISTRATION_TOKEN",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    mock.get_runner_by_name = AsyncMock(return_value=None)
    mock.get_runner_by_id = AsyncMock(return_value=None)
    mock.delete_runner = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_github_runner():
    """Create a mock GitHub runner response."""
    runner = MagicMock()
    runner.id = 12345
    runner.name = "test-runner"
    runner.status = "online"
    runner.busy = False
    runner.labels = ["self-hosted", "linux", "x64", "test-label"]
    return runner


# Authentication override fixtures
@pytest.fixture
def auth_override(mock_user: AuthenticatedUser):
    """Override authentication to return mock user."""
    from app.auth.dependencies import get_current_user

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_auth_override(mock_admin_user: AuthenticatedUser, mock_settings):
    """Override authentication to return admin user."""
    from app.auth.dependencies import get_current_user
    from app.config import get_settings

    async def override_get_current_user():
        return mock_admin_user

    def override_get_settings():
        return mock_settings

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings
    yield mock_admin_user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def no_auth_override(mock_settings):
    """Override settings to disable OIDC auth for testing."""
    from app.config import get_settings

    mock_settings.enable_oidc_auth = False

    def override_get_settings():
        return mock_settings

    app.dependency_overrides[get_settings] = override_get_settings
    yield mock_settings
    app.dependency_overrides.pop(get_settings, None)
