# Usage Examples

This document provides practical examples for using the Runner Token Service.

## Table of Contents

- [Setup](#setup)
- [JIT Provisioning (Recommended)](#jit-provisioning)
- [JIT with Podman](#jit-with-podman)
- [API Examples](#api-examples)
- [CLI Examples](#cli-examples)
- [Integration Examples](#integration-examples)
- [Legacy: Registration Token Workflow](#basic-workflow)

## Setup

### 1. Create GitHub App

```bash
# Navigate to: https://github.com/settings/apps/new
# Configure the app with these settings:
# - Name: Runner Token Service
# - Webhook: Disabled
# - Organization permissions:
#   - Self-hosted runners: Read & Write
#
# After creating:
# 1. Generate private key (download .pem file)
# 2. Install app to your organization
# 3. Note App ID and Installation ID
```

### 2. Configure Service

```bash
cd runner-token-service

# Create .env file
cat > .env <<EOF
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_ORG=my-org

OIDC_ISSUER=https://auth.example.com
OIDC_AUDIENCE=runner-token-service
OIDC_JWKS_URL=https://auth.example.com/.well-known/jwks.json
ENABLE_OIDC_AUTH=true

DATABASE_URL=sqlite:///./runner_service.db
LOG_LEVEL=INFO
EOF

# Place GitHub App private key
cp ~/Downloads/my-app.private-key.pem ./github-app-private-key.pem
chmod 600 github-app-private-key.pem
```

### 3. Initialize Database

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python -m app.cli init-db
```

### 4. Run Service

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## JIT with Podman

Running JIT-provisioned runners with Podman is ideal for macOS development where the GitHub runner binary requires Linux.

### Basic Podman JIT Flow

```bash
# 1. Provision runner using JIT
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/runners/jit \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "podman-runner",
    "labels": ["podman", "linux"]
  }')

# 2. Extract JIT config
JIT_CONFIG=$(echo "$RESPONSE" | jq -r '.encoded_jit_config')
RUNNER_NAME=$(echo "$RESPONSE" | jq -r '.runner_name')

echo "Starting runner: $RUNNER_NAME"

# 3. Run with Podman (no config.sh needed!)
podman run -it --rm \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$JIT_CONFIG"
```

### Podman with Resource Limits

```bash
# Run with CPU and memory limits
podman run -it --rm \
  --cpus=2 \
  --memory=4g \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$JIT_CONFIG"
```

### Podman in Background

```bash
# Run detached
CONTAINER_ID=$(podman run -d --rm \
  --name "$RUNNER_NAME" \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$JIT_CONFIG")

echo "Runner started in container: $CONTAINER_ID"

# View logs
podman logs -f "$RUNNER_NAME"

# Stop when done
podman stop "$RUNNER_NAME"
```

### macOS Notes

- Make sure `podman machine` is running: `podman machine start`
- The container runs inside a Linux VM managed by Podman
- JIT runners will automatically terminate after one job (ephemeral)

## Legacy: Registration Token Workflow

> **Note:** JIT provisioning is recommended for production use. Registration tokens allow clients to bypass label and ephemeral settings.

### Complete Runner Provisioning Flow

```bash
# 1. Get OIDC token (example using a mock service)
OIDC_TOKEN="your-oidc-token-here"

# 2. Provision runner
curl -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Authorization: Bearer $OIDC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "gpu-worker-001",
    "labels": ["gpu", "ubuntu-22.04", "cuda-11.8"],
    "ephemeral": true
  }' | jq .

# Response:
# {
#   "runner_id": "abc123...",
#   "runner_name": "gpu-worker-001",
#   "registration_token": "AABBCCDD...",
#   "expires_at": "2026-01-16T15:30:00Z",
#   "github_url": "https://github.com/my-org",
#   "runner_group_id": 1,
#   "ephemeral": true,
#   "labels": ["gpu", "ubuntu-22.04", "cuda-11.8"],
#   "configuration_command": "./config.sh --url https://github.com/my-org --token AABBCCDD... --name gpu-worker-001 --labels gpu,ubuntu-22.04,cuda-11.8 --ephemeral"
# }

# 3. Save the token and configuration command
RUNNER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Authorization: Bearer $OIDC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "gpu-worker-001",
    "labels": ["gpu"],
    "ephemeral": true
  }' | jq -r .registration_token)

# 4. Configure the runner on target machine
# (Third party runs this on their infrastructure)
cd actions-runner
./config.sh \
  --url https://github.com/my-org \
  --token $RUNNER_TOKEN \
  --name gpu-worker-001 \
  --labels gpu,ubuntu-22.04 \
  --ephemeral

# 5. Start the runner
./run.sh

# 6. Sync runner status with GitHub
# Note: After starting the runner, it will be in "pending" state until synced
python -m app.cli sync-github

# 7. Check status (should now be "active" or "offline" depending on availability)
curl http://localhost:8000/api/v1/runners/gpu-worker-001 \
  -H "Authorization: Bearer $OIDC_TOKEN" | jq .
```

## JIT Provisioning

JIT (Just-In-Time) provisioning offers stronger security guarantees than registration tokens:
- **Labels enforced server-side**: Labels cannot be modified by the client
- **Ephemeral mode always enabled**: Runners auto-delete after one job
- **No config step**: Run directly with `./run.sh --jitconfig <config>`

### JIT Provisioning Flow

```bash
# 1. Get OIDC token
OIDC_TOKEN="your-oidc-token-here"

# 2. Provision runner using JIT endpoint
curl -X POST http://localhost:8000/api/v1/runners/jit \
  -H "Authorization: Bearer $OIDC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "secure-worker-001",
    "labels": ["gpu", "ubuntu-22.04"],
    "runner_group_id": 1,
    "work_folder": "_work"
  }' | jq .

# Response:
# {
#   "runner_id": "abc123...",
#   "runner_name": "secure-worker-001",
#   "encoded_jit_config": "eyJhbGciOiJIUzI1NiIsInR5...",
#   "labels": ["self-hosted", "linux", "x64", "gpu", "ubuntu-22.04"],
#   "expires_at": "2026-01-16T16:30:00Z",
#   "run_command": "./run.sh --jitconfig eyJhbGciOiJIUzI1NiIsInR5..."
# }

# 3. Extract the JIT config
JIT_CONFIG=$(curl -s -X POST http://localhost:8000/api/v1/runners/jit \
  -H "Authorization: Bearer $OIDC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "secure-worker-001",
    "labels": ["gpu"]
  }' | jq -r .encoded_jit_config)

# 4. Start the runner directly (no config.sh needed!)
# (Third party runs this on their infrastructure)
cd actions-runner
./run.sh --jitconfig $JIT_CONFIG
```

### JIT with Name Prefix

```bash
# Use runner_name_prefix to auto-generate unique names
curl -X POST http://localhost:8000/api/v1/runners/jit \
  -H "Authorization: Bearer $OIDC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "gpu-worker",
    "labels": ["gpu", "cuda-12"]
  }' | jq .

# Response will have a generated name like "gpu-worker-a1b2c3"
```

### JIT vs Registration Token Comparison

| Feature | Registration Token | JIT Configuration |
|---------|-------------------|-------------------|
| Endpoint | POST /api/v1/runners/provision | POST /api/v1/runners/jit |
| Client runs | `./config.sh` then `./run.sh` | `./run.sh --jitconfig` only |
| Label enforcement | Client can ignore | Server-side enforced |
| Ephemeral mode | Client choice | Always enabled |
| Use case | Legacy, full control | Production, security |

## API Examples

### Provision Multiple Runners

```bash
#!/bin/bash
OIDC_TOKEN="your-token"

# Provision 3 runners
for i in {1..3}; do
  echo "Provisioning runner $i..."

  curl -s -X POST http://localhost:8000/api/v1/runners/provision \
    -H "Authorization: Bearer $OIDC_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"runner_name\": \"worker-$(printf %03d $i)\",
      \"labels\": [\"worker\", \"batch-$i\"],
      \"ephemeral\": true
    }" | jq -r '.configuration_command' > runner-$i-config.sh

  echo "Configuration saved to runner-$i-config.sh"
done
```

### List All Your Runners

```bash
OIDC_TOKEN="your-token"

curl http://localhost:8000/api/v1/runners \
  -H "Authorization: Bearer $OIDC_TOKEN" | jq .

# Filter by status using jq
curl -s http://localhost:8000/api/v1/runners \
  -H "Authorization: Bearer $OIDC_TOKEN" | \
  jq '.runners[] | select(.status == "active")'
```

### Refresh Runner Status

```bash
OIDC_TOKEN="your-token"
RUNNER_ID="uuid-from-provision-response"

# Sync status with GitHub
curl -X POST http://localhost:8000/api/v1/runners/$RUNNER_ID/refresh \
  -H "Authorization: Bearer $OIDC_TOKEN" | jq .
```

### Deprovision Runner

```bash
OIDC_TOKEN="your-token"
RUNNER_ID="uuid-from-provision-response"

curl -X DELETE http://localhost:8000/api/v1/runners/$RUNNER_ID \
  -H "Authorization: Bearer $OIDC_TOKEN" | jq .
```

## CLI Examples

### Initialize Database

```bash
python -m app.cli init-db
```

### List All Runners

```bash
# All runners
python -m app.cli list-runners

# Filter by status
python -m app.cli list-runners --status active

# Filter by user
python -m app.cli list-runners --user alice@example.com
```

### Cleanup Stale Runners

```bash
# Dry run (show what would be deleted)
python -m app.cli cleanup-stale-runners --hours 24 --dry-run

# Actually delete
python -m app.cli cleanup-stale-runners --hours 24
```

### Sync with GitHub

```bash
# Update all runner statuses from GitHub API
python -m app.cli sync-github
```

### Export Audit Log

```bash
# Export to JSON file
python -m app.cli export-audit-log \
  --since 2026-01-01 \
  --output audit-report.json

# Filter by event type
python -m app.cli export-audit-log \
  --event-type provision \
  --limit 50

# Filter by user
python -m app.cli export-audit-log \
  --user alice@example.com \
  --output alice-audit.json
```

## Integration Examples

### Automated JIT Runner Provisioning Script (Recommended)

```python
#!/usr/bin/env python3
"""Automated JIT runner provisioning with the Token Service."""

import requests
import subprocess
import sys
import time

TOKEN_SERVICE_URL = "http://localhost:8000"
OIDC_TOKEN = "your-oidc-token"

def get_oidc_token():
    """Get OIDC token from your auth provider."""
    # Implement your OIDC token retrieval here
    return OIDC_TOKEN

def provision_jit_runner(name_prefix, labels):
    """Provision a runner using JIT configuration."""
    headers = {
        "Authorization": f"Bearer {get_oidc_token()}",
        "Content-Type": "application/json"
    }

    payload = {
        "runner_name_prefix": name_prefix,
        "labels": labels
    }

    response = requests.post(
        f"{TOKEN_SERVICE_URL}/api/v1/runners/jit",
        headers=headers,
        json=payload
    )
    response.raise_for_status()

    return response.json()

def main():
    """Main JIT provisioning flow."""
    name_prefix = f"auto-worker"
    labels = ["automated", "python", "linux"]

    print(f"Provisioning JIT runner with prefix: {name_prefix}")

    try:
        # Get JIT configuration
        config_data = provision_jit_runner(name_prefix, labels)
        runner_name = config_data["runner_name"]
        jit_config = config_data["encoded_jit_config"]

        print(f"✓ JIT config obtained for runner: {runner_name}")
        print(f"  Labels: {config_data['labels']}")
        print(f"  Expires: {config_data['expires_at']}")

        # Start runner directly (no config.sh needed!)
        print("Starting runner...")
        subprocess.run(["./run.sh", "--jitconfig", jit_config], check=True)

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Legacy: Automated Registration Token Script

```python
#!/usr/bin/env python3
"""Automated runner provisioning with registration tokens (legacy)."""

import requests
import subprocess
import sys

TOKEN_SERVICE_URL = "http://localhost:8000"
OIDC_TOKEN = "your-oidc-token"

def get_oidc_token():
    """Get OIDC token from your auth provider."""
    return OIDC_TOKEN

def provision_runner(name, labels, ephemeral=True):
    """Provision a runner via the token service."""
    headers = {
        "Authorization": f"Bearer {get_oidc_token()}",
        "Content-Type": "application/json"
    }

    payload = {
        "runner_name": name,
        "labels": labels,
        "ephemeral": ephemeral
    }

    response = requests.post(
        f"{TOKEN_SERVICE_URL}/api/v1/runners/provision",
        headers=headers,
        json=payload
    )
    response.raise_for_status()

    return response.json()

def configure_runner(config_data):
    """Configure the runner locally."""
    token = config_data["registration_token"]
    name = config_data["runner_name"]
    url = config_data["github_url"]
    labels = ",".join(config_data["labels"])

    cmd = [
        "./config.sh",
        "--url", url,
        "--token", token,
        "--name", name,
        "--labels", labels
    ]

    if config_data["ephemeral"]:
        cmd.append("--ephemeral")

    subprocess.run(cmd, check=True)
    print(f"✓ Runner {name} configured successfully")

def main():
    """Main provisioning flow."""
    import time
    runner_name = f"auto-worker-{int(time.time())}"
    labels = ["automated", "python", "linux"]

    print(f"Provisioning runner: {runner_name}")

    try:
        config_data = provision_runner(runner_name, labels)
        print(f"✓ Registration token obtained (expires: {config_data['expires_at']})")
        configure_runner(config_data)
        print("Starting runner...")
        subprocess.run(["./run.sh"], check=True)

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Kubernetes Job with JIT (Recommended)

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: github-runner-jit
spec:
  template:
    spec:
      serviceAccountName: runner-provisioner
      containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        env:
        - name: TOKEN_SERVICE_URL
          value: "http://runner-token-service:8000"
        - name: RUNNER_PREFIX
          value: "k8s-runner"
        command:
        - /bin/bash
        - -c
        - |
          set -e

          # Get OIDC token (from K8s service account)
          OIDC_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)

          # Provision runner using JIT
          RESPONSE=$(curl -s -X POST $TOKEN_SERVICE_URL/api/v1/runners/jit \
            -H "Authorization: Bearer $OIDC_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
              \"runner_name_prefix\": \"$RUNNER_PREFIX\",
              \"labels\": [\"kubernetes\", \"docker\"]
            }")

          # Extract JIT config
          JIT_CONFIG=$(echo $RESPONSE | jq -r .encoded_jit_config)
          RUNNER_NAME=$(echo $RESPONSE | jq -r .runner_name)

          echo "Starting runner: $RUNNER_NAME"

          # Run directly with JIT config (no config.sh needed!)
          ./run.sh --jitconfig "$JIT_CONFIG"
      restartPolicy: Never
  backoffLimit: 3
```

### Legacy: Kubernetes Job with Registration Token

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: github-runner-legacy
spec:
  template:
    spec:
      serviceAccountName: runner-provisioner
      containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        env:
        - name: TOKEN_SERVICE_URL
          value: "http://runner-token-service:8000"
        - name: RUNNER_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        command:
        - /bin/bash
        - -c
        - |
          set -e

          OIDC_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)

          RESPONSE=$(curl -s -X POST $TOKEN_SERVICE_URL/api/v1/runners/provision \
            -H "Authorization: Bearer $OIDC_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
              \"runner_name\": \"$RUNNER_NAME\",
              \"labels\": [\"kubernetes\", \"ephemeral\"],
              \"ephemeral\": true
            }")

          REG_TOKEN=$(echo $RESPONSE | jq -r .registration_token)
          GITHUB_URL=$(echo $RESPONSE | jq -r .github_url)

          ./config.sh \
            --url $GITHUB_URL \
            --token $REG_TOKEN \
            --name $RUNNER_NAME \
            --labels kubernetes,ephemeral \
            --ephemeral

          ./run.sh
      restartPolicy: Never
  backoffLimit: 3
```

### Terraform Module

```hcl
# Provision runner via Token Service
resource "null_resource" "provision_runner" {
  provisioner "local-exec" {
    command = <<-EOT
      curl -X POST ${var.token_service_url}/api/v1/runners/provision \
        -H "Authorization: Bearer ${var.oidc_token}" \
        -H "Content-Type: application/json" \
        -d '{
          "runner_name": "${var.runner_name}",
          "labels": ${jsonencode(var.labels)},
          "ephemeral": ${var.ephemeral}
        }' | jq -r .registration_token > /tmp/runner-token
    EOT
  }
}

# Configure EC2 instance as runner
resource "aws_instance" "github_runner" {
  ami           = var.ami_id
  instance_type = var.instance_type

  user_data = <<-EOT
    #!/bin/bash
    cd /home/ubuntu/actions-runner

    # Get token from provisioning step
    TOKEN=$(cat /tmp/runner-token)

    ./config.sh \
      --url https://github.com/${var.github_org} \
      --token $TOKEN \
      --name ${var.runner_name} \
      --labels ${join(",", var.labels)} \
      --ephemeral

    ./run.sh
  EOT

  depends_on = [null_resource.provision_runner]
}
```

## Testing Without OIDC

For development/testing, disable OIDC authentication:

```bash
# In .env
ENABLE_OIDC_AUTH=false

# Restart service
uvicorn app.main:app --reload
```

Then make requests without the Authorization header:

```bash
curl -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "test-runner",
    "labels": ["test"],
    "ephemeral": true
  }'
```
