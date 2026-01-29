"""Configuration management for the runner token service."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # GitHub App Configuration
    github_app_id: int = Field(..., description="GitHub App ID")
    github_app_installation_id: int = Field(
        ..., description="GitHub App Installation ID"
    )
    github_app_private_key_path: Path = Field(
        ..., description="Path to GitHub App private key"
    )
    github_org: str = Field(..., description="GitHub organization name")
    github_api_url: str = Field(
        default="https://api.github.com", description="GitHub API base URL"
    )

    # OIDC Configuration
    oidc_issuer: str = Field(..., description="OIDC issuer URL")
    oidc_audience: str = Field(..., description="Expected OIDC audience")
    oidc_jwks_url: str = Field(..., description="OIDC JWKS URL for token validation")
    enable_oidc_auth: bool = Field(
        default=True, description="Enable OIDC authentication"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./runner_service.db", description="Database connection URL"
    )

    # PostgreSQL Connection Pool Settings
    db_pool_size: int = Field(
        default=10, description="Database connection pool size (PostgreSQL only)"
    )
    db_max_overflow: int = Field(
        default=20,
        description="Maximum overflow connections beyond pool_size (PostgreSQL only)",
    )
    db_pool_recycle: int = Field(
        default=3600,
        description="Seconds before recycling connections (PostgreSQL only)",
    )

    # PostgreSQL SSL/TLS Settings
    db_ssl_mode: Optional[str] = Field(
        default=None,
        description="PostgreSQL SSL mode: disable, allow, prefer, require, verify-ca, verify-full",
    )
    db_ssl_cert: Optional[str] = Field(
        default=None, description="Path to client SSL certificate (PostgreSQL only)"
    )
    db_ssl_key: Optional[str] = Field(
        default=None, description="Path to client SSL key (PostgreSQL only)"
    )
    db_ssl_root_cert: Optional[str] = Field(
        default=None, description="Path to root SSL certificate (PostgreSQL only)"
    )

    # Service Configuration
    service_host: str = Field(default="0.0.0.0", description="Service host")
    service_port: int = Field(default=8000, description="Service port")
    log_level: str = Field(
        default="INFO",
        description="Application logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    access_log_tracing: bool = Field(
        default=False,
        description="Enable detailed tracing in access logs (headers, payloads)",
    )
    log_dir: Path = Field(default=Path("logs"), description="Directory for log files")

    # Security
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    admin_identities: str = Field(
        default="",
        description="Comma-separated list of admin user identities (email or OIDC sub)",
    )

    # Runner Configuration Defaults
    default_runner_group_id: int = Field(
        default=1, description="Default runner group ID"
    )
    registration_token_expiry_hours: int = Field(
        default=1, description="Registration token expiry in hours"
    )
    cleanup_stale_runners_hours: int = Field(
        default=24, description="Hours before considering a runner stale"
    )

    # Sync Configuration
    sync_enabled: bool = Field(
        default=True, description="Enable background runner sync with GitHub"
    )
    sync_interval_seconds: int = Field(
        default=120, description="Seconds between sync cycles (default: 2 min)"
    )
    sync_on_startup: bool = Field(
        default=True, description="Run sync immediately on startup"
    )

    # Webhook Configuration
    github_webhook_secret: str = Field(
        default="", description="GitHub webhook secret for signature verification"
    )

    # Label Policy Enforcement
    label_policy_enforcement: str = Field(
        default="audit",
        description="Label policy enforcement mode: 'audit' (log only) or 'enforce' (cancel workflow)",
    )

    # JIT Label Drift Enforcement
    label_drift_delete_busy_runners: bool = Field(
        default=False,
        description="Delete runners with label drift even if currently running a job",
    )

    # HTTPS Configuration
    https_enabled: bool = Field(
        default=False,
        description="Enable HTTPS (recommended for production)",
    )
    https_cert_file: Optional[Path] = Field(
        default=None,
        description="Path to SSL certificate file (required if https_enabled=true)",
    )
    https_key_file: Optional[Path] = Field(
        default=None,
        description="Path to SSL private key file (required if https_enabled=true)",
    )

    # Bootstrap Admin Configuration
    bootstrap_admin_username: str = Field(
        default="admin",
        description="Bootstrap admin username (created on first startup)",
    )
    bootstrap_admin_password: str = Field(
        default="", description="Bootstrap admin password (required for first startup)"
    )
    bootstrap_admin_email: Optional[str] = Field(
        default=None, description="Bootstrap admin email (optional)"
    )

    # Dashboard Features
    enable_new_dashboard: bool = Field(
        default=False,
        description="Enable new React-based dashboard at /app path",
    )

    @field_validator("github_app_private_key_path")
    @classmethod
    def validate_private_key_path(cls, v: Path) -> Path:
        """Validate that the private key file exists."""
        if not v.exists():
            raise ValueError(f"GitHub App private key file not found: {v}")
        if not v.is_file():
            raise ValueError(f"GitHub App private key path is not a file: {v}")
        return v

    @property
    def github_app_private_key(self) -> str:
        """Read and return the GitHub App private key."""
        return self.github_app_private_key_path.read_text()


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()  # type: ignore[arg-type]
