.PHONY: help init fmt fmt-check lint test clean compress docs-serve docs-build \
        build-cli test-go audit lint-workflows lint-manifest \
        build-base-generic build-base-intel build-base-amd \
        build-base-nvidia-legacy build-base-nvidia-mainstream build-base-nvidia-modern build-base-nvidia-bleeding build-base-nvidia-datacenter \
        build-docker-generic build-docker-intel build-docker-amd build-docker-nvidia build-docker-nvidia-modern build-docker-nvidia-bleeding \
        build-podman-generic \
        build-k8s-generic build-k8s-cilium build-k8s-calico build-k8s-flannel \
        build-k8s-intel build-k8s-amd build-k8s-nvidia build-k8s-nvidia-modern build-k8s-nvidia-bleeding \
        build-ai-infer-generic build-ai-infer-intel build-ai-infer-amd \
        build-k3s-agent-generic build-k3s-agent-intel build-k3s-agent-amd build-k3s-agent-nvidia build-k3s-server-generic \
        build-cloudnative-generic build-cloudnative-k8s build-cloudnative-storage build-cloudnative-pg \
        build-appliance-vision-nvr build-appliance-gateway-dns build-appliance-media-server build-appliance-ci-runner build-appliance-game-server \
        build-generic build-intel build-amd build-nvidia


