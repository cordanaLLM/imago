#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 32-gpu-amd-rocm.sh — AMD ROCm compute runtime for AI/ML and GPU acceleration
# Configures ROCm repository (ROCm 7.0 / 10.0), HIP runtime, and /dev/kfd CDI specs.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

ROCM_VERSION="${ROCM_VERSION:-10.0}"
DISTRO_RELEASE="${DISTRO_RELEASE:-resolute}"

setup_rocm_repository() {
  echo "==> Configuring AMD ROCm apt repository (v${ROCM_VERSION}) on Ubuntu ${DISTRO_RELEASE}..."
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL --max-time 30 https://repo.radeon.com/rocm/rocm.gpg |
    sudo gpg --dearmor --yes -o /etc/apt/keyrings/rocm.gpg

  local arch
  arch="$(dpkg --print-architecture)"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/${ROCM_VERSION} ${DISTRO_RELEASE} main" |
    sudo tee /etc/apt/sources.list.d/rocm.list

  sudo apt-get update || echo "    Warning: repository index update returned non-zero, continuing..."
}

install_rocm_packages() {
  echo "==> Installing ROCm HIP runtime and core compute libraries..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    rocm-hip-runtime \
    rocminfo \
    hwinfo
}

configure_rocm_permissions_and_cdi() {
  echo "==> Configuring AMD KFD compute permissions and Container Device Interface (CDI)..."
  sudo usermod -aG render,video ubuntu

  cat <<'EOF' | sudo tee /etc/udev/rules.d/65-rocm-kfd.rules
KERNEL=="kfd", SUBSYSTEM=="kfd", GROUP="render", MODE="0666"
EOF

  sudo mkdir -p /etc/cdi
  cat <<'EOF' | sudo tee /etc/cdi/amd.yaml
cdiVersion: "0.6.0"
kind: "amd.com/gpu"
devices:
  - name: "all"
    containerEdits:
      deviceNodes:
        - path: "/dev/kfd"
        - path: "/dev/dri/card0"
        - path: "/dev/dri/renderD128"
EOF
}

main() {
  setup_rocm_repository
  install_rocm_packages
  configure_rocm_permissions_and_cdi
  echo "==> 32-gpu-amd-rocm: Complete."
}

main "$@"
