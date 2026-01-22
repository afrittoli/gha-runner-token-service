#!/bin/zsh

# The oidc script facilitates obtaining an OIDC token from Auth0
# It opens a browser for user login, captures the authorization code,
# and exchanges it for an access token.

# The following environment variables must be set for this script to work:
# AUTH0_DOMAIN, AUTH0_AUDIENCE, AUTH0_WEB_CLIENT_ID

# Source this script to use this function, or store in your .zshrc

get_oidc_token() {
  local AUDIENCE="$AUTH0_AUDIENCE"
  local CLIENT_ID="$AUTH0_NATIVE_CLIENT_ID"
  local DEVICE_AUTH_ENDPOINT="https://$AUTH0_DOMAIN/oauth/device/code"
  local TOKEN_ENDPOINT="https://$AUTH0_DOMAIN/oauth/token"
  local REDIRECT_URI="http://localhost:$NC_PORT"

  # Request code from Auth0
  RESPONSE=$(curl -s --request POST \
    --url "$DEVICE_AUTH_ENDPOINT" \
    --data "client_id=${CLIENT_ID}&audience=$AUDIENCE&scope=openid profile email")

  # Extract values from response
  USER_CODE=$(echo $RESPONSE | jq -r .user_code)
  AUTH_URL=$(echo $RESPONSE | jq -r .verification_uri)
  DEVICE_CODE=$(echo $RESPONSE | jq -r .device_code)
  INTERVAL=$(echo $RESPONSE | jq -r .interval)

  # Prompt user to complete authentication
  echo "Enter this code on the browser: $USER_CODE" >&2
  open -n -a "Google Chrome" --args --incognito "${AUTH_URL}"

  while true; do
    TOKEN_RESPONSE=$(curl -s --request POST \
      --url "$TOKEN_ENDPOINT" \
      --data "grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=${DEVICE_CODE}&client_id=${CLIENT_ID}")

    # Check if we got an access token
    ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token // empty')
    if [[ -n "$ACCESS_TOKEN" ]]; then
      echo "Successfully authenticated!" >&2
      break
    fi

    sleep $INTERVAL
  done

  echo "$ACCESS_TOKEN"
}
