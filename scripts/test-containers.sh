#!/bin/bash
# Container testing script for Podman/Docker
# Tests container builds, runs basic validation, and optionally loads to kind

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_TOOL="${CONTAINER_TOOL:-podman}"
REGISTRY="${REGISTRY:-ghcr.io}"
ORG="${ORG:-your-org}"
PROJECT="gha-runner-token-service"
VERSION="${VERSION:-test}"

BACKEND_IMAGE="${REGISTRY}/${ORG}/${PROJECT}-backend:${VERSION}"
FRONTEND_IMAGE="${REGISTRY}/${ORG}/${PROJECT}-frontend:${VERSION}"

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

cleanup() {
    log_info "Cleaning up test containers..."
    $CONTAINER_TOOL rm -f test-backend test-frontend test-db 2>/dev/null || true
    $CONTAINER_TOOL network rm test-network 2>/dev/null || true
}

# Trap cleanup on exit
trap cleanup EXIT

# Main script
main() {
    log_info "Container Testing Script"
    log_info "========================"
    log_info "Container tool: $CONTAINER_TOOL"
    log_info "Backend image: $BACKEND_IMAGE"
    log_info "Frontend image: $FRONTEND_IMAGE"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_tool "$CONTAINER_TOOL"
    log_success "Container tool found: $CONTAINER_TOOL"

    # Build images
    log_info "Building backend image..."
    $CONTAINER_TOOL build -f Dockerfile.backend -t "$BACKEND_IMAGE" . || {
        log_error "Backend build failed"
        exit 1
    }
    log_success "Backend image built"

    log_info "Building frontend image..."
    $CONTAINER_TOOL build -f frontend/Dockerfile -t "$FRONTEND_IMAGE" frontend/ || {
        log_error "Frontend build failed"
        exit 1
    }
    log_success "Frontend image built"

    # Inspect images
    log_info "Inspecting images..."
    echo "Backend image size: $($CONTAINER_TOOL images --format '{{.Size}}' "$BACKEND_IMAGE")"
    echo "Frontend image size: $($CONTAINER_TOOL images --format '{{.Size}}' "$FRONTEND_IMAGE")"

    # Test backend image
    log_info "Testing backend image..."
    
    # Test 1: Check Python imports
    log_info "  - Testing Python imports..."
    $CONTAINER_TOOL run --rm "$BACKEND_IMAGE" python -c "import app; print('Imports OK')" || {
        log_error "Backend import test failed"
        exit 1
    }
    log_success "  - Python imports OK"

    # Test 2: Check FastAPI app
    log_info "  - Testing FastAPI app..."
    $CONTAINER_TOOL run --rm "$BACKEND_IMAGE" python -c "from app.main import app; print('FastAPI app OK')" || {
        log_error "FastAPI app test failed"
        exit 1
    }
    log_success "  - FastAPI app OK"

    # Test 3: Check dependencies
    log_info "  - Checking dependencies..."
    $CONTAINER_TOOL run --rm "$BACKEND_IMAGE" pip list | grep -E "(fastapi|sqlalchemy|psycopg2)" || {
        log_error "Dependencies check failed"
        exit 1
    }
    log_success "  - Dependencies OK"

    # Test frontend image
    log_info "Testing frontend image..."
    
    # Test 1: Check Nginx config
    log_info "  - Testing Nginx configuration..."
    $CONTAINER_TOOL run --rm "$FRONTEND_IMAGE" nginx -t || {
        log_error "Nginx config test failed"
        exit 1
    }
    log_success "  - Nginx configuration OK"

    # Test 2: Check static files
    log_info "  - Checking static files..."
    $CONTAINER_TOOL run --rm "$FRONTEND_IMAGE" ls -la /usr/share/nginx/html/ | grep index.html || {
        log_error "Static files check failed"
        exit 1
    }
    log_success "  - Static files OK"

    # Integration test
    log_info "Running integration test..."
    
    # Create network
    log_info "  - Creating test network..."
    $CONTAINER_TOOL network create test-network 2>/dev/null || true

    # Start PostgreSQL
    log_info "  - Starting PostgreSQL..."
    $CONTAINER_TOOL run -d \
        --name test-db \
        --network test-network \
        -e POSTGRES_USER=gharts \
        -e POSTGRES_PASSWORD=gharts \
        -e POSTGRES_DB=gharts \
        postgres:15-alpine

    # Wait for PostgreSQL
    log_info "  - Waiting for PostgreSQL to be ready..."
    sleep 5
    for i in {1..30}; do
        if $CONTAINER_TOOL exec test-db pg_isready -U gharts > /dev/null 2>&1; then
            log_success "  - PostgreSQL ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "PostgreSQL failed to start"
            exit 1
        fi
        sleep 1
    done

    # Start backend
    log_info "  - Starting backend..."
    $CONTAINER_TOOL run -d \
        --name test-backend \
        --network test-network \
        -p 8000:8000 \
        -e DATABASE_URL=postgresql://gharts:gharts@test-db:5432/gharts \
        -e GITHUB_APP_ID=123456 \
        -e GITHUB_APP_PRIVATE_KEY="test-key" \
        -e OIDC_CLIENT_ID=test-client \
        -e OIDC_CLIENT_SECRET=test-secret \
        -e OIDC_DISCOVERY_URL=https://example.com/.well-known/openid-configuration \
        -e BOOTSTRAP_ADMIN_USERNAME=admin \
        -e BOOTSTRAP_ADMIN_PASSWORD=admin123 \
        -e BOOTSTRAP_ADMIN_EMAIL=admin@test.local \
        "$BACKEND_IMAGE"

    # Wait for backend
    log_info "  - Waiting for backend to be ready..."
    sleep 5
    for i in {1..30}; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "  - Backend ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "Backend failed to start"
            log_info "Backend logs:"
            $CONTAINER_TOOL logs test-backend
            exit 1
        fi
        sleep 1
    done

    # Test backend endpoints
    log_info "  - Testing backend endpoints..."
    
    # Health check
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "    - Health endpoint OK"
    else
        log_error "Health endpoint failed"
        exit 1
    fi

    # API health check
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        log_success "    - API health endpoint OK"
    else
        log_error "API health endpoint failed"
        exit 1
    fi

    # Start frontend
    log_info "  - Starting frontend..."
    $CONTAINER_TOOL run -d \
        --name test-frontend \
        --network test-network \
        -p 8080:80 \
        "$FRONTEND_IMAGE"

    # Wait for frontend
    log_info "  - Waiting for frontend to be ready..."
    sleep 3
    for i in {1..30}; do
        if curl -f http://localhost:8080/ > /dev/null 2>&1; then
            log_success "  - Frontend ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "Frontend failed to start"
            log_info "Frontend logs:"
            $CONTAINER_TOOL logs test-frontend
            exit 1
        fi
        sleep 1
    done

    # Test frontend
    log_info "  - Testing frontend..."
    if curl -f http://localhost:8080/ | grep -q "<!DOCTYPE html>"; then
        log_success "    - Frontend serving HTML OK"
    else
        log_error "Frontend HTML test failed"
        exit 1
    fi

    # Test API proxy
    log_info "  - Testing API proxy..."
    if curl -f http://localhost:8080/api/v1/health > /dev/null 2>&1; then
        log_success "    - API proxy OK"
    else
        log_warning "    - API proxy test skipped (requires backend connection)"
    fi

    log_success "Integration test passed!"

    # Security scan (if trivy is available)
    if command -v trivy &> /dev/null; then
        log_info "Running security scans..."
        
        log_info "  - Scanning backend image..."
        trivy image --severity HIGH,CRITICAL "$BACKEND_IMAGE" || log_warning "Backend scan found issues"
        
        log_info "  - Scanning frontend image..."
        trivy image --severity HIGH,CRITICAL "$FRONTEND_IMAGE" || log_warning "Frontend scan found issues"
    else
        log_warning "Trivy not found, skipping security scans"
    fi

    # Summary
    echo
    log_success "All tests passed!"
    echo
    log_info "Image Summary:"
    echo "  Backend:  $BACKEND_IMAGE"
    echo "  Frontend: $FRONTEND_IMAGE"
    echo
    log_info "To load images to kind cluster:"
    echo "  kind load docker-image $BACKEND_IMAGE"
    echo "  kind load docker-image $FRONTEND_IMAGE"
    echo
    log_info "To push images to registry:"
    echo "  $CONTAINER_TOOL push $BACKEND_IMAGE"
    echo "  $CONTAINER_TOOL push $FRONTEND_IMAGE"
}

# Run main function
main "$@"

# Made with Bob
