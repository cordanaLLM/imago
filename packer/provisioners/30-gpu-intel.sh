#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 30-gpu-intel.sh — Intel Arc, Battlemage Xe2, and UHD/Iris Xe GPU acceleration stack
# Installs Level Zero, oneVPL, Intel Media VA-API driver, OpenCL, and generates CDI specs.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

install_intel_drivers() {
  echo "==> Installing Intel Media Driver, Level Zero, and OpenCL runtime on Ubuntu 26.04..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    intel-media-va-driver-non-free \
    libva2 \
    vainfo \
    intel-opencl-icd \
    clinfo \
    libze1 \
    libze-intel-gpu1 \
    libvpl2 \
    hwinfo
}

configure_intel_permissions_and_cdi() {
  echo "==> Configuring udev rules and Intel Container Device Interface (CDI)..."
  sudo usermod -aG render,video ubuntu

  cat <<'EOF' | sudo tee /etc/udev/rules.d/60-intel-gpu.rules
KERNEL=="card*", SUBSYSTEM=="drm", GROUP="video", MODE="0660"
KERNEL=="renderD*", SUBSYSTEM=="drm", GROUP="render", MODE="0666"
EOF

  sudo mkdir -p /etc/cdi
  cat <<'EOF' | sudo tee /etc/cdi/intel.yaml
cdiVersion: "0.6.0"
kind: "intel.com/gpu"
devices:
  - name: "all"
    containerEdits:
      deviceNodes:
        - path: "/dev/dri/card0"
        - path: "/dev/dri/renderD128"
EOF
}

main() {
  install_intel_drivers
  configure_intel_permissions_and_cdi
  echo "==> 30-gpu-intel: Complete."
}

main "$@"
