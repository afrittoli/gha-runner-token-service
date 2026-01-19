# Development Environment Setup

This guide covers setting up a complete development environment for the Runner Token Service, including a local OIDC provider using Auth0.

## Prerequisites

- Python 3.11+
- Git
- A GitHub account with an organization (or create one for testing)
- An Auth0 account (free tier is sufficient)

## Quick Setup

```bash
# Clone the repository
git clone https://github.com/your-org/runner-token-service.git
cd runner-token-service

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy example configuration
cp .env.example .env
```

## 1. GitHub App Setup

### Create a GitHub App

1. Go to your GitHub organization: `https://github.com/organizations/YOUR-ORG/settings/apps`
2. Click "New GitHub App"
3. Configure the app:

   | Field | Value |
   |-------|-------|
   | **GitHub App name** | Runner Token Service Dev |
   | **Homepage URL** | `http://localhost:8000` |
   | **Webhook** | Uncheck "Active" (not needed) |

4. Set permissions:

   | Permission | Access |
   |------------|--------|
   | **Organization permissions > Self-hosted runners** | Read and write |

5. Click "Create GitHub App"

### Generate Private Key

1. On the app settings page, scroll to "Private keys"
2. Click "Generate a private key"
3. Save the downloaded `.pem` file to your project directory:

   ```bash
   mv ~/Downloads/your-app.*.private-key.pem ./github-app-private-key.pem
   chmod 600 github-app-private-key.pem
   ```

### Install the App

1. Click "Install App" in the left sidebar
2. Select your organization
3. Click "Install"
4. Note the Installation ID from the URL: `https://github.com/organizations/YOUR-ORG/settings/installations/INSTALLATION_ID`

### Update Configuration

Edit `.env` with your GitHub App details:

```bash
GITHUB_APP_ID=123456                    # From app settings page
GITHUB_APP_INSTALLATION_ID=12345678     # From installation URL
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_ORG=your-organization
```

## 2. Auth0 OIDC Setup

Auth0 provides a free tier that's perfect for development and testing.

### Create Auth0 Account and Tenant

