#!/bin/bash
# Deploy Keycloak to kind cluster for Helm chart and realm config validation
# Uses Bitnami Keycloak Helm chart

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-gharts-test}"
NAMESPACE="${KEYCLOAK_NAMESPACE:-keycloak}"
RELEASE_NAME="${KEYCLOAK_RELEASE:-keycloak-dev}"
KEYCLOAK_PORT="${KEYCLOAK_PORT:-8080}"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

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
        echo "  Installation instructions:"
        case "$1" in
            kind)
                echo "    brew install kind  # macOS"
                echo "    # or visit: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
                ;;
            kubectl)
                echo "    brew install kubectl  # macOS"
                echo "    # or visit: https://kubernetes.io/docs/tasks/tools/"
                ;;
            helm)
                echo "    brew install helm  # macOS"
                echo "    # or visit: https://helm.sh/docs/intro/install/"
                ;;
        esac
        exit 1
    fi
}

cleanup() {
    log_info "Cleaning up..."
    helm uninstall "$RELEASE_NAME" -n "$NAMESPACE" 2>/dev/null || true
    kubectl delete namespace "$NAMESPACE" 2>/dev/null || true
}

wait_for_keycloak() {
    log_info "Waiting for Keycloak to be ready..."
    kubectl wait --namespace "$NAMESPACE" \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/name=keycloak \
        --timeout=300s || {
        log_error "Keycloak failed to start within timeout"
        log_info "Pod status:"
        kubectl get pods -n "$NAMESPACE"
        log_info "Pod logs:"
        kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=keycloak --tail=50
        return 1
    }
    log_success "Keycloak is ready!"
}

# Main script
main() {
    log_info "Keycloak Kind Deployment"
    log_info "========================"
    log_info "Cluster name: $CLUSTER_NAME"
    log_info "Namespace: $NAMESPACE"
    log_info "Release name: $RELEASE_NAME"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_tool kind
    check_tool kubectl
    check_tool helm
    log_success "All required tools found"

    # Check if kind cluster exists
    if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        log_error "Kind cluster '$CLUSTER_NAME' not found"
        log_info "Please create it first using:"
        echo "  ./scripts/setup-kind-cluster.sh"
        exit 1
    fi
    log_success "Kind cluster found"

    # Set kubectl context
    kubectl config use-context "kind-${CLUSTER_NAME}"

    # Check if Keycloak is already deployed
    if helm list -n "$NAMESPACE" 2>/dev/null | grep -q "^${RELEASE_NAME}"; then
        log_warning "Keycloak release '$RELEASE_NAME' already exists in namespace '$NAMESPACE'"
        read -p "Uninstall and redeploy? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cleanup
            log_success "Cleaned up existing deployment"
        else
            log_info "Using existing deployment"
            print_connection_info
            exit 0
        fi
    fi

    # Create namespace
    log_info "Creating namespace '$NAMESPACE'..."
    kubectl create namespace "$NAMESPACE" 2>/dev/null || log_warning "Namespace may already exist"

    # Add Bitnami Helm repository
    log_info "Adding Bitnami Helm repository..."
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update

    # Deploy Keycloak
    log_info "Deploying Keycloak..."
    helm install "$RELEASE_NAME" bitnami/keycloak \
        --namespace "$NAMESPACE" \
        --set auth.adminUser="$KEYCLOAK_ADMIN" \
        --set auth.adminPassword="$KEYCLOAK_ADMIN_PASSWORD" \
        --set service.type=NodePort \
        --set service.nodePorts.http="$KEYCLOAK_PORT" \
        --set production=false \
        --set proxy=edge \
        --set httpRelativePath="/" \
        --wait --timeout=5m || {
        log_error "Failed to deploy Keycloak"
        log_info "Helm status:"
        helm status "$RELEASE_NAME" -n "$NAMESPACE"
        exit 1
    }

    # Wait for Keycloak to be ready
    wait_for_keycloak || {
        log_error "Keycloak deployment failed"
        exit 1
    }

    print_connection_info
}

print_connection_info() {
    # Get NodePort
    local node_port=$(kubectl get svc -n "$NAMESPACE" "${RELEASE_NAME}" -o jsonpath='{.spec.ports[0].nodePort}')

    echo
    log_success "Keycloak Deployed to Kind!"
    echo
    log_info "Connection Information:"
    echo "  Admin Console: http://localhost:${node_port}"
    echo "  Admin Username: ${KEYCLOAK_ADMIN}"
    echo "  Admin Password: ${KEYCLOAK_ADMIN_PASSWORD}"
    echo
    log_info "Port Forward (alternative access):"
    echo "  kubectl port-forward -n ${NAMESPACE} svc/${RELEASE_NAME} 8080:80"
    echo "  Then access: http://localhost:8080"
    echo
    log_info "Terraform/OpenTofu Provider Configuration:"
    echo
    cat <<TFEOF
provider "keycloak" {
  client_id     = "admin-cli"
  username      = "${KEYCLOAK_ADMIN}"
  password      = "${KEYCLOAK_ADMIN_PASSWORD}"
  url           = "http://localhost:${node_port}"
  initial_login = false
}
TFEOF
    echo
    log_info "Kubernetes Resources:"
    echo "  View pods:     kubectl get pods -n ${NAMESPACE}"
    echo "  View services: kubectl get svc -n ${NAMESPACE}"
    echo "  View logs:     kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/name=keycloak -f"
    echo
    log_info "Helm Management:"
    echo "  Status:    helm status ${RELEASE_NAME} -n ${NAMESPACE}"
    echo "  Upgrade:   helm upgrade ${RELEASE_NAME} bitnami/keycloak -n ${NAMESPACE}"
    echo "  Uninstall: helm uninstall ${RELEASE_NAME} -n ${NAMESPACE}"
    echo
    log_info "Next Steps:"
    echo "  1. For Helm chart validation (issue 271):"
    echo "     - Verify pods are running: kubectl get pods -n ${NAMESPACE}"
    echo "     - Check service configuration: kubectl get svc -n ${NAMESPACE}"
    echo
    echo "  2. For realm config validation (issue 3wx):"
    echo "     - Use the provider config above in your Terraform/OpenTofu"
    echo "     - Run: terraform plan"
    echo "     - Run: terraform apply"
    echo
}

# Handle script interruption
trap cleanup EXIT INT TERM

# Run main function
main "$@"
