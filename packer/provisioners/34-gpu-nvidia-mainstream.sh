#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 34-gpu-nvidia-mainstream.sh — NVIDIA Mainstream (Ampere, Ada, Turing) driver stack
# Pinned NVIDIA 565+ headless driver and NVIDIA Container Toolkit with modern CDI v0.6+.
set -euo pipefail

DRIVER_BRANCH="${NVIDIA_MAINSTREAM_DRIVER:-565}"

setup_nvidia_repositories() {
  echo "==> Configuring NVIDIA Container Toolkit apt repository..."
  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/gpgkey |
    sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  sudo apt-get update
}

install_mainstream_driver() {
  echo "==> Installing NVIDIA mainstream branch ${DRIVER_BRANCH} and container toolkit..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nvidia-headless-"${DRIVER_BRANCH}" \
    nvidia-utils-"${DRIVER_BRANCH}" \
    nvidia-container-toolkit \
    hwinfo
}

configure_nvidia_runtime() {
  echo "==> Configuring modern NVIDIA Container Device Interface (CDI)..."
  if command -v nvidia-ctk >/dev/null 2>&1; then
    if ! sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml; then
      echo "    nvidia-ctk cdi generate returned non-zero; /etc/cdi/nvidia.yaml was not written at build time." >&2
    fi
  fi
  sudo usermod -aG render,video ubuntu
}

main() {
  setup_nvidia_repositories
  install_mainstream_driver
  configure_nvidia_runtime
  echo "==> 34-gpu-nvidia-mainstream: Complete."
}

main "$@"