1. Go to [auth0.com](https://auth0.com) and sign up
2. Create a new tenant (e.g., `runner-token-dev`)

### Create an API

1. Go to **Applications > APIs** in the Auth0 dashboard
2. Click "Create API"
3. Configure:

   | Field | Value |
   |-------|-------|
   | **Name** | Runner Token Service |
   | **Identifier** | `runner-token-service` |
   | **Signing Algorithm** | RS256 |

4. Click "Create"

### Create a Machine-to-Machine Application

This is for automated/service authentication:

1. Go to **Applications > Applications**
2. Click "Create Application"
3. Configure:

   | Field | Value |
   |-------|-------|
   | **Name** | Runner Token Service M2M |
   | **Application Type** | Machine to Machine Applications |

4. Click "Create"
5. Select the "Runner Token Service" API you created
6. Click "Authorize" (no custom scopes are required - the service uses the token's `sub` claim for identity)

Note down:
- **Domain**: `your-tenant.auth0.com`
- **Client ID**: (from application settings)
- **Client Secret**: (from application settings)

### Create Test Users

1. Go to **User Management > Users**
2. Click "Create User"
3. Create test users:

   | Email | Password | Description |
   |-------|----------|-------------|
   | `admin@example.com` | (strong password) | Admin user for testing |
   | `developer@example.com` | (strong password) | Regular developer user |

### Create a Regular Web Application (for user login)

1. Go to **Applications > Applications**
2. Click "Create Application"
3. Configure:

   | Field | Value |
   |-------|-------|
   | **Name** | Runner Token Service Web |
   | **Application Type** | Regular Web Applications |

4. Click "Create"
5. In Settings, configure:

   | Field | Value |
   |-------|-------|
   | **Allowed Callback URLs** | `http://localhost:8000/callback` |
   | **Allowed Logout URLs** | `http://localhost:8000` |
   | **Allowed Web Origins** | `http://localhost:8000` |

6. Save Changes

### Update Configuration

Edit `.env` with your Auth0 details:

```bash
ENABLE_OIDC_AUTH=true
OIDC_ISSUER=https://your-tenant.auth0.com/
OIDC_AUDIENCE=runner-token-service
OIDC_JWKS_URL=https://your-tenant.auth0.com/.well-known/jwks.json
```

## 3. Database Setup

The service uses SQLite by default for development:

```bash
# Initialize the database
python -m app.cli init-db
```

For PostgreSQL (optional, for production-like setup):

```bash
# Install PostgreSQL driver
pip install psycopg2-binary

# Update .env
DATABASE_URL=postgresql://user:password@localhost:5432/runner_service
```

## 4. Running the Service

### Development Mode (with auto-reload)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Debug Mode

```bash
uvicorn app.main:app --reload --log-level debug
```

The service is now available at:
- API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- API Docs (ReDoc): `http://localhost:8000/redoc`

## 5. Testing with OIDC

### Get an Access Token (M2M)

Use the Machine-to-Machine application to get a token:

```bash
# Set your Auth0 credentials
AUTH0_DOMAIN="your-tenant.auth0.com"
AUTH0_CLIENT_ID="your-m2m-client-id"
AUTH0_CLIENT_SECRET="your-m2m-client-secret"
AUTH0_AUDIENCE="runner-token-service"

# Get access token
TOKEN_RESPONSE=$(curl -s --request POST \
  --url "https://${AUTH0_DOMAIN}/oauth/token" \
  --header 'content-type: application/json' \
  --data "{
    \"client_id\": \"${AUTH0_CLIENT_ID}\",
    \"client_secret\": \"${AUTH0_CLIENT_SECRET}\",
    \"audience\": \"${AUTH0_AUDIENCE}\",
    \"grant_type\": \"client_credentials\"
  }")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')
echo "Access Token: ${ACCESS_TOKEN:0:50}..."
```

### Get an Access Token (User Login via Resource Owner Password)

For testing with user credentials (enable "Password" grant in Auth0 first):

1. Go to **Applications > Applications > Runner Token Service Web > Settings**
2. Scroll to "Advanced Settings" > "Grant Types"
3. Enable "Password"
4. Save

```bash
# Get user access token
TOKEN_RESPONSE=$(curl -s --request POST \
  --url "https://${AUTH0_DOMAIN}/oauth/token" \
  --header 'content-type: application/json' \
  --data "{
    \"client_id\": \"${AUTH0_CLIENT_ID}\",
    \"client_secret\": \"${AUTH0_CLIENT_SECRET}\",
    \"audience\": \"${AUTH0_AUDIENCE}\",
    \"grant_type\": \"password\",
    \"username\": \"developer@example.com\",
    \"password\": \"your-password\"
  }")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')
```

### Make Authenticated API Calls

```bash
# Provision a runner with authentication
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "dev-runner",
    "labels": ["dev", "test"],
    "ephemeral": true
  }')
echo "$RESPONSE" | jq .
```

### List Runners

```bash
curl -s http://localhost:8000/api/v1/runners \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | jq .
```

## 6. Development Without OIDC

For quick local testing without setting up OIDC:

```bash
# In .env
ENABLE_OIDC_AUTH=false
```

This disables authentication and uses a mock user identity. **Never use this in production.**

## 7. CLI Commands

The service includes a CLI for administrative tasks:

```bash
# Initialize database
python -m app.cli init-db

# List all runners
python -m app.cli list-runners

# Sync runner status with GitHub
python -m app.cli sync-github

# Cleanup stale runners (dry run)
python -m app.cli cleanup-stale-runners --hours 24 --dry-run

# Cleanup stale runners (actually delete)
python -m app.cli cleanup-stale-runners --hours 24

# Export audit log
python -m app.cli export-audit-log --output audit.json
```

## 8. Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## 9. Project Structure

```
runner-token-service/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── runners.py      # API endpoints
│   ├── auth/
│   │   └── dependencies.py     # OIDC authentication
│   ├── github/
│   │   ├── app_auth.py         # GitHub App authentication
│   │   └── client.py           # GitHub API client
│   ├── services/
│   │   ├── runner_service.py   # Runner management logic
│   │   └── label_policy_service.py  # Label policy enforcement
│   ├── cli.py                  # CLI commands
│   ├── config.py               # Configuration
│   ├── main.py                 # FastAPI application
│   ├── models.py               # Database models
│   └── schemas.py              # Pydantic schemas
├── .env.example                # Example configuration
├── requirements.txt            # Python dependencies
├── QUICKSTART.md              # Quick start guide
├── DEVELOPMENT.md             # This file
└── README.md                  # Project overview
```

## 10. Troubleshooting

### "Failed to generate GitHub token"

- Verify `GITHUB_APP_ID` is correct
- Verify `GITHUB_APP_INSTALLATION_ID` is correct
- Check the private key file exists and is readable
- Ensure the GitHub App is installed to your organization
- Verify the App has "Self-hosted runners: Read & Write" permission

### "Invalid token" or "Unauthorized"

- Check `OIDC_ISSUER` matches your Auth0 domain (include trailing slash)
- Verify `OIDC_AUDIENCE` matches the API identifier in Auth0
- Ensure the token hasn't expired (default is 24 hours)
- Check `ENABLE_OIDC_AUTH=true` in your `.env`

### Database errors

```bash
# Reset the database
rm runner_service.db
python -m app.cli init-db
```

### Runner not appearing in GitHub

- Wait 30-60 seconds after provisioning
- Check the registration token hasn't expired (1 hour limit)
- Verify the runner name is unique
- Check the runner was configured with the correct token and URL

## 11. Auth0 Free Tier Limits

The Auth0 free tier includes:
- 7,500 monthly active users
- Unlimited Machine-to-Machine tokens
- Social connections
- Custom domains (limited)

This is more than sufficient for development and small-scale testing.

## 12. Security Notes for Development

- Never commit `.env` or private keys to version control
- Use different Auth0 tenants for development and production
- Rotate secrets regularly
- The SQLite database stores sensitive tokens temporarily - don't share it
- When `ENABLE_OIDC_AUTH=false`, anyone can access the API
