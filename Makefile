# Via http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html

# Detect container runtime: prefer podman, fall back to docker
CONTAINER_RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
ifeq ($(CONTAINER_RUNTIME),)
$(error Neither podman nor docker found in PATH. Please install one of them.)
endif

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies with uv
	uv sync

.PHONY: run
run: ## Run the podcast backup
	uv run podcast-backup

.PHONY: run-debug
run-debug: ## Run the podcast backup with debug logging
	uv run podcast-backup --debug

.PHONY: clean
clean: ## Clean build artifacts and cache
	rm -rf .venv
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: lint
lint: ## Run linters
	uv run ruff check .

.PHONY: format
format: ## Format code
	uv run ruff format .

.PHONY: docker-build
docker-build: ## Build Docker image
	$(CONTAINER_RUNTIME) build -t podcast-backup:latest .

.PHONY: docker-run
docker-run: docker-build ## Run podcast backup in Docker
	$(CONTAINER_RUNTIME) run --rm \
		-v ./config.toml:/config/config.toml:ro \
		-v ./podcasts:/podcasts \
		podcast-backup:latest

.PHONY: docker-run-debug
docker-run-debug: docker-build ## Run podcast backup in Docker with debug logging
	$(CONTAINER_RUNTIME) run --rm \
		-v ./config.toml:/config/config.toml:ro \
		-v ./podcasts:/podcasts \
		podcast-backup:latest --debug

.DEFAULT_GOAL := help
