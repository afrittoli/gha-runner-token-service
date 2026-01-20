# JIT Runner Provisioning Design

## Overview

This document describes the design for Just-In-Time (JIT) runner provisioning as an alternative to the existing registration token workflow. JIT provisioning offers stronger security guarantees by enforcing labels and ephemeral mode at registration time.

## Background

### Current Registration Token Flow

1. Client requests a runner via `POST /api/v1/runners`
2. Service validates labels against policy
3. Service calls GitHub API to get a registration token
4. Client receives: registration token, runner name, labels, config command
5. Client runs `./config.sh --token <token> --labels <labels> --ephemeral`
6. **Risk**: Client can ignore provided labels and use different ones

### JIT Configuration Flow

1. Client requests a runner via `POST /api/v1/runners/jit`
2. Service validates labels against policy
3. Service calls GitHub API to generate JIT config (includes labels, ephemeral flag)
4. Client receives: encoded JIT config, runner name
5. Client runs `./run.sh --jitconfig <encoded_config>`
6. **Benefit**: Labels and ephemeral mode are pre-configured and cannot be overridden

## Security Benefits

| Aspect | Registration Token | JIT Configuration |
|--------|-------------------|-------------------|
| Label enforcement | Client can ignore | Server-side enforced |
| Ephemeral mode | Client can skip `--ephemeral` | Always enforced |
| Credential lifetime | Token valid ~1 hour, then permanent credentials | Credentials tied to pre-registered runner |
| Configuration step | Required (`config.sh`) | Not needed (direct `run.sh`) |

## API Design

### New Endpoint: POST /api/v1/runners/jit

**Request (with exact name):**
```json
{
  "runner_name": "my-runner-001",
  "labels": ["gpu", "large"],
  "runner_group_id": 1,
  "work_folder": "_work"
}
```

**Request (with name prefix - auto-generates unique suffix):**
```json
{
  "runner_name_prefix": "my-runner",
  "labels": ["gpu", "large"],
  "runner_group_id": 1,
  "work_folder": "_work"
}
```

Note: You must provide either `runner_name` OR `runner_name_prefix`, but not both.
When using `runner_name_prefix`, a unique suffix (e.g., `-a1b2c3`) is automatically appended.

**Response (Success - 201 Created):**
```json
{
  "runner_id": "uuid-here",
  "runner_name": "my-runner-001",
  "encoded_jit_config": "base64-encoded-config...",
  "labels": ["self-hosted", "linux", "x64", "gpu", "large"],
  "expires_at": "2024-01-20T12:00:00Z",
  "run_command": "./run.sh --jitconfig <encoded_jit_config>"
}
```

**Response (Policy Violation - 403 Forbidden):**
```json
{
  "detail": "Labels ['forbidden-label'] not permitted by policy",
  "error_code": "LABEL_POLICY_VIOLATION"
}
```

### Comparison with Existing Endpoint

| Aspect | POST /api/v1/runners | POST /api/v1/runners/jit |
|--------|---------------------|--------------------------|
| Returns | Registration token | Encoded JIT config |
| Config step needed | Yes (`config.sh`) | No |
| Ephemeral enforced | No (client choice) | Yes (always) |
| Labels enforced | At validation only | At registration |

## Implementation Details

### GitHub API Integration

The GitHub API endpoint is:
```
POST /orgs/{org}/actions/runners/generate-jitconfig
```

**Request body:**
```json
{
  "name": "runner-name",
  "runner_group_id": 1,
  "labels": ["label1", "label2"],
  "work_folder": "_work"
}
```

**Response:**
```json
{
  "runner": {
    "id": 12345,
    "name": "runner-name",
    "os": "linux",
    "status": "offline",
    "labels": [...]
  },
  "encoded_jit_config": "base64-string..."
}
```

### What's in the JIT Config

The `encoded_jit_config` is a base64-encoded JSON containing:
- `.runner` file contents (runner settings including `Ephemeral: true`)
- `.credentials` file contents (OAuth client ID and authorization URL)
- `.credentials_rsaparams` file contents (RSA key pair for authentication)

The runner decodes this and writes the files, then starts immediately.

### Database Changes

No schema changes required. The existing `Runner` model works for both flows:
- `registration_token` field will be NULL for JIT runners
- `github_runner_id` is set immediately (not after first sync)

### Service Layer

New method in `RunnerService`:

