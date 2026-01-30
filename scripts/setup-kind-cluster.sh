#!/bin/bash
# Setup kind cluster for testing Kubernetes deployment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-gharts-test}"
KUBERNETES_VERSION="${KUBERNETES_VERSION:-v1.28.0}"

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

# Main script
main() {
    log_info "Kind Cluster Setup Script"
    log_info "=========================="
    log_info "Cluster name: $CLUSTER_NAME"
    log_info "Kubernetes version: $KUBERNETES_VERSION"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_tool kind
    check_tool kubectl
    check_tool helm
    log_success "All required tools found"

    # Check if cluster already exists
    if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        log_warning "Cluster '$CLUSTER_NAME' already exists"
        read -p "Delete and recreate? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deleting existing cluster..."
            kind delete cluster --name "$CLUSTER_NAME"
            log_success "Cluster deleted"
        else
            log_info "Using existing cluster"
            kubectl cluster-info --context "kind-${CLUSTER_NAME}"
            exit 0
        fi
    fi

    # Create kind config
    log_info "Creating kind cluster configuration..."
    cat > /tmp/kind-config.yaml <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
  - role: worker
  - role: worker
EOF

    # Create cluster
    log_info "Creating kind cluster..."
    kind create cluster \
        --name "$CLUSTER_NAME" \
        --config /tmp/kind-config.yaml \
        --image "kindest/node:${KUBERNETES_VERSION}" || {
        log_error "Failed to create cluster"
        exit 1
    }
    log_success "Cluster created"

    # Wait for cluster to be ready
    log_info "Waiting for cluster to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=300s
    log_success "Cluster is ready"

    # Install Nginx Ingress Controller
    log_info "Installing Nginx Ingress Controller..."
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

    log_info "Waiting for Ingress Controller to be ready..."
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s
    log_success "Ingress Controller ready"

    # Install cert-manager (optional)
    read -p "Install cert-manager? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installing cert-manager..."
        kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
        
        log_info "Waiting for cert-manager to be ready..."
        kubectl wait --namespace cert-manager \
            --for=condition=ready pod \
            --selector=app.kubernetes.io/instance=cert-manager \
            --timeout=300s
        log_success "cert-manager ready"
    fi

    # Install metrics-server (for HPA)
    log_info "Installing metrics-server..."
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
    
    # Patch metrics-server for kind
    kubectl patch deployment metrics-server -n kube-system --type='json' \
        -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
    
    log_info "Waiting for metrics-server to be ready..."
    kubectl wait --namespace kube-system \
        --for=condition=ready pod \
        --selector=k8s-app=metrics-server \
        --timeout=300s || log_warning "metrics-server may need more time to start"
    log_success "metrics-server installed"

    # Create namespace for application
    log_info "Creating application namespace..."
    kubectl create namespace gharts || log_warning "Namespace may already exist"
    log_success "Namespace created"

    # Display cluster info
    echo
    log_success "Kind cluster setup complete!"
    echo
    log_info "Cluster Information:"
    kubectl cluster-info --context "kind-${CLUSTER_NAME}"
    echo
    log_info "Nodes:"
    kubectl get nodes
    echo
    log_info "To use this cluster:"
    echo "  export KUBECONFIG=\$(kind get kubeconfig --name ${CLUSTER_NAME})"
    echo "  kubectl config use-context kind-${CLUSTER_NAME}"
    echo
    log_info "To delete this cluster:"
    echo "  kind delete cluster --name ${CLUSTER_NAME}"
    echo
    log_info "Next steps:"
    echo "  1. Deploy application (builds and loads images automatically):"
    echo "     ./scripts/deploy-to-kind.sh"
    echo
    echo "  Or manually build and load images:"
    echo "     make build                    # Build images"
    echo "     make load-to-kind             # Load to kind (auto-detects podman/docker)"
    echo
    echo "  Configure with environment variables:"
    echo "     CONTAINER_TOOL=podman|docker  # Default: podman"
    echo "     ORG=your-org                  # Default: your-org"
    echo "     VERSION=latest                # Default: latest"
}

# Run main function
main "$@"

# Made with Bob
