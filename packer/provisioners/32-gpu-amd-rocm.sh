#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 32-gpu-amd-rocm.sh — AMD ROCm compute runtime for AI/ML and GPU acceleration
# Configures the AMD ROCm apt repository, HIP runtime, and /dev/kfd CDI specs.
# Version, repository root and apt suite come from versions.json (drivers.amd).
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

: "${ROCM_VERSION:?ROCM_VERSION must come from versions.json}"
: "${ROCM_REPO:?ROCM_REPO must come from versions.json}"
: "${ROCM_APT_SUITE:?ROCM_APT_SUITE must come from versions.json}"
DISTRO_RELEASE="${DISTRO_RELEASE:-resolute}"

setup_rocm_repository() {
  echo "==> Configuring AMD ROCm apt repository (v${ROCM_VERSION}, suite ${ROCM_APT_SUITE})..."
  # AMD publishes ROCm for jammy and noble only. On another release the image uses the
  # suite from versions.json and says so, instead of a suite AMD does not publish.
  if [ "${ROCM_APT_SUITE}" != "${DISTRO_RELEASE}" ]; then
    echo "    Note: Ubuntu ${DISTRO_RELEASE} uses the ROCm ${ROCM_APT_SUITE} packages."
  fi
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL --max-time 30 "${ROCM_REPO}/rocm.gpg.key" |
    sudo gpg --dearmor --yes -o /etc/apt/keyrings/rocm.gpg

  local arch
  arch="$(dpkg --print-architecture)"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/rocm.gpg] ${ROCM_REPO}/apt/${ROCM_VERSION} ${ROCM_APT_SUITE} main" |
    sudo tee /etc/apt/sources.list.d/rocm.list

  # The Ubuntu archive carries an older ROCm of its own; without this pin apt mixes the
  # two and cannot satisfy rocm-hip-runtime's exact version dependencies.
  printf 'Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600\n' |
    sudo tee /etc/apt/preferences.d/rocm-pin-600

  sudo apt-get update
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