```python
async def provision_runner_jit(
    self,
    runner_name: str,
    labels: list[str],
    runner_group_id: int,
    user_identity: str,
    work_folder: str = "_work",
) -> JitProvisionResponse:
    """
    Provision a runner using JIT configuration.

    Returns the encoded JIT config that the client passes to run.sh.
    Labels and ephemeral mode are enforced server-side.
    """
```

New method in `GitHubClient`:

```python
async def generate_jit_config(
    self,
    name: str,
    runner_group_id: int,
    labels: list[str],
    work_folder: str = "_work",
) -> JitConfigResponse:
    """
    Generate JIT configuration for a runner.

    The runner will be registered with the specified labels and
    ephemeral mode enabled.
    """
```

## Sync Service Updates

### Label Drift Detection

The sync service already validates labels. Updates needed:

1. **Track original labels**: Store the labels from provisioning time
2. **Compare on sync**: Check if GitHub runner labels differ from original
3. **Handle drift**:
   - If runner is idle: Log security event, delete runner
   - If runner is busy: Log security event, optionally delete (configurable)

### New Configuration

```python
# Label drift enforcement for busy runners
label_drift_delete_busy_runners: bool = Field(
    default=False,
    description="Delete runners with label drift even if currently running a job"
)
```

### Security Events

New event type: `label_drift_detected`
- Logged when runner labels differ from provisioned labels
- Includes: original labels, current labels, runner status, action taken

## HTTPS Support

### Configuration

```python
# HTTPS Configuration
https_enabled: bool = Field(
    default=True,
    description="Enable HTTPS (recommended for production)"
)
https_cert_file: Optional[Path] = Field(
    default=None,
    description="Path to SSL certificate file"
)
https_key_file: Optional[Path] = Field(
    default=None,
    description="Path to SSL private key file"
)
```

### Development Mode

For local development without certificates:
```bash
export HTTPS_ENABLED=false
```

Or with self-signed certificates:
```bash
# Generate self-signed cert
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

export HTTPS_ENABLED=true
export HTTPS_CERT_FILE=cert.pem
export HTTPS_KEY_FILE=key.pem
```

## Migration Path

1. Deploy JIT endpoint alongside existing registration token endpoint
2. Both endpoints remain functional
3. Admins can choose which to enable per user (future: user authorization table)
4. Eventually deprecate registration token endpoint (optional)

## Testing Strategy

### Unit Tests
- JIT config generation in GitHubClient
- Label validation for JIT requests
- Runner creation with JIT metadata
- Label drift detection in sync service

### Integration Tests
- End-to-end JIT provisioning (mocked GitHub API)
- Sync detecting and handling label drift
- Security event logging for drift

### Manual Testing
- Actual JIT runner provisioning against GitHub
- Verify runner starts with correct labels
- Verify ephemeral behavior (runner deletes after job)

## Schemas

### Request Schema

```python
class JitProvisionRequest(BaseModel):
    """Request to provision a runner using JIT configuration."""

    runner_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Exact name for the runner (mutually exclusive with runner_name_prefix)"
    )
    runner_name_prefix: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Prefix for auto-generated runner name (e.g., 'my-runner' becomes 'my-runner-a1b2c3')"
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Custom labels for the runner"
    )
    runner_group_id: Optional[int] = Field(
        default=None,
        description="Runner group ID (uses default if not specified)"
    )
    work_folder: str = Field(
        default="_work",
        description="Working directory for the runner"
    )

    # Validation: exactly one of runner_name or runner_name_prefix must be provided
```

### Response Schema

```python
class JitProvisionResponse(BaseModel):
    """Response containing JIT configuration for a runner."""

    runner_id: str = Field(
        ...,
        description="Internal runner UUID"
    )
    runner_name: str = Field(
        ...,
        description="Runner name"
    )
    encoded_jit_config: str = Field(
        ...,
        description="Base64-encoded JIT configuration to pass to run.sh"
    )
    labels: list[str] = Field(
        ...,
        description="Full list of labels including system labels"
    )
    expires_at: datetime = Field(
        ...,
        description="When the JIT config expires (runner must start before this)"
    )
    run_command: str = Field(
        ...,
        description="Command to start the runner"
    )
```

## Future Considerations

1. **User Authorization**: Once implemented, admins can restrict which users can use JIT vs registration token
2. **Rate Limiting**: JIT config generation counts against GitHub API rate limits
3. **Audit Trail**: All JIT provisioning should be logged for compliance
4. **Metrics**: Track JIT vs registration token usage for migration planning
