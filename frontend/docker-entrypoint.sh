#!/bin/sh
set -e

echo "Generating runtime configuration..."

# Set defaults for optional environment variables
export API_BASE_URL="${API_BASE_URL:-}"
export REFETCH_INTERVAL="${REFETCH_INTERVAL:-30000}"

# Validate required environment variables
if [ -z "$OIDC_AUTHORITY" ]; then
  echo "ERROR: OIDC_AUTHORITY environment variable is required"
  exit 1
fi

if [ -z "$OIDC_CLIENT_ID" ]; then
  echo "ERROR: OIDC_CLIENT_ID environment variable is required"
  exit 1
fi

if [ -z "$OIDC_AUDIENCE" ]; then
  echo "ERROR: OIDC_AUDIENCE environment variable is required"
  exit 1
fi

if [ -z "$OIDC_REDIRECT_URI" ]; then
  echo "ERROR: OIDC_REDIRECT_URI environment variable is required"
  exit 1
fi

if [ -z "$OIDC_POST_LOGOUT_REDIRECT_URI" ]; then
  echo "ERROR: OIDC_POST_LOGOUT_REDIRECT_URI environment variable is required"
  exit 1
fi

# Generate config.js from template with environment variable substitution
envsubst < /etc/nginx/config.template.js \
  > /usr/share/nginx/html/config.js

echo "Runtime configuration generated successfully"
echo "OIDC Authority: $OIDC_AUTHORITY"
echo "OIDC Audience: $OIDC_AUDIENCE"
echo "API Base URL: ${API_BASE_URL:-<same-origin>}"

# Execute the main command (nginx)
exec "$@"
