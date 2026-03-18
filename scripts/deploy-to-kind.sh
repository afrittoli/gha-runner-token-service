#!/bin/bash
# Deploy application to kind cluster

set -e

# Temp file for Helm values — cleaned up on exit
KIND_VALUES_FILE="$(mktemp /tmp/kind-values.XXXXXX.yaml)"
trap 'rm -f "$KIND_VALUES_FILE"' EXIT

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - these should match Makefile defaults
CLUSTER_NAME="${CLUSTER_NAME:-gharts-test}"
NAMESPACE="${NAMESPACE:-gharts}"
RELEASE_NAME="${RELEASE_NAME:-gharts}"
VERSION="${VERSION:-latest}"
CONTAINER_TOOL="${CONTAINER_TOOL:-podman}"
PROJECT="${PROJECT:-gha-runner-token-service}"

# Use localhost/ prefix to make clear these are local-only images (never pushed to a registry)
BACKEND_IMAGE="localhost/${PROJECT}-backend:${VERSION}"
FRONTEND_IMAGE="localhost/${PROJECT}-frontend:${VERSION}"

# Load .env file if present — values here take precedence over the parent environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [ -f "$PROJECT_ROOT/.env" ]; then
    # Unset known variables so parent-shell exports cannot override .env values
    unset OIDC_AUDIENCE OIDC_ISSUER OIDC_JWKS_URL ENABLE_OIDC_AUTH
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
fi

# GitHub/OIDC configuration (can be overridden by .env or environment)
GITHUB_APP_ID="${GITHUB_APP_ID:-123456}"
GITHUB_APP_INSTALLATION_ID="${GITHUB_APP_INSTALLATION_ID:-12345678}"
GITHUB_ORG="${GITHUB_ORG:-test-org}"
GITHUB_PRIVATE_KEY_FILE="${GITHUB_APP_PRIVATE_KEY_PATH:-$PROJECT_ROOT/github-app-private-key.pem}"
ENABLE_OIDC="${ENABLE_OIDC_AUTH:-false}"
OIDC_ISSUER="${OIDC_ISSUER:-https://placeholder.invalid}"
OIDC_AUDIENCE="${OIDC_AUDIENCE:-gharts}"
OIDC_JWKS_URL="${OIDC_JWKS_URL:-https://placeholder.invalid/.well-known/jwks.json}"

# M2M team credentials configuration
TEAM_CREDENTIALS_ENABLED="${TEAM_CREDENTIALS_ENABLED:-true}"
TEAM_CREDENTIALS_CLAIM="${TEAM_CREDENTIALS_CLAIM:-team}"
TEAM_CREDENTIALS_REQUIRE_IN_DB="${TEAM_CREDENTIALS_REQUIRE_IN_DB:-true}"

# Frontend OIDC configuration — audience and authority come from OIDC_AUDIENCE / OIDC_ISSUER above
# VITE_OIDC_CLIENT_ID overrides the Auth0 SPA client ID stored in the k8s Secret
FRONTEND_OIDC_CLIENT_ID="${VITE_OIDC_CLIENT_ID:-kind-test-client-id}"
# For kind, we use localhost:8080 (port-forward to frontend service)
FRONTEND_OIDC_REDIRECT_URI="${VITE_OIDC_REDIRECT_URI:-http://localhost:8080/app/callback}"
FRONTEND_OIDC_POST_LOGOUT_REDIRECT_URI="${VITE_OIDC_POST_LOGOUT_REDIRECT_URI:-http://localhost:8080/app}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_tool() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 not found. Please install it first."
        exit 1
    fi
}

check_cluster() {
    if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        log_error "Cluster '$CLUSTER_NAME' not found"
        log_info "Run './scripts/setup-kind-cluster.sh' first"
        exit 1
    fi
}

check_images_exist() {
    # Check if images exist locally
    if ! $CONTAINER_TOOL images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${BACKEND_IMAGE}$"; then
        return 1
    fi
    if ! $CONTAINER_TOOL images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${FRONTEND_IMAGE}$"; then
        return 1
    fi
    return 0
}

