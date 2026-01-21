"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ProvisionRunnerRequest(BaseModel):
    """Request to provision a new runner."""

    runner_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Exact name for the runner (mutually exclusive with runner_name_prefix)",
    )
    runner_name_prefix: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Prefix for auto-generated runner name (e.g., 'my-runner' becomes 'my-runner-a1b2c3')",
    )
    labels: List[str] = Field(
        default_factory=list,
        description="Labels for the runner (used for job targeting)",
    )
    runner_group_id: Optional[int] = Field(
        default=None, description="Runner group ID (uses default if not specified)"
    )
    ephemeral: bool = Field(
        default=True,
        description="Whether runner auto-deletes after one job (recommended: true)",
    )
    disable_update: bool = Field(
        default=False, description="Disable automatic runner updates"
    )

    @field_validator("runner_name")
    @classmethod
    def validate_runner_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate runner name format."""
        if v is not None and not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Runner name must contain only alphanumeric, hyphens, and underscores"
            )
        return v

    @field_validator("runner_name_prefix")
    @classmethod
    def validate_runner_name_prefix(cls, v: Optional[str]) -> Optional[str]:
        """Validate runner name prefix format."""
        if v is not None and not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Runner name prefix must contain only alphanumeric, hyphens, and underscores"
            )
        return v

    def model_post_init(self, __context) -> None:
        """Validate that either runner_name or runner_name_prefix is provided, but not both."""
        if self.runner_name is None and self.runner_name_prefix is None:
            raise ValueError(
                "Either 'runner_name' or 'runner_name_prefix' must be provided"
            )
        if self.runner_name is not None and self.runner_name_prefix is not None:
            raise ValueError(
                "Only one of 'runner_name' or 'runner_name_prefix' can be provided, not both"
            )

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: List[str]) -> List[str]:
        """Validate labels format."""
        for label in v:
            if not label.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    f"Label '{label}' must contain only alphanumeric, hyphens, and underscores"
                )
        return v


class ProvisionRunnerResponse(BaseModel):
    """Response after provisioning a runner."""

    runner_id: str = Field(..., description="Internal runner ID")
    runner_name: str = Field(..., description="Runner name")
    registration_token: str = Field(
        ..., description="GitHub registration token (expires in 1 hour)"
    )
    expires_at: datetime = Field(..., description="Token expiration time")
    github_url: str = Field(..., description="GitHub organization URL")
    runner_group_id: int = Field(..., description="Runner group ID")
    ephemeral: bool = Field(..., description="Whether runner is ephemeral")
    labels: List[str] = Field(..., description="Runner labels")
    configuration_command: str = Field(
        ..., description="Command to configure the runner"
    )


class RunnerStatus(BaseModel):
    """Runner status information."""

    runner_id: str
    runner_name: str
    status: str  # pending, active, offline, deleted
    github_runner_id: Optional[int] = None
    runner_group_id: int
    labels: List[str]
    ephemeral: bool
    provisioned_by: str
    created_at: datetime
    updated_at: datetime
    registered_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class RunnerListResponse(BaseModel):
    """List of runners."""

    runners: List[RunnerStatus]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    error_code: Optional[str] = None


class DeprovisionResponse(BaseModel):
    """Response after deprovisioning a runner."""

    runner_id: str
    runner_name: str
    success: bool
    message: str


# Label Policy Schemas


class LabelPolicyCreate(BaseModel):
    """Request to create or update a label policy."""

    user_identity: str = Field(..., description="User identity to apply policy to")
    allowed_labels: List[str] = Field(..., description="Explicitly allowed labels")
    label_patterns: Optional[List[str]] = Field(
        default=None, description="Regex patterns for allowed labels (e.g., 'team-.*')"
    )
    max_runners: Optional[int] = Field(
        default=None, ge=0, description="Maximum concurrent runners"
    )
    require_approval: bool = Field(
        default=False, description="Whether provisioning requires admin approval"
    )
    description: Optional[str] = Field(default=None, description="Policy description")

    @field_validator("label_patterns")
    @classmethod
    def validate_patterns(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate regex patterns."""
        if v:
            import re

            for pattern in v:
                try:
                    re.compile(pattern)
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
        return v


class LabelPolicyResponse(BaseModel):
    """Label policy information."""

    user_identity: str
    allowed_labels: List[str]
    label_patterns: Optional[List[str]]
    max_runners: Optional[int]
    require_approval: bool
    description: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class LabelPolicyListResponse(BaseModel):
    """List of label policies."""

    policies: List[LabelPolicyResponse]
    total: int


