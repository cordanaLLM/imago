#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 35-gpu-nvidia-datacenter.sh — NVIDIA Datacenter (Hopper & Blackwell) driver stack
# Installs NVIDIA Open Kernel Modules, Fabric Manager for NVLink, and Container Toolkit.
set -euo pipefail

BASE_BRANCH="${NVIDIA_DATACENTER_BRANCH:-565}"
CLEAN_BRANCH="${BASE_BRANCH%-open}"

setup_datacenter_repositories() {
  echo "==> Configuring NVIDIA Datacenter & Container Toolkit repositories..."
  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/gpgkey |
    sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  sudo apt-get update
}

install_datacenter_driver_and_fabric() {
  echo "==> Installing NVIDIA Open Kernel Modules and Fabric Manager..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nvidia-driver-"${CLEAN_BRANCH}"-open \
    nvidia-fabricmanager-"${CLEAN_BRANCH}" \
    nvidia-container-toolkit \
    hwinfo || {
    echo "    Warning: specific open branch unavailable, falling back to standard headless..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      nvidia-headless-"${CLEAN_BRANCH}" nvidia-container-toolkit hwinfo
  }

  if systemctl cat nvidia-fabricmanager.service >/dev/null 2>&1; then
    sudo systemctl enable nvidia-fabricmanager.service
  else
    echo "    nvidia-fabricmanager.service is not installed; Fabric Manager is not enabled." >&2
  fi
}

configure_datacenter_runtime() {
  echo "==> Configuring NVIDIA CDI and user permissions for datacenter nodes..."
  if command -v nvidia-ctk >/dev/null 2>&1; then
    if ! sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml; then
      echo "    nvidia-ctk cdi generate returned non-zero; /etc/cdi/nvidia.yaml was not written at build time." >&2
    fi
  fi
  sudo usermod -aG render,video ubuntu
}

main() {
  setup_datacenter_repositories
  install_datacenter_driver_and_fabric
  configure_datacenter_runtime
  echo "==> 35-gpu-nvidia-datacenter: Complete."
}

main "$@"
