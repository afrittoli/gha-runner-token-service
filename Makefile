# Makefile for building and testing containers with Podman/Docker

# Variables
CONTAINER_TOOL ?= podman
REGISTRY ?= ghcr.io
ORG ?= afrittoli
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
	$(CONTAINER_TOOL) build -f Dockerfile -t $(BACKEND_IMAGE):$(VERSION) .
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
		-f Dockerfile \
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
ifeq ($(CONTAINER_TOOL),docker)
	kind load docker-image $(BACKEND_IMAGE):$(VERSION)
	kind load docker-image $(FRONTEND_IMAGE):$(VERSION)
else
	@echo "$(YELLOW)Using save/load approach for $(CONTAINER_TOOL)...$(NC)"
	$(CONTAINER_TOOL) save -o /tmp/backend-kind.tar $(BACKEND_IMAGE):$(VERSION)
	$(CONTAINER_TOOL) save -o /tmp/frontend-kind.tar $(FRONTEND_IMAGE):$(VERSION)
	kind load image-archive /tmp/backend-kind.tar
	kind load image-archive /tmp/frontend-kind.tar
	rm -f /tmp/backend-kind.tar /tmp/frontend-kind.tar
endif
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

# Kind cluster targets
.PHONY: kind-setup
kind-setup: ## Setup kind cluster for testing
	@echo "$(GREEN)Setting up kind cluster...$(NC)"
	./scripts/setup-kind-cluster.sh

.PHONY: kind-deploy
kind-deploy: ## Build images and deploy to kind cluster
	@echo "$(GREEN)Deploying to kind cluster...$(NC)"
	./scripts/deploy-to-kind.sh

.PHONY: kind-clean
kind-clean: ## Delete the kind test cluster
	@echo "$(YELLOW)Deleting kind cluster...$(NC)"
	kind delete cluster --name $${CLUSTER_NAME:-gharts-test}
	@echo "$(GREEN)Kind cluster deleted$(NC)"

.PHONY: kind-logs
kind-logs: ## Show logs from kind deployment
	@echo "$(GREEN)Showing backend logs...$(NC)"
	kubectl logs -n $${NAMESPACE:-gharts} -l app.kubernetes.io/component=backend --tail=100 -f

# Helm chart targets
.PHONY: helm-lint
helm-lint: ## Lint Helm chart
	@echo "$(GREEN)Linting Helm chart...$(NC)"
	helm lint helm/gharts
	@echo "$(GREEN)Helm chart lint passed$(NC)"

.PHONY: helm-template
helm-template: ## Validate Helm chart templates
	@echo "$(GREEN)Validating Helm chart templates...$(NC)"
	helm template test-release helm/gharts \
		--set config.githubAppId=123456 \
		--set config.githubAppPrivateKey="test-key" \
		--set config.oidcClientId=test \
		--set config.oidcClientSecret=test \
		--set config.oidcDiscoveryUrl=https://example.com/.well-known/openid-configuration \
		--set bootstrap.admin.password=test123 \
		> /dev/null
	@echo "$(GREEN)Helm chart templates valid$(NC)"

.PHONY: helm-package
helm-package: ## Package Helm chart
	@echo "$(GREEN)Packaging Helm chart...$(NC)"
	mkdir -p dist
	helm package helm/gharts -d dist/
	@echo "$(GREEN)Helm chart packaged$(NC)"
	@ls -lh dist/gharts-*.tgz

.PHONY: helm-push
helm-push: ## Push Helm chart to OCI registry (requires VERSION)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION must be set (e.g., VERSION=1.0.0)$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Pushing Helm chart to OCI registry...$(NC)"
	@if [ ! -f "dist/gharts-$(VERSION).tgz" ]; then \
		echo "$(YELLOW)Chart not found, packaging first...$(NC)"; \
		$(MAKE) helm-package; \
	fi
	helm push dist/gharts-$(VERSION).tgz oci://$(REGISTRY)/$(ORG)
	@echo "$(GREEN)Helm chart pushed to $(REGISTRY)/$(ORG)/gharts:$(VERSION)$(NC)"

.PHONY: helm-test
helm-test: helm-lint helm-template ## Run all Helm chart tests
	@echo "$(GREEN)All Helm chart tests passed$(NC)"

.PHONY: helm-install-local
helm-install-local: ## Install chart locally from filesystem
	@echo "$(GREEN)Installing Helm chart locally...$(NC)"
	helm upgrade --install gharts-local helm/gharts \
		--set config.githubAppId=123456 \
		--set config.githubAppPrivateKey="test-key" \
		--set config.oidcClientId=test \
		--set config.oidcClientSecret=test \
		--set config.oidcDiscoveryUrl=https://example.com/.well-known/openid-configuration \
		--set bootstrap.admin.password=test123 \
		--create-namespace \
		--namespace gharts-test
	@echo "$(GREEN)Helm chart installed in namespace gharts-test$(NC)"

.PHONY: helm-uninstall-local
helm-uninstall-local: ## Uninstall local chart installation
	@echo "$(YELLOW)Uninstalling local Helm chart...$(NC)"
	helm uninstall gharts-local -n gharts-test || true
	kubectl delete namespace gharts-test || true
	@echo "$(GREEN)Local Helm chart uninstalled$(NC)"

.PHONY: helm-install-oci
helm-install-oci: ## Install chart from OCI registry (requires VERSION)
	@if [ -z "$(VERSION)" ]; then \
		VERSION=latest; \
	fi
	@echo "$(GREEN)Installing Helm chart from OCI registry (version: $(VERSION))...$(NC)"
	helm upgrade --install gharts-oci oci://$(REGISTRY)/$(ORG)/gharts \
		--version $(VERSION) \
		--set config.githubAppId=123456 \
		--set config.githubAppPrivateKey="test-key" \
		--set config.oidcClientId=test \
		--set config.oidcClientSecret=test \
		--set config.oidcDiscoveryUrl=https://example.com/.well-known/openid-configuration \
		--set bootstrap.admin.password=test123 \
		--create-namespace \
		--namespace gharts-oci-test
	@echo "$(GREEN)Helm chart installed from OCI registry$(NC)"

.PHONY: helm-uninstall-oci
helm-uninstall-oci: ## Uninstall OCI chart installation
	@echo "$(YELLOW)Uninstalling OCI Helm chart...$(NC)"
	helm uninstall gharts-oci -n gharts-oci-test || true
	kubectl delete namespace gharts-oci-test || true
	@echo "$(GREEN)OCI Helm chart uninstalled$(NC)"