SHELL := /usr/bin/env bash
PACKER := packer

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-28s\033[0m %s\n", $$1, $$2}'

init: ## Initialize Packer plugins
	@cd packer && $(PACKER) init .

fmt: ## Format Packer HCL configurations
	@cd packer && $(PACKER) fmt .

fmt-check: ## Verify Packer HCL formatting
	@cd packer && $(PACKER) fmt -check .

lint: fmt-check lint-workflows lint-manifest ## Run packer validate, shellcheck, actionlint, and yamllint
	@echo "==> Validating Packer configuration..."
	@cd packer && $(PACKER) validate .
	@echo "==> Running ShellCheck on provisioner scripts..."
	@shellcheck packer/provisioners/*.sh scripts/*.sh
	@if command -v yamllint >/dev/null 2>&1; then \
		echo "==> Running Yamllint..."; \
		yamllint -c .yamllint.yml .github/ packer/http/; \
	fi
	@echo "==> All lint checks passed successfully."

lint-workflows: ## Run actionlint on GitHub Actions workflows
	@PATH="$$HOME/go/bin:$$PATH" actionlint .github/workflows/*.yml

lint-manifest: ## Validate versions.json against schema
	@python3 -c "import json, jsonschema; jsonschema.validate(json.load(open('versions.json')), json.load(open('versions.schema.json')))"

build-cli: ## Build Go 1.27 imago CLI and MCP server
	@go build -o bin/imago ./cmd/imago

test-go: ## Run Go unit test suite
	@go test ./... -v

test-bench: ## Run Go benchmarks with memory allocation metrics
	@go test -bench ".*" -benchmem ./...

test-coverage: ## Run Go test coverage analysis
	@go test -cover -coverprofile=coverage.out ./...
	@go tool cover -func=coverage.out

test: test-go ## Run automated configuration, SSOT, privacy, execution, and container tests
	@pytest tests/ -v

test-all: lint test test-bench ## Run full enterprise verification suite (lints, unit tests, mock execution, live docker, benchmarks)

compress: ## Compress generated output images with zstd (sparse)
	@echo "==> Compressing output images with zstd (sparse, -19)..."
	@find output-images -type f -name '*.qcow2' -exec zstd -T0 -19 --sparse --rm {} +
	@echo "==> Compression complete."

docs-serve: ## Serve documentation portal locally via mkdocs
	@mkdocs serve

docs-build: ## Build documentation portal strictly
	@mkdocs build --strict

build: init ## Build any flavor dynamically (e.g. make build FLAVOR=base-generic)
	@if [ -z "$(FLAVOR)" ]; then \
		echo "Error: FLAVOR is required. Example: make build FLAVOR=base-generic"; \
		exit 1; \
	fi
	@echo "==> Building flavor: $(FLAVOR)..."
	@cd packer && $(PACKER) build -only="$(FLAVOR).qemu.image" .

# Base Flavors
build-base-generic: init ## Build base-generic minimal cloud image
	@$(MAKE) build FLAVOR=base-generic

build-base-intel: init ## Build base-intel image (Xe/Arc Media/Compute)
	@$(MAKE) build FLAVOR=base-intel

build-base-amd: init ## Build base-amd image (Mesa/RADV Vulkan)
	@$(MAKE) build FLAVOR=base-amd

build-base-nvidia-legacy: init ## Build base-nvidia-legacy image (NVIDIA 535 / CUDA 12.2)
	@cd packer && $(PACKER) build -only="base-nvidia-legacy.qemu.image" .

build-base-nvidia-mainstream: init ## Build base-nvidia-mainstream image (NVIDIA 565 / CUDA 12.8)
	@cd packer && $(PACKER) build -only="base-nvidia-mainstream.qemu.image" .

build-base-nvidia-modern: init ## Build base-nvidia-modern image (NVIDIA 610 / CUDA 13.3)
	@cd packer && $(PACKER) build -only="base-nvidia-modern.qemu.image" .

build-base-nvidia-bleeding: init ## Build base-nvidia-bleeding image (NVIDIA 615 / CUDA 13.4)
	@cd packer && $(PACKER) build -only="base-nvidia-bleeding.qemu.image" .

build-base-nvidia-datacenter: init ## Build base-nvidia-datacenter image (Open Modules + Fabric Mgr)
	@cd packer && $(PACKER) build -only="base-nvidia-datacenter.qemu.image" .

# Docker & Container Appliances
build-docker-generic: init ## Build docker-generic appliance (Docker 29.8)
	@cd packer && $(PACKER) build -only="docker-generic.qemu.image" .

build-docker-intel: init ## Build docker-intel appliance (QuickSync / CDI)
	@cd packer && $(PACKER) build -only="docker-intel.qemu.image" .

build-docker-amd: init ## Build docker-amd appliance (ROCm 10 / CDI)
	@cd packer && $(PACKER) build -only="docker-amd.qemu.image" .

build-docker-nvidia: init ## Build docker-nvidia appliance (NVIDIA 565 / CDI)
	@cd packer && $(PACKER) build -only="docker-nvidia.qemu.image" .

build-docker-nvidia-modern: init ## Build docker-nvidia-modern appliance (NVIDIA 610 / CDI)
	@cd packer && $(PACKER) build -only="docker-nvidia-modern.qemu.image" .

build-docker-nvidia-bleeding: init ## Build docker-nvidia-bleeding appliance (NVIDIA 615 / CDI)
	@cd packer && $(PACKER) build -only="docker-nvidia-bleeding.qemu.image" .

build-podman-generic: init ## Build podman-generic appliance (Quadlet / Netavark)
	@cd packer && $(PACKER) build -only="podman-generic.qemu.image" .

# Kubernetes Node Flavors
build-k8s-generic: init ## Build k8s-node-generic image (Lean zero-preheat)
	@cd packer && $(PACKER) build -only="k8s-node-generic.qemu.image" .

build-k8s-cilium: init ## Build k8s-node-cilium image (Preheated Cilium CNI & kube-vip)
	@cd packer && $(PACKER) build -only="k8s-node-cilium.qemu.image" .

build-k8s-calico: init ## Build k8s-node-calico image (Preheated Calico CNI & kube-vip)
	@cd packer && $(PACKER) build -only="k8s-node-calico.qemu.image" .

build-k8s-flannel: init ## Build k8s-node-flannel image (Preheated Flannel CNI & kube-vip)
	@cd packer && $(PACKER) build -only="k8s-node-flannel.qemu.image" .

build-k8s-intel: init ## Build k8s-node-intel image (Intel K8s Plugin)
	@cd packer && $(PACKER) build -only="k8s-node-intel.qemu.image" .

build-k8s-amd: init ## Build k8s-node-amd image (AMD ROCm K8s Plugin)
	@cd packer && $(PACKER) build -only="k8s-node-amd.qemu.image" .

build-k8s-nvidia: init ## Build k8s-node-nvidia image (NVIDIA 565 K8s Plugin)
	@cd packer && $(PACKER) build -only="k8s-node-nvidia.qemu.image" .

build-k8s-nvidia-modern: init ## Build k8s-node-nvidia-modern image (NVIDIA 610 K8s Plugin)
	@cd packer && $(PACKER) build -only="k8s-node-nvidia-modern.qemu.image" .

build-k8s-nvidia-bleeding: init ## Build k8s-node-nvidia-bleeding image (NVIDIA 615 K8s Plugin)
	@cd packer && $(PACKER) build -only="k8s-node-nvidia-bleeding.qemu.image" .

# AI Inference Appliances
build-ai-infer-generic: init ## Build ai-infer-generic host (CPU High-Throughput / AMX / AVX-512)
	@cd packer && $(PACKER) build -only="ai-infer-generic.qemu.image" .

build-ai-infer-intel: init ## Build ai-infer-intel host (Intel Arc/Xe2 / OpenVINO / Level Zero)
	@cd packer && $(PACKER) build -only="ai-infer-intel.qemu.image" .

build-ai-infer-amd: init ## Build ai-infer-amd host (AMD ROCm 10 / RDNA 3/4 & Instinct)
	@cd packer && $(PACKER) build -only="ai-infer-amd.qemu.image" .

build-ai-infer-nvidia: init ## Build ai-infer-nvidia host (NVIDIA 565 / Hugepages / vLLM)
	@cd packer && $(PACKER) build -only="ai-infer-nvidia.qemu.image" .

build-ai-infer-nvidia-modern: init ## Build ai-infer-nvidia-modern host (NVIDIA 610 / Hugepages / vLLM)
	@cd packer && $(PACKER) build -only="ai-infer-nvidia-modern.qemu.image" .

build-ai-infer-nvidia-bleeding: init ## Build ai-infer-nvidia-bleeding host (NVIDIA 615 / Blackwell / vLLM)
	@cd packer && $(PACKER) build -only="ai-infer-nvidia-bleeding.qemu.image" .

# K3s Edge Fleet Flavors
build-k3s-agent-generic: init ## Build k3s-agent-generic image (Lightweight < 300MB RAM worker)
	@cd packer && $(PACKER) build -only="k3s-agent-generic.qemu.image" .

build-k3s-agent-intel: init ## Build k3s-agent-intel image (K3s worker + QuickSync / Xe)
	@cd packer && $(PACKER) build -only="k3s-agent-intel.qemu.image" .

build-k3s-agent-amd: init ## Build k3s-agent-amd image (K3s worker + AMD ROCm 10)
	@cd packer && $(PACKER) build -only="k3s-agent-amd.qemu.image" .

build-k3s-agent-nvidia: init ## Build k3s-agent-nvidia image (K3s worker + NVIDIA 565 / CDI)
	@cd packer && $(PACKER) build -only="k3s-agent-nvidia.qemu.image" .

build-k3s-server-generic: init ## Build k3s-server-generic image (K3s control plane + SQLite)
	@cd packer && $(PACKER) build -only="k3s-server-generic.qemu.image" .

# CloudNative & Storage Appliances
build-cloudnative-generic: init ## Build cloudnative-generic immutable container host
	@cd packer && $(PACKER) build -only="cloudnative-generic.qemu.image" .

build-cloudnative-k8s: init ## Build cloudnative-k8s immutable Kubernetes worker node
	@cd packer && $(PACKER) build -only="cloudnative-k8s.qemu.image" .

build-cloudnative-storage: init ## Build cloudnative-storage CNCF storage appliance (NVMe-oF / ZFS)
	@cd packer && $(PACKER) build -only="cloudnative-storage.qemu.image" .

build-cloudnative-pg: init ## Build cloudnative-pg PostgreSQL / CloudNativePG host
	@cd packer && $(PACKER) build -only="cloudnative-pg.qemu.image" .

# Specialized Homelab Appliances
build-appliance-vision-nvr: init ## Build appliance-vision-nvr (Coral TPU + QuickSync + Frigate)
	@cd packer && $(PACKER) build -only="appliance-vision-nvr.qemu.image" .

build-appliance-gateway-dns: init ## Build appliance-gateway-dns (Port 53 freed, WireGuard, AdGuard/Pi-hole)
	@cd packer && $(PACKER) build -only="appliance-gateway-dns.qemu.image" .

build-appliance-media-server: init ## Build appliance-media-server (Intel/AMD VA-API, NFS/CIFS, Jellyfin/Plex)
	@cd packer && $(PACKER) build -only="appliance-media-server.qemu.image" .

build-appliance-ci-runner: init ## Build appliance-ci-runner (QEMU ARM64 binfmt, Buildx, GitHub/GitLab runner)
	@cd packer && $(PACKER) build -only="appliance-ci-runner.qemu.image" .

build-appliance-game-server: init ## Build appliance-game-server (SteamCMD, 32-bit glibc, low-latency UDP)
	@cd packer && $(PACKER) build -only="appliance-game-server.qemu.image" .



# Backwards compatibility aliases
build-generic: build-base-generic
build-intel: build-base-intel
build-amd: build-base-amd
build-nvidia: build-docker-nvidia

clean: ## Clean up local build artifacts and caches
	@rm -rf output-images/ packer/packer_cache/ .pytest_cache/ site/
	@echo "==> Build artifacts cleaned."

# Praetor declared verification; existing project recipes remain unchanged.
.PHONY: verify-all
verify-all:
	@standardsctl compile-context --verify
	@standardsctl audit
	@'go' 'build' '-v' './...'
	@'go' 'test' '-v' '-race' './...'
	@'python3' '-m' 'pytest'

compile-context:
	@standardsctl compile-context

audit:
	@standardsctl audit