class SecurityEventResponse(BaseModel):
    """Security event information."""

    id: int
    event_type: str
    severity: str
    runner_id: Optional[str]
    runner_name: Optional[str]
    github_runner_id: Optional[int]
    user_identity: str
    violation_data: dict
    action_taken: Optional[str]
    timestamp: datetime


class SecurityEventListResponse(BaseModel):
    """List of security events."""

    events: List[SecurityEventResponse]
    total: int


# JIT Provisioning Schemas


class JitProvisionRequest(BaseModel):
    """Request to provision a runner using JIT configuration."""

    runner_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Exact name for the runner (mutually exclusive with runner_name_prefix)",
    )
    runner_name_prefix: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Prefix for auto-generated runner name (e.g., 'my-runner' becomes 'my-runner-a1b2c3')",
    )
    labels: List[str] = Field(
        default_factory=list,
        description="Custom labels for the runner (system labels added automatically)",
    )
    runner_group_id: Optional[int] = Field(
        default=None,
        description="Runner group ID (uses default if not specified)",
    )
    work_folder: str = Field(
        default="_work",
        description="Working directory for the runner",
    )

    @field_validator("runner_name")
    @classmethod
    def validate_runner_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate runner name format."""
        if v is not None and not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Runner name must contain only alphanumeric, hyphens, and underscores"
            )
        return v

    @field_validator("runner_name_prefix")
    @classmethod
    def validate_runner_name_prefix(cls, v: Optional[str]) -> Optional[str]:
        """Validate runner name prefix format."""
        if v is not None and not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Runner name prefix must contain only alphanumeric, hyphens, and underscores"
            )
        return v

    def model_post_init(self, __context) -> None:
        """Validate that either runner_name or runner_name_prefix is provided, but not both."""
        if self.runner_name is None and self.runner_name_prefix is None:
            raise ValueError(
                "Either 'runner_name' or 'runner_name_prefix' must be provided"
            )
        if self.runner_name is not None and self.runner_name_prefix is not None:
            raise ValueError(
                "Only one of 'runner_name' or 'runner_name_prefix' can be provided, not both"
            )

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: List[str]) -> List[str]:
        """Validate labels format."""
        for label in v:
            if not label.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    f"Label '{label}' must contain only alphanumeric, hyphens, and underscores"
                )
        return v


class JitProvisionResponse(BaseModel):
    """Response containing JIT configuration for a runner."""

    runner_id: str = Field(
        ...,
        description="Internal runner UUID",
    )
    runner_name: str = Field(
        ...,
        description="Runner name",
    )
    encoded_jit_config: str = Field(
        ...,
        description="Base64-encoded JIT configuration to pass to run.sh --jitconfig",
    )
    labels: List[str] = Field(
        ...,
        description="Full list of labels including system labels (self-hosted, os, arch)",
    )
    expires_at: datetime = Field(
        ...,
        description="When the JIT config expires (runner must start before this)",
    )
    run_command: str = Field(
        ...,
        description="Command to start the runner",
    )


# User Authorization Schemas


class UserCreate(BaseModel):
    """Request to create a new user."""

    email: Optional[str] = Field(
        default=None,
        description="User email (primary identifier)",
    )
    oidc_sub: Optional[str] = Field(
        default=None,
        description="OIDC subject claim (alternative identifier)",
    )
    display_name: Optional[str] = Field(
        default=None,
        description="Display name for dashboard",
    )
    is_admin: bool = Field(
        default=False,
        description="Grant admin privileges",
    )
    can_use_registration_token: bool = Field(
        default=True,
        description="Allow access to registration token API",
    )
    can_use_jit: bool = Field(
        default=True,
        description="Allow access to JIT API",
    )

    def model_post_init(self, __context) -> None:
        """Validate that at least one identifier is provided."""
        if not self.email and not self.oidc_sub:
            raise ValueError("Either 'email' or 'oidc_sub' must be provided")


class UserUpdate(BaseModel):
    """Request to update a user."""

    display_name: Optional[str] = Field(
        default=None,
        description="Display name for dashboard",
    )
    is_admin: Optional[bool] = Field(
        default=None,
        description="Admin privileges",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether user account is active",
    )
    can_use_registration_token: Optional[bool] = Field(
        default=None,
        description="Allow access to registration token API",
    )
    can_use_jit: Optional[bool] = Field(
        default=None,
        description="Allow access to JIT API",
    )


class UserResponse(BaseModel):
    """User information response."""

    id: str
    email: Optional[str]
    oidc_sub: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    is_active: bool
    can_use_registration_token: bool
    can_use_jit: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    created_by: Optional[str]


class UserListResponse(BaseModel):
    """List of users response."""

    users: List[UserResponse]
    total: int
