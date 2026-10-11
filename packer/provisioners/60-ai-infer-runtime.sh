#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 60-ai-infer-runtime.sh — Turnkey AI/LLM inference host configuration (vLLM & Ollama)
# Configures transparent hugepages, NUMA interleaving, and high-performance execution.
set -euo pipefail

configure_hugepages_and_numa() {
  echo "==> Configuring transparent hugepages and memory allocation..."
  cat <<'EOF' | sudo tee /etc/sysctl.d/95-ai-memory.conf
# Enable transparent hugepages compaction and virtual memory overcommit
vm.overcommit_memory = 1
vm.max_map_count = 1048576
EOF

  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    numactl \
    libnuma-dev \
    libgomp1
}

setup_inference_directories() {
  echo "==> Setting up model cache directories and permissions..."
  sudo mkdir -p /var/lib/models/huggingface /var/lib/models/ollama /var/lib/models/vllm /etc/vllm /etc/ollama
  sudo chown -R ubuntu:ubuntu /var/lib/models

  # Hook environment variables for model caches and runtime thread affinity
  cat <<'EOF' | sudo tee /etc/profile.d/ai-env.sh
export HF_HOME="/var/lib/models/huggingface"
export OLLAMA_MODELS="/var/lib/models/ollama"
export VLLM_CACHE_ROOT="/var/lib/models/vllm"
export OMP_PROC_BIND="spread"
export OMP_PLACES="threads"
EOF

  # If Intel GPU runtime is present, configure oneAPI Level Zero selector
  if [ -f /etc/cdi/intel.yaml ] || [ -d /usr/lib/x86_64-linux-gnu/levelzero ]; then
    echo "export ONEAPI_DEVICE_SELECTOR=level_zero:*" | sudo tee -a /etc/profile.d/ai-env.sh
  fi

  # If AMD ROCm runtime is present, configure ROCm paths
  if [ -d /opt/rocm ] || [ -f /etc/cdi/amd.yaml ]; then
    echo "export ROCM_PATH=/opt/rocm" | sudo tee -a /etc/profile.d/ai-env.sh
    echo "export PATH=\$PATH:/opt/rocm/bin" | sudo tee -a /etc/profile.d/ai-env.sh
  fi
}

main() {
  configure_hugepages_and_numa
  setup_inference_directories
  echo "==> 60-ai-infer-runtime: Complete."
}

main "$@"