build_images() {
    log_info "Building images..."

    # Build backend
    log_info "Building backend image..."
    $CONTAINER_TOOL build -f "$PROJECT_ROOT/Dockerfile" -t "$BACKEND_IMAGE" "$PROJECT_ROOT"

    # Build frontend (generic build, no build-time config)
    log_info "Building frontend image (generic, runtime-configured)..."
    $CONTAINER_TOOL build -t "$FRONTEND_IMAGE" "$PROJECT_ROOT/frontend"

    log_success "Images built"
}

load_images_to_kind() {
    log_info "Loading images to kind cluster..."

    if [ "$CONTAINER_TOOL" = "docker" ]; then
        # Docker can use kind load docker-image directly
        kind load docker-image "$BACKEND_IMAGE" --name "$CLUSTER_NAME"
        kind load docker-image "$FRONTEND_IMAGE" --name "$CLUSTER_NAME"
    else
        # Podman requires save/load approach
        log_info "Using save/load approach for $CONTAINER_TOOL..."
        local backend_tar="/tmp/gharts-backend-${VERSION}.tar"
        local frontend_tar="/tmp/gharts-frontend-${VERSION}.tar"

        $CONTAINER_TOOL save -o "$backend_tar" "$BACKEND_IMAGE"
        $CONTAINER_TOOL save -o "$frontend_tar" "$FRONTEND_IMAGE"

        kind load image-archive "$backend_tar" --name "$CLUSTER_NAME"
        kind load image-archive "$frontend_tar" --name "$CLUSTER_NAME"

        rm -f "$backend_tar" "$frontend_tar"
    fi
    log_success "Images loaded to kind"
}

