#!/bin/bash
# Start standalone Keycloak in dev mode for local Terraform module validation
# Uses podman to run quay.io/keycloak/keycloak in development mode

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="${KEYCLOAK_CONTAINER_NAME:-gharts-keycloak-dev}"
KEYCLOAK_PORT="${KEYCLOAK_PORT:-8080}"
KEYCLOAK_IMAGE="${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:latest}"
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
            podman)
                echo "    brew install podman  # macOS"
                echo "    # or visit: https://podman.io/getting-started/installation"
                ;;
        esac
        exit 1
    fi
}

cleanup() {
    log_info "Cleaning up..."
    podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

wait_for_keycloak() {
    log_info "Waiting for Keycloak to be ready..."
    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "http://localhost:${KEYCLOAK_PORT}/health/ready" > /dev/null 2>&1; then
            log_success "Keycloak is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    log_error "Keycloak failed to start within timeout"
    return 1
}

# Main script
main() {
    log_info "Keycloak Dev Environment Setup"
    log_info "==============================="
    log_info "Container name: $CONTAINER_NAME"
    log_info "Port: $KEYCLOAK_PORT"
    log_info "Image: $KEYCLOAK_IMAGE"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_tool podman
    check_tool curl
    log_success "All required tools found"

    # Check if container already exists
    if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        log_warning "Container '$CONTAINER_NAME' already exists"
        read -p "Stop and remove existing container? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cleanup
            log_success "Container removed"
        else
            # Check if it's running
            if podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
                log_info "Container is already running"
            else
                log_info "Starting existing container..."
                podman start "$CONTAINER_NAME"
            fi
            wait_for_keycloak
            print_connection_info
            exit 0
        fi
    fi

    # Pull latest image
    log_info "Pulling Keycloak image..."
    podman pull "$KEYCLOAK_IMAGE"

    # Start Keycloak in dev mode
    log_info "Starting Keycloak container..."
    podman run -d \
        --name "$CONTAINER_NAME" \
        -p "${KEYCLOAK_PORT}:8080" \
        -e KEYCLOAK_ADMIN="$KEYCLOAK_ADMIN" \
        -e KEYCLOAK_ADMIN_PASSWORD="$KEYCLOAK_ADMIN_PASSWORD" \
        "$KEYCLOAK_IMAGE" \
        start-dev

    # Wait for Keycloak to be ready
    wait_for_keycloak || {
        log_error "Failed to start Keycloak"
        log_info "Container logs:"
        podman logs "$CONTAINER_NAME"
        cleanup
        exit 1
    }

    print_connection_info
}

print_connection_info() {
    echo
    log_success "Keycloak Dev Environment Ready!"
    echo
    log_info "Connection Information:"
    echo "  Admin Console: http://localhost:${KEYCLOAK_PORT}"
    echo "  Admin Username: ${KEYCLOAK_ADMIN}"
    echo "  Admin Password: ${KEYCLOAK_ADMIN_PASSWORD}"
    echo
    log_info "Terraform Provider Configuration:"
    echo
    cat <<TFEOF
provider "keycloak" {
  client_id     = "admin-cli"
  username      = "${KEYCLOAK_ADMIN}"
  password      = "${KEYCLOAK_ADMIN_PASSWORD}"
  url           = "http://localhost:${KEYCLOAK_PORT}"
  initial_login = false
}
TFEOF
    echo
    log_info "OpenTofu Provider Configuration:"
    echo
    cat <<TFEOF
provider "keycloak" {
  client_id     = "admin-cli"
  username      = "${KEYCLOAK_ADMIN}"
  password      = "${KEYCLOAK_ADMIN_PASSWORD}"
  url           = "http://localhost:${KEYCLOAK_PORT}"
  initial_login = false
}
TFEOF
    echo
    log_info "Container Management:"
    echo "  View logs:    podman logs -f ${CONTAINER_NAME}"
    echo "  Stop:         podman stop ${CONTAINER_NAME}"
    echo "  Start:        podman start ${CONTAINER_NAME}"
    echo "  Remove:       podman rm -f ${CONTAINER_NAME}"
    echo
    log_info "Next Steps:"
    echo "  1. Navigate to terraform/environments/local-keycloak/"
    echo "  2. Run: terraform init"
    echo "  3. Run: terraform plan"
    echo "  4. Run: terraform apply"
    echo
}

# Handle script interruption
trap cleanup EXIT INT TERM

# Run main function
main "$@"
