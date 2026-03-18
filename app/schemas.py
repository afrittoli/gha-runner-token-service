"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class RunnerDetailResponse(BaseModel):
    """Detailed runner information."""

    runner_id: str
    runner_name: str
    status: str
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


class SecurityEventResponse(BaseModel):
    """Security event information."""

    id: int
    event_type: str
    severity: str
    runner_id: Optional[str]
    runner_name: Optional[str]
    github_runner_id: Optional[int]
    team_id: Optional[str] = None
    team_name: Optional[str] = None
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
    team_id: Optional[str] = Field(
        default=None,
        description="Team ID for team-based authorization (optional, uses user's teams if not specified)",
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
    can_use_jit: bool = Field(
        default=True,
        description="Allow access to JIT API",
    )
    team_ids: List[str] = Field(
        default_factory=list,
        description="Team IDs to add the user to on creation",
    )

    def model_post_init(self, __context) -> None:
        """Validate that at least one identifier is provided."""
        if not self.email and not self.oidc_sub:
            raise ValueError("Either 'email' or 'oidc_sub' must be provided")
        if not self.is_admin and not self.team_ids:
            raise ValueError("Non-admin users must belong to at least one team")


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
    can_use_jit: Optional[bool] = Field(
        default=None,
        description="Allow access to JIT API",
    )


class DeactivateUserRequest(BaseModel):
    """Request to deactivate a user."""

    comment: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for deactivating the user (required for audit trail)",
    )


class UserResponse(BaseModel):
    """User information response."""

    id: str
    email: Optional[str]
    oidc_sub: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    is_active: bool
    can_use_jit: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    created_by: Optional[str]


class UserListResponse(BaseModel):
    """List of users response."""

    users: List[UserResponse]
    total: int


class AuditLogResponse(BaseModel):
    """Audit log entry information."""

    id: int
    event_type: str
    runner_id: Optional[str]
    runner_name: Optional[str]
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    user_identity: str
    oidc_sub: Optional[str]
    request_ip: Optional[str]
    user_agent: Optional[str]
    event_data: Optional[dict]
    success: bool
    error_message: Optional[str]
    timestamp: datetime
    team_id: Optional[str] = None
    team_name: Optional[str] = None


class AuditLogListResponse(BaseModel):
    """List of audit log entries."""

    logs: List[AuditLogResponse]
    total: int


# Batch Operation Schemas


class BatchActionRequest(BaseModel):
    """Request for batch admin actions requiring audit comment."""

    comment: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Required comment explaining the reason for this action (audit trail)",
    )


class BatchDisableUsersRequest(BatchActionRequest):
    """Request to disable multiple users."""

    user_ids: Optional[List[str]] = Field(
        default=None,
        description="List of user IDs to disable. If empty/null, disables all non-admin users.",
    )
    exclude_admins: bool = Field(
        default=True,
        description="Exclude admin users from batch disable (safety measure)",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, preview affected users without making changes",
    )


class BatchRestoreUsersRequest(BatchActionRequest):
    """Request to restore (reactivate) multiple users."""

    user_ids: Optional[List[str]] = Field(
        default=None,
        description="List of user IDs to restore. If empty/null, restores all inactive users.",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, preview affected users without making changes",
    )


class BatchDeleteRunnersRequest(BatchActionRequest):
    """Request to delete multiple runners."""

    user_identity: Optional[str] = Field(
        default=None,
        description="Delete all runners for this user identity.",
    )
    runner_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific runner IDs to delete. Takes precedence over user_identity.",
    )

    def model_post_init(self, __context) -> None:
        """Require targeting field to prevent fleet-wide deletion."""
        if not self.runner_ids and not self.user_identity:
            raise ValueError(
                "At least one of 'runner_ids' or 'user_identity' must be" " provided"
            )


class BatchDeactivateTeamsRequest(BatchActionRequest):
    """Request to deactivate multiple teams."""

    team_ids: Optional[List[str]] = Field(
        default=None,
        description=("List of team IDs to deactivate. If null, deactivates all."),
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason stored on each team record (separate from the audit comment)",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, preview affected teams without making changes",
    )


class BatchReactivateTeamsRequest(BatchActionRequest):
    """Request to reactivate multiple teams."""

    team_ids: Optional[List[str]] = Field(
        default=None,
        description="List of team IDs to reactivate. If empty/null, reactivates all inactive teams.",
    )


