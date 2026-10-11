#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 31-gpu-amd-mesa.sh — AMD Radeon and Ryzen APU Mesa VA-API and Vulkan stack
# Installs Mesa Gallium radeonsi VA-API, RADV Vulkan drivers, DRM runtime, and CDI specs.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

install_amd_mesa_drivers() {
  echo "==> Installing AMD GPU drivers (Mesa VA-API, RADV Vulkan) on Ubuntu 26.04..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    mesa-va-drivers \
    mesa-vulkan-drivers \
    libdrm-amdgpu1 \
    vainfo \
    vulkan-tools \
    hwinfo
}

configure_amd_permissions_and_cdi() {
  echo "==> Configuring udev rules and AMD Container Device Interface (CDI)..."
  sudo usermod -aG render,video ubuntu

  cat <<'EOF' | sudo tee /etc/udev/rules.d/60-amd-gpu.rules
KERNEL=="card*", SUBSYSTEM=="drm", GROUP="video", MODE="0660"
KERNEL=="renderD*", SUBSYSTEM=="drm", GROUP="render", MODE="0666"
EOF

  sudo mkdir -p /etc/cdi
  cat <<'EOF' | sudo tee /etc/cdi/amd.yaml
cdiVersion: "0.6.0"
kind: "amd.com/gpu"
devices:
  - name: "all"
    containerEdits:
      deviceNodes:
        - path: "/dev/dri/card0"
        - path: "/dev/dri/renderD128"
EOF
}

main() {
  install_amd_mesa_drivers
  configure_amd_permissions_and_cdi
  echo "==> 31-gpu-amd-mesa: Complete."
}

main "$@"
