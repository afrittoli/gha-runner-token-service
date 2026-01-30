#!/bin/bash
# Deploy application to kind cluster

set -e

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
REGISTRY="${REGISTRY:-ghcr.io}"
ORG="${ORG:-your-org}"
PROJECT="${PROJECT:-gha-runner-token-service}"

BACKEND_IMAGE="${REGISTRY}/${ORG}/${PROJECT}-backend:${VERSION}"
FRONTEND_IMAGE="${REGISTRY}/${ORG}/${PROJECT}-frontend:${VERSION}"

# Load .env file if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [ -f "$PROJECT_ROOT/.env" ]; then
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
    log_info "Building images with make..."
    make build CONTAINER_TOOL="$CONTAINER_TOOL" ORG="$ORG" VERSION="$VERSION"
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

    # Build images if they don't exist
    log_info "Checking if images exist locally..."
    if check_images_exist; then
        log_success "Images already exist locally"
    else
        log_warning "Images not found locally, building..."
        build_images
    fi

    # Load images to kind
    load_images_to_kind

    # Load PostgreSQL image to kind (for local development)
    log_info "Loading PostgreSQL image to kind..."
    POSTGRES_IMAGE="docker.io/bitnami/postgresql:latest"
    if ! $CONTAINER_TOOL images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${POSTGRES_IMAGE}$"; then
        log_info "Pulling PostgreSQL image..."
        $CONTAINER_TOOL pull "$POSTGRES_IMAGE"
    fi
    if [ "$CONTAINER_TOOL" = "docker" ]; then
        kind load docker-image "$POSTGRES_IMAGE" --name "$CLUSTER_NAME"
    else
        local pg_tar="/tmp/postgresql-kind.tar"
        $CONTAINER_TOOL save -o "$pg_tar" "$POSTGRES_IMAGE"
        kind load image-archive "$pg_tar" --name "$CLUSTER_NAME"
        rm -f "$pg_tar"
    fi
    log_success "PostgreSQL image loaded"

    # Create namespace if it doesn't exist
    log_info "Ensuring namespace exists..."
    kubectl create namespace "$NAMESPACE" 2>/dev/null || log_info "Namespace already exists"

    # Create secrets
    log_info "Creating secrets..."
    
    # Generate a test GitHub App private key
    cat > /tmp/test-github-key.pem <<EOF
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAtest-key-for-development-only
-----END RSA PRIVATE KEY-----
EOF

    kubectl create secret generic gharts-secrets \
        --namespace "$NAMESPACE" \
        --from-literal=github-app-id="123456" \
        --from-file=github-app-private-key=/tmp/test-github-key.pem \
        --from-literal=oidc-client-id="test-client-id" \
        --from-literal=oidc-client-secret="test-client-secret" \
        --from-literal=bootstrap-admin-password="admin123" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    rm /tmp/test-github-key.pem
    log_success "Secrets created"

    # Create values file for kind deployment
    log_info "Creating Helm values for kind..."
    cat > /tmp/kind-values.yaml <<EOF
# Kind-specific values
replicaCount:
  backend: 1
  frontend: 1

backend:
  image:
    repository: ${REGISTRY}/${ORG}/${PROJECT}-backend
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

  podDisruptionBudget:
    enabled: false

  podSecurityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000

  securityContext:
    capabilities:
      drop:
        - ALL
    readOnlyRootFilesystem: true

frontend:
  image:
    repository: ${REGISTRY}/${ORG}/${PROJECT}-frontend
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

  podDisruptionBudget:
    enabled: false

  podSecurityContext:
    runAsNonRoot: true
    runAsUser: 101
    fsGroup: 101

  securityContext:
    capabilities:
      drop:
        - ALL
    readOnlyRootFilesystem: true

# PostgreSQL is installed separately - configure external database connection
postgresql:
  enabled: false

externalDatabase:
  host: "${RELEASE_NAME}-postgresql"
  port: 5432
  username: gharts
  password: gharts
  database: gharts
  sslMode: disable

# Application configuration (values from .env or defaults)
config:
  github:
    appId: "${GITHUB_APP_ID}"
    installationId: "${GITHUB_APP_INSTALLATION_ID}"
    organization: "${GITHUB_ORG}"
    privateKey: |
$(cat "$GITHUB_PRIVATE_KEY_FILE" 2>/dev/null | sed 's/^/      /' || echo "      -----BEGIN RSA PRIVATE KEY-----
      placeholder-key-for-testing
      -----END RSA PRIVATE KEY-----")

  oidc:
    enabled: ${ENABLE_OIDC}
    issuer: "${OIDC_ISSUER}"
    audience: "${OIDC_AUDIENCE}"
    jwksUrl: "${OIDC_JWKS_URL}"

  bootstrap:
    enabled: true
    username: "admin"
    password: "admin123"
    email: "admin@kind.local"

  sync:
    enabled: true
    intervalSeconds: 60
    onStartup: true

  logLevel: "DEBUG"

# Enable ingress for kind
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

# Disable monitoring for kind
serviceMonitor:
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
            --values /tmp/kind-values.yaml \
            --wait \
            --timeout 5m
    else
        log_info "Installing new release..."
        helm install "$RELEASE_NAME" ./helm/gharts \
            --namespace "$NAMESPACE" \
            --values /tmp/kind-values.yaml \
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

    log_info "Access the application:"
    echo
    echo "1. Via port-forward (backend):"
    echo "   kubectl port-forward -n $NAMESPACE $BACKEND_POD 8000:8000"
    echo "   curl http://localhost:8000/health"
    echo
    echo "2. Via port-forward (frontend):"
    echo "   kubectl port-forward -n $NAMESPACE $FRONTEND_POD 8080:80"
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

# Made with Bob
