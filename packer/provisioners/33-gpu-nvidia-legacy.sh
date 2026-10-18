#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 33-gpu-nvidia-legacy.sh — NVIDIA Legacy (Pascal & Volta) driver and container runtime
# Headless driver of the legacy branch (drivers.nvidia.legacy_driver in versions.json) and
# the NVIDIA Container Toolkit with CDI hooks.
set -euo pipefail

DRIVER_BRANCH="${NVIDIA_LEGACY_DRIVER:?NVIDIA_LEGACY_DRIVER must come from versions.json}"

setup_nvidia_repositories() {
  echo "==> Configuring NVIDIA Container Toolkit apt repository..."
  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/gpgkey |
    sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  sudo apt-get update
}

install_legacy_driver() {
  echo "==> Installing NVIDIA legacy branch ${DRIVER_BRANCH} and container toolkit..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nvidia-headless-"${DRIVER_BRANCH}" \
    nvidia-utils-"${DRIVER_BRANCH}" \
    nvidia-container-toolkit \
    hwinfo
}

configure_nvidia_runtime() {
  echo "==> Configuring NVIDIA CDI and user permissions..."
  if command -v nvidia-ctk >/dev/null 2>&1; then
    if ! sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml; then
      echo "    nvidia-ctk cdi generate returned non-zero; /etc/cdi/nvidia.yaml was not written at build time." >&2
    fi
  fi
  sudo usermod -aG render,video ubuntu
}

main() {
  setup_nvidia_repositories
  install_legacy_driver
  configure_nvidia_runtime
  echo "==> 33-gpu-nvidia-legacy: Complete."
}

main "$@"
