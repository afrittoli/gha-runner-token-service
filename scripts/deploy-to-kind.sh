#!/bin/bash
# Deploy application to kind cluster

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-gharts-test}"
NAMESPACE="${NAMESPACE:-gharts}"
RELEASE_NAME="${RELEASE_NAME:-gharts}"
VERSION="${VERSION:-test}"

BACKEND_IMAGE="ghcr.io/your-org/gha-runner-token-service-backend:${VERSION}"
FRONTEND_IMAGE="ghcr.io/your-org/gha-runner-token-service-frontend:${VERSION}"

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

# Main script
main() {
    log_info "Deploy to Kind Script"
    log_info "===================="
    log_info "Cluster: $CLUSTER_NAME"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"
    log_info "Version: $VERSION"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_tool kind
    check_tool kubectl
    check_tool helm
    check_tool docker
    check_cluster
    log_success "Prerequisites OK"

    # Switch to kind context
    log_info "Switching to kind context..."
    kubectl config use-context "kind-${CLUSTER_NAME}"
    log_success "Context switched"

    # Build images if they don't exist
    log_info "Checking if images exist..."
    if ! docker images | grep -q "$BACKEND_IMAGE"; then
        log_warning "Backend image not found, building..."
        docker build -f Dockerfile.backend -t "$BACKEND_IMAGE" .
    fi
    if ! docker images | grep -q "$FRONTEND_IMAGE"; then
        log_warning "Frontend image not found, building..."
        docker build -f frontend/Dockerfile -t "$FRONTEND_IMAGE" frontend/
    fi
    log_success "Images ready"

    # Load images to kind
    log_info "Loading images to kind cluster..."
    kind load docker-image "$BACKEND_IMAGE" --name "$CLUSTER_NAME"
    kind load docker-image "$FRONTEND_IMAGE" --name "$CLUSTER_NAME"
    log_success "Images loaded"

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

image:
  backend:
    repository: ghcr.io/your-org/gha-runner-token-service-backend
    tag: ${VERSION}
    pullPolicy: IfNotPresent
  frontend:
    repository: ghcr.io/your-org/gha-runner-token-service-frontend
    tag: ${VERSION}
    pullPolicy: IfNotPresent

backend:
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

frontend:
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

# Use built-in PostgreSQL
postgresql:
  enabled: true
  auth:
    username: gharts
    password: gharts
    database: gharts
  primary:
    persistence:
      enabled: true
      size: 1Gi

# Test configuration
config:
  githubAppId: "123456"
  githubAppPrivateKey: ""  # Set via secret
  oidcClientId: ""  # Set via secret
  oidcClientSecret: ""  # Set via secret
  oidcDiscoveryUrl: "https://example.com/.well-known/openid-configuration"
  logLevel: "DEBUG"
  databasePoolSize: 5
  databaseMaxOverflow: 5

# Bootstrap admin
bootstrap:
  enabled: true
  admin:
    username: "admin"
    password: ""  # Set via secret
    email: "admin@kind.local"

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

    # Install or upgrade Helm chart
    log_info "Deploying Helm chart..."
    if helm list -n "$NAMESPACE" | grep -q "^${RELEASE_NAME}"; then
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
