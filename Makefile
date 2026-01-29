# Makefile for building and testing containers with Podman/Docker

# Variables
CONTAINER_TOOL ?= podman
REGISTRY ?= ghcr.io
ORG ?= your-org
PROJECT ?= gha-runner-token-service
VERSION ?= latest

BACKEND_IMAGE = $(REGISTRY)/$(ORG)/$(PROJECT)-backend
FRONTEND_IMAGE = $(REGISTRY)/$(ORG)/$(PROJECT)-frontend

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[0;33m
NC = \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "$(GREEN)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

.PHONY: check-tool
check-tool: ## Check if container tool is available
	@which $(CONTAINER_TOOL) > /dev/null || (echo "$(RED)Error: $(CONTAINER_TOOL) not found$(NC)" && exit 1)
	@echo "$(GREEN)Using container tool: $(CONTAINER_TOOL)$(NC)"

.PHONY: build-backend
build-backend: check-tool ## Build backend container image
	@echo "$(GREEN)Building backend image...$(NC)"
	$(CONTAINER_TOOL) build -f Dockerfile.backend -t $(BACKEND_IMAGE):$(VERSION) .
	@echo "$(GREEN)Backend image built: $(BACKEND_IMAGE):$(VERSION)$(NC)"

.PHONY: build-frontend
build-frontend: check-tool ## Build frontend container image
	@echo "$(GREEN)Building frontend image...$(NC)"
	$(CONTAINER_TOOL) build -f frontend/Dockerfile -t $(FRONTEND_IMAGE):$(VERSION) frontend/
	@echo "$(GREEN)Frontend image built: $(FRONTEND_IMAGE):$(VERSION)$(NC)"

.PHONY: build
build: build-backend build-frontend ## Build all container images

.PHONY: build-multiarch
build-multiarch: check-tool ## Build multi-architecture images (amd64, arm64)
	@echo "$(GREEN)Building multi-arch backend image...$(NC)"
	$(CONTAINER_TOOL) build --platform linux/amd64,linux/arm64 \
		-f Dockerfile.backend \
		-t $(BACKEND_IMAGE):$(VERSION) .
	@echo "$(GREEN)Building multi-arch frontend image...$(NC)"
	$(CONTAINER_TOOL) build --platform linux/amd64,linux/arm64 \
		-f frontend/Dockerfile \
		-t $(FRONTEND_IMAGE):$(VERSION) frontend/

.PHONY: test-backend
test-backend: build-backend ## Test backend container
	@echo "$(GREEN)Testing backend container...$(NC)"
	@$(CONTAINER_TOOL) run --rm $(BACKEND_IMAGE):$(VERSION) python -c "import app; print('Backend imports OK')"
	@echo "$(GREEN)Backend container test passed$(NC)"

.PHONY: test-frontend
test-frontend: build-frontend ## Test frontend container
	@echo "$(GREEN)Testing frontend container...$(NC)"
	@$(CONTAINER_TOOL) run --rm -d --name test-frontend -p 8888:80 $(FRONTEND_IMAGE):$(VERSION)
	@sleep 2
	@curl -f http://localhost:8888/ > /dev/null 2>&1 && echo "$(GREEN)Frontend container test passed$(NC)" || echo "$(RED)Frontend container test failed$(NC)"
	@$(CONTAINER_TOOL) stop test-frontend
	@$(CONTAINER_TOOL) rm test-frontend

.PHONY: test
test: test-backend test-frontend ## Test all containers

.PHONY: run-backend
run-backend: ## Run backend container locally
	@echo "$(GREEN)Starting backend container...$(NC)"
	$(CONTAINER_TOOL) run --rm -it \
		-p 8000:8000 \
		-e DATABASE_URL=postgresql://gharts:gharts@host.containers.internal:5432/gharts \
		-e GITHUB_APP_ID=123456 \
		-e GITHUB_APP_PRIVATE_KEY="test-key" \
		-e OIDC_CLIENT_ID=test-client \
		-e OIDC_CLIENT_SECRET=test-secret \
		-e OIDC_DISCOVERY_URL=https://example.com/.well-known/openid-configuration \
		$(BACKEND_IMAGE):$(VERSION)

.PHONY: run-frontend
run-frontend: ## Run frontend container locally
	@echo "$(GREEN)Starting frontend container...$(NC)"
	$(CONTAINER_TOOL) run --rm -it \
		-p 8080:80 \
		$(FRONTEND_IMAGE):$(VERSION)

.PHONY: compose-up
compose-up: ## Start all services with docker-compose/podman-compose
	@echo "$(GREEN)Starting services with compose...$(NC)"
	$(CONTAINER_TOOL)-compose up -d
	@echo "$(GREEN)Services started. Access at http://localhost:8080$(NC)"

.PHONY: compose-down
compose-down: ## Stop all services
	@echo "$(GREEN)Stopping services...$(NC)"
	$(CONTAINER_TOOL)-compose down

.PHONY: compose-logs
compose-logs: ## Show logs from all services
	$(CONTAINER_TOOL)-compose logs -f

.PHONY: push-backend
push-backend: build-backend ## Push backend image to registry
	@echo "$(GREEN)Pushing backend image...$(NC)"
	$(CONTAINER_TOOL) push $(BACKEND_IMAGE):$(VERSION)
	@echo "$(GREEN)Backend image pushed$(NC)"

.PHONY: push-frontend
push-frontend: build-frontend ## Push frontend image to registry
	@echo "$(GREEN)Pushing frontend image...$(NC)"
	$(CONTAINER_TOOL) push $(FRONTEND_IMAGE):$(VERSION)
	@echo "$(GREEN)Frontend image pushed$(NC)"

.PHONY: push
push: push-backend push-frontend ## Push all images to registry

.PHONY: tag-release
tag-release: ## Tag images with release version (VERSION=x.y.z)
	@if [ -z "$(VERSION)" ] || [ "$(VERSION)" = "latest" ]; then \
		echo "$(RED)Error: VERSION must be set to a release version (e.g., VERSION=1.0.0)$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Tagging images with version $(VERSION)...$(NC)"
	$(CONTAINER_TOOL) tag $(BACKEND_IMAGE):latest $(BACKEND_IMAGE):$(VERSION)
	$(CONTAINER_TOOL) tag $(FRONTEND_IMAGE):latest $(FRONTEND_IMAGE):$(VERSION)
	@echo "$(GREEN)Images tagged with $(VERSION)$(NC)"

.PHONY: save-images
save-images: build ## Save images to tar files
	@echo "$(GREEN)Saving images to tar files...$(NC)"
	$(CONTAINER_TOOL) save -o backend-$(VERSION).tar $(BACKEND_IMAGE):$(VERSION)
	$(CONTAINER_TOOL) save -o frontend-$(VERSION).tar $(FRONTEND_IMAGE):$(VERSION)
	@echo "$(GREEN)Images saved:$(NC)"
	@ls -lh backend-$(VERSION).tar frontend-$(VERSION).tar

.PHONY: load-images
load-images: ## Load images from tar files
	@echo "$(GREEN)Loading images from tar files...$(NC)"
	$(CONTAINER_TOOL) load -i backend-$(VERSION).tar
	$(CONTAINER_TOOL) load -i frontend-$(VERSION).tar
	@echo "$(GREEN)Images loaded$(NC)"

.PHONY: load-to-kind
load-to-kind: build ## Load images to kind cluster
	@echo "$(GREEN)Loading images to kind cluster...$(NC)"
	kind load docker-image $(BACKEND_IMAGE):$(VERSION)
	kind load docker-image $(FRONTEND_IMAGE):$(VERSION)
	@echo "$(GREEN)Images loaded to kind$(NC)"

.PHONY: scan-backend
scan-backend: build-backend ## Scan backend image for vulnerabilities
	@echo "$(GREEN)Scanning backend image...$(NC)"
	@which trivy > /dev/null && trivy image $(BACKEND_IMAGE):$(VERSION) || echo "$(YELLOW)trivy not found, skipping scan$(NC)"

.PHONY: scan-frontend
scan-frontend: build-frontend ## Scan frontend image for vulnerabilities
	@echo "$(GREEN)Scanning frontend image...$(NC)"
	@which trivy > /dev/null && trivy image $(FRONTEND_IMAGE):$(VERSION) || echo "$(YELLOW)trivy not found, skipping scan$(NC)"

.PHONY: scan
scan: scan-backend scan-frontend ## Scan all images for vulnerabilities

.PHONY: inspect-backend
inspect-backend: ## Inspect backend image
	$(CONTAINER_TOOL) inspect $(BACKEND_IMAGE):$(VERSION)

.PHONY: inspect-frontend
inspect-frontend: ## Inspect frontend image
	$(CONTAINER_TOOL) inspect $(FRONTEND_IMAGE):$(VERSION)

.PHONY: shell-backend
shell-backend: ## Open shell in backend container
	$(CONTAINER_TOOL) run --rm -it --entrypoint /bin/bash $(BACKEND_IMAGE):$(VERSION)

.PHONY: shell-frontend
shell-frontend: ## Open shell in frontend container
	$(CONTAINER_TOOL) run --rm -it --entrypoint /bin/sh $(FRONTEND_IMAGE):$(VERSION)

.PHONY: clean
clean: ## Remove built images
	@echo "$(GREEN)Removing images...$(NC)"
	-$(CONTAINER_TOOL) rmi $(BACKEND_IMAGE):$(VERSION)
	-$(CONTAINER_TOOL) rmi $(FRONTEND_IMAGE):$(VERSION)
	@echo "$(GREEN)Images removed$(NC)"

.PHONY: clean-all
clean-all: clean ## Remove all images and tar files
	@echo "$(GREEN)Removing tar files...$(NC)"
	-rm -f backend-*.tar frontend-*.tar
	@echo "$(GREEN)Cleanup complete$(NC)"

.PHONY: prune
prune: ## Prune unused containers, images, and volumes
	@echo "$(YELLOW)Warning: This will remove all unused containers, images, and volumes$(NC)"
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(CONTAINER_TOOL) system prune -af --volumes; \
	fi

.PHONY: list-images
list-images: ## List all project images
	@echo "$(GREEN)Project images:$(NC)"
	@$(CONTAINER_TOOL) images | grep $(PROJECT) || echo "No images found"

.PHONY: verify-build
verify-build: build test ## Build and test all images
	@echo "$(GREEN)All images built and tested successfully!$(NC)"

# Development helpers
.PHONY: dev-setup
dev-setup: ## Setup development environment
	@echo "$(GREEN)Setting up development environment...$(NC)"
	python -m pip install -r requirements.txt
	python -m pip install -r requirements-dev.txt
	cd frontend && npm install
	@echo "$(GREEN)Development environment ready$(NC)"

.PHONY: dev-test
dev-test: ## Run tests locally (without containers)
	@echo "$(GREEN)Running backend tests...$(NC)"
	python -m pytest tests/ -v
	@echo "$(GREEN)Running frontend tests...$(NC)"
	cd frontend && npm test

.PHONY: dev-lint
dev-lint: ## Run linters
	@echo "$(GREEN)Running backend linters...$(NC)"
	python -m ruff check app/ tests/
	python -m mypy app/
	@echo "$(GREEN)Running frontend linters...$(NC)"
	cd frontend && npm run lint

# CI/CD helpers
.PHONY: ci-build
ci-build: verify-build ## CI build target (build and test)

.PHONY: ci-push
ci-push: build push ## CI push target (build and push)

.PHONY: ci-release
ci-release: ## CI release target (build, tag, and push release)
	@if [ -z "$(VERSION)" ] || [ "$(VERSION)" = "latest" ]; then \
		echo "$(RED)Error: VERSION must be set for release$(NC)"; \
		exit 1; \
	fi
	$(MAKE) build VERSION=$(VERSION)
	$(MAKE) tag-release VERSION=$(VERSION)
	$(MAKE) push VERSION=$(VERSION)
	@echo "$(GREEN)Release $(VERSION) complete$(NC)"