# Main script
main() {
    log_info "Deploy to Kind Script"
    log_info "===================="
    log_info "Cluster: $CLUSTER_NAME"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"
    log_info "Version: $VERSION"
    log_info "Container tool: $CONTAINER_TOOL"
    log_info "Backend image: $BACKEND_IMAGE"
    log_info "Frontend image: $FRONTEND_IMAGE"
    log_info "OIDC Authority: $OIDC_ISSUER"
    log_info "OIDC Audience: $OIDC_AUDIENCE"
    log_info "Frontend OIDC Redirect URI: $FRONTEND_OIDC_REDIRECT_URI"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_tool kind
    check_tool kubectl
    check_tool helm
    check_tool "$CONTAINER_TOOL"
    check_cluster
    log_success "Prerequisites OK"

    # Switch to kind context
    log_info "Switching to kind context..."
    kubectl config use-context "kind-${CLUSTER_NAME}"
    log_success "Context switched"

    # Always rebuild images to pick up latest code changes
    build_images

    # Load images to kind
    load_images_to_kind

    # Create namespace if it doesn't exist
    log_info "Ensuring namespace exists..."
    kubectl create namespace "$NAMESPACE" 2>/dev/null || log_info "Namespace already exists"

    # Create/update k8s Secret for GitHub App private key
    log_info "Creating GitHub App private key Secret..."
    if [ -f "$GITHUB_PRIVATE_KEY_FILE" ]; then
        kubectl create secret generic "${RELEASE_NAME}-github" \
            --namespace "$NAMESPACE" \
            --from-file=private-key.pem="$GITHUB_PRIVATE_KEY_FILE" \
            --dry-run=client -o yaml | kubectl apply -f -
        log_success "GitHub App private key Secret created/updated"
    else
        log_warning "GitHub App private key file not found: $GITHUB_PRIVATE_KEY_FILE"
        log_warning "Creating placeholder Secret — backend GitHub calls will fail"
        kubectl create secret generic "${RELEASE_NAME}-github" \
            --namespace "$NAMESPACE" \
            --from-literal=private-key.pem="-----BEGIN RSA PRIVATE KEY-----
placeholder-key-for-testing
-----END RSA PRIVATE KEY-----" \
            --dry-run=client -o yaml | kubectl apply -f -
    fi

    # Create/update k8s Secret for OIDC client ID
    log_info "Creating OIDC client ID Secret..."
    kubectl create secret generic "${RELEASE_NAME}-oidc" \
        --namespace "$NAMESPACE" \
        --from-literal=oidc-client-id="${FRONTEND_OIDC_CLIENT_ID}" \
        --dry-run=client -o yaml | kubectl apply -f -
    log_success "OIDC client ID Secret created/updated"

    # Create/update k8s Secret for database URL
    log_info "Creating database URL Secret..."
    kubectl create secret generic "${RELEASE_NAME}-db" \
        --namespace "$NAMESPACE" \
        --from-literal=DATABASE_URL="postgresql://gharts:gharts@${RELEASE_NAME}-postgresql:5432/gharts?sslmode=disable" \
        --dry-run=client -o yaml | kubectl apply -f -
    log_success "Database URL Secret created/updated"

    # Create values file for kind deployment
    log_info "Creating Helm values for kind..."
    cat > "$KIND_VALUES_FILE" <<EOF
# Kind-specific values
replicaCount:
  backend: 1
  frontend: 1

backend:
  image:
    repository: localhost/${PROJECT}-backend
    tag: ${VERSION}
    pullPolicy: IfNotPresent
  autoscaling:
    enabled: false

  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 256Mi

frontend:
  image:
    repository: localhost/${PROJECT}-frontend
    tag: ${VERSION}
    pullPolicy: IfNotPresent

  autoscaling:
    enabled: false

  resources:
    limits:
      cpu: 200m
      memory: 128Mi
    requests:
      cpu: 50m
      memory: 64Mi

# ─── OIDC (shared by backend and frontend) ────────────────────────────────────
oidc:
  enabled: ${ENABLE_OIDC}
  issuer: "${OIDC_ISSUER}"
  audience: "${OIDC_AUDIENCE}"
  jwksUrl: "${OIDC_JWKS_URL}"
  redirectUri: "${FRONTEND_OIDC_REDIRECT_URI}"
  postLogoutRedirectUri: "${FRONTEND_OIDC_POST_LOGOUT_REDIRECT_URI}"
  clientIdSecret: "${RELEASE_NAME}-oidc"
  clientIdSecretKey: "oidc-client-id"

# ─── GitHub App ───────────────────────────────────────────────────────────────
github:
  organization: "${GITHUB_ORG}"
  appId: "${GITHUB_APP_ID}"
  installationId: "${GITHUB_APP_INSTALLATION_ID}"
  privateKeySecret: "${RELEASE_NAME}-github"
  privateKeySecretKey: "private-key.pem"

# ─── Database ─────────────────────────────────────────────────────────────────
# PostgreSQL is installed separately — use its URL from a pre-created Secret
postgresql:
  enabled: false

database:
  sslMode: disable
  databaseUrlSecret: "${RELEASE_NAME}-db"
  databaseUrlSecretKey: "DATABASE_URL"

# ─── Application behavior ─────────────────────────────────────────────────────
config:
  teamCredentials:
    enabled: ${TEAM_CREDENTIALS_ENABLED}
    teamClaim: "${TEAM_CREDENTIALS_CLAIM}"
    requireTeamInDB: ${TEAM_CREDENTIALS_REQUIRE_IN_DB}

  sync:
    enabled: true
    intervalSeconds: 60
    onStartup: true

  logLevel: "DEBUG"

# ─── Ingress ──────────────────────────────────────────────────────────────────
ingress:
  enabled: true
  className: "nginx"
  annotations: {}
  hosts:
    - host: gharts.local
      paths:
        - path: /
          pathType: Prefix
  tls: []

# ─── Monitoring ───────────────────────────────────────────────────────────────
monitoring:
  enabled: false
EOF

    # Install PostgreSQL for local development (not needed for production with external DB)
    log_info "Installing PostgreSQL for local development..."
    if helm list -n "$NAMESPACE" | grep -q "^${RELEASE_NAME}-postgresql"; then
        log_info "PostgreSQL already installed, upgrading..."
        helm upgrade "${RELEASE_NAME}-postgresql" oci://registry-1.docker.io/bitnamicharts/postgresql \
            --namespace "$NAMESPACE" \
            --set auth.username=gharts \
            --set auth.password=gharts \
            --set auth.database=gharts \
            --set image.tag=latest \
            --set primary.persistence.size=1Gi \
            --wait \
            --timeout 3m
    else
        log_info "Installing PostgreSQL..."
        helm install "${RELEASE_NAME}-postgresql" oci://registry-1.docker.io/bitnamicharts/postgresql \
            --namespace "$NAMESPACE" \
            --set auth.username=gharts \
            --set auth.password=gharts \
            --set auth.database=gharts \
            --set image.tag=latest \
            --set primary.persistence.size=1Gi \
            --wait \
            --timeout 3m
    fi
    log_success "PostgreSQL installed"

    # Install or upgrade Helm chart
    log_info "Deploying Helm chart..."
    if helm list -n "$NAMESPACE" | grep -q "^${RELEASE_NAME}[[:space:]]"; then
        log_info "Upgrading existing release..."
        helm upgrade "$RELEASE_NAME" ./helm/gharts \
            --namespace "$NAMESPACE" \
            --values "$KIND_VALUES_FILE" \
            --reset-values \
            --wait \
            --timeout 5m
    else
        log_info "Installing new release..."
        helm install "$RELEASE_NAME" ./helm/gharts \
            --namespace "$NAMESPACE" \
            --values "$KIND_VALUES_FILE" \
            --wait \
            --timeout 5m
    fi
    log_success "Helm chart deployed"

    # Wait for pods to be ready
    log_info "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod \
        --selector=app.kubernetes.io/name=gharts \
        --namespace "$NAMESPACE" \
        --timeout=300s || log_warning "Some pods may still be starting"
    log_success "Pods ready"

    # Run Helm tests
    log_info "Running Helm tests..."
    helm test "$RELEASE_NAME" --namespace "$NAMESPACE" || log_warning "Some tests failed"

    # Display deployment info
    echo
    log_success "Deployment complete!"
    echo
    log_info "Deployment Information:"
    echo
    echo "Pods:"
    kubectl get pods -n "$NAMESPACE"
    echo
    echo "Services:"
    kubectl get svc -n "$NAMESPACE"
    echo
    echo "Ingress:"
    kubectl get ingress -n "$NAMESPACE"
    echo

    # Get backend pod for port-forward
    BACKEND_POD=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=backend -o jsonpath='{.items[0].metadata.name}')
    FRONTEND_POD=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=frontend -o jsonpath='{.items[0].metadata.name}')

    log_info "Create admin user (REQUIRED for first login):"
    echo
    echo "   kubectl exec -n $NAMESPACE $BACKEND_POD -- python -m app.cli create-admin --email admin@kind.local"
    echo
    log_warning "You must create an admin user before you can access the dashboard!"
    echo

    log_info "Access the application:"
    echo
    echo "1. Via port-forward (backend):"
    echo "   kubectl port-forward -n $NAMESPACE $BACKEND_POD 8000:8000"
    echo "   curl http://localhost:8000/health"
    echo
    echo "2. Via port-forward (frontend):"
    echo "   kubectl port-forward -n $NAMESPACE $FRONTEND_POD 8080:8080"
    echo "   open http://localhost:8080"
    echo
    echo "3. Via ingress (requires /etc/hosts entry):"
    echo "   echo '127.0.0.1 gharts.local' | sudo tee -a /etc/hosts"
    echo "   open http://gharts.local"
    echo
    log_info "View logs:"
    echo "   kubectl logs -n $NAMESPACE -l app.kubernetes.io/component=backend -f"
    echo "   kubectl logs -n $NAMESPACE -l app.kubernetes.io/component=frontend -f"
    echo
    log_info "Uninstall:"
    echo "   helm uninstall $RELEASE_NAME -n $NAMESPACE"
    echo
    log_info "Delete cluster:"
    echo "   kind delete cluster --name $CLUSTER_NAME"
}

# Run main function
main "$@"