class BatchActionResponse(BaseModel):
    """Response for batch admin actions."""

    success: bool
    action: str
    affected_count: int
    failed_count: int = 0
    comment: str
    dry_run: bool = False
    details: Optional[List[dict]] = Field(
        default=None,
        description="Details of each affected item (success/failure)",
    )


# Team Management Schemas


class TeamCreate(BaseModel):
    """Request to create a new team."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Team name (kebab-case, e.g., 'platform-team')",
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="Team description"
    )
    required_labels: List[str] = Field(
        ..., description="Labels that are always added to team runners"
    )
    optional_label_patterns: Optional[List[str]] = Field(
        default=None,
        description="Regex patterns for optional labels (e.g., 'feature-.*')",
    )
    max_runners: Optional[int] = Field(
        default=None, ge=0, description="Maximum concurrent runners (null = unlimited)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate team name is kebab-case."""
        import re

        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError(
                "Team name must be kebab-case (lowercase, alphanumeric, hyphens)"
            )
        return v

    @field_validator("optional_label_patterns")
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


class TeamUpdate(BaseModel):
    """Request to update a team."""

    description: Optional[str] = Field(
        default=None, max_length=500, description="Team description"
    )
    required_labels: Optional[List[str]] = Field(
        default=None, description="Labels that are always added to team runners"
    )
    optional_label_patterns: Optional[List[str]] = Field(
        default=None,
        description="Regex patterns for optional labels (e.g., 'feature-.*')",
    )
    max_runners: Optional[int] = Field(
        default=None, ge=0, description="Maximum concurrent runners (null = unlimited)"
    )

    @field_validator("optional_label_patterns")
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


class TeamDeactivate(BaseModel):
    """Request to deactivate a team."""

    reason: str = Field(..., min_length=1, description="Reason for deactivation")


class TeamResponse(BaseModel):
    """Team information."""

    id: str
    name: str
    description: Optional[str]
    required_labels: List[str]
    optional_label_patterns: Optional[List[str]]
    max_runners: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    deactivation_reason: Optional[str] = None
    # Runtime stats
    member_count: Optional[int] = Field(
        default=None, description="Number of users in team"
    )
    active_runner_count: Optional[int] = Field(
        default=None, description="Number of active/pending runners"
    )


class TeamListResponse(BaseModel):
    """List of teams."""

    teams: List[TeamResponse]
    total: int


class TeamMemberResponse(BaseModel):
    """Team member information."""

    user_id: str
    email: Optional[str]
    display_name: Optional[str]
    joined_at: datetime
    added_by: Optional[str]


class TeamMembersListResponse(BaseModel):
    """List of team members."""

    team_id: str
    team_name: str
    members: List[TeamMemberResponse]
    total: int


class AddTeamMemberRequest(BaseModel):
    """Request to add a user to a team."""

    user_id: str = Field(..., description="User ID to add to team")


class UserTeamsResponse(BaseModel):
    """List of teams a user belongs to."""

    user_id: str
    teams: List[TeamResponse]
    total: int


# ---------------------------------------------------------------------------
# OAuth M2M client schemas
# ---------------------------------------------------------------------------


class OAuthClientCreate(BaseModel):
    """Request to register a new OAuth M2M client for a team."""

    client_id: str = Field(
        ...,
        description="Auth0 client_id of the M2M application",
        min_length=1,
    )
    team_id: str = Field(..., description="Team this client is authorized for")
    description: Optional[str] = Field(
        None, description="Human-readable label (e.g. 'CI pipeline')"
    )


class OAuthClientUpdate(BaseModel):
    """Request to update an OAuth M2M client."""

    description: Optional[str] = Field(None, description="New description")
    is_active: Optional[bool] = Field(None, description="Enable or disable")


class OAuthClientResponse(BaseModel):
    """OAuth M2M client details."""

    id: str
    client_id: str
    team_id: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    created_by: Optional[str]
    last_used_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class OAuthClientListResponse(BaseModel):
    """Paginated list of OAuth M2M clients."""

    clients: List[OAuthClientResponse]
    total: int


# ---------------------------------------------------------------------------
# Team-scoped events schemas
# ---------------------------------------------------------------------------


class TeamAuditLogListResponse(BaseModel):
    """Team-scoped list of audit log entries."""

    team_id: str
    team_name: str
    logs: List[AuditLogResponse]
    total: int


class TeamSecurityEventListResponse(BaseModel):
    """Team-scoped list of security events."""

    team_id: str
    team_name: str
    events: List[SecurityEventResponse]
    total: int
