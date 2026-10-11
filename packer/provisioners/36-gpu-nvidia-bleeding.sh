#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 36-gpu-nvidia-bleeding.sh — NVIDIA Bleeding (Blackwell RTX 5090/B200, Ada) R615/R610 + CUDA 13.4
# Cutting-edge driver stack with native Container Device Interface (CDI) and MPS support.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

DRIVER_BRANCH="${NVIDIA_BLEEDING_DRIVER:-615}"
CUDA_VER="${CUDA_BLEEDING:-13.4}"

setup_nvidia_repositories() {
  echo "==> Configuring NVIDIA Container Toolkit and CUDA ${CUDA_VER} repositories..."
  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/gpgkey |
    sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL --max-time 30 https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  sudo apt-get update
}

install_bleeding_driver() {
  echo "==> Installing NVIDIA bleeding branch ${DRIVER_BRANCH} (CUDA ${CUDA_VER}) and toolkit..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nvidia-headless-"${DRIVER_BRANCH}" \
    nvidia-utils-"${DRIVER_BRANCH}" \
    nvidia-container-toolkit \
    hwinfo || {
    echo "    Warning: branch ${DRIVER_BRANCH} not found, falling back to 610..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      nvidia-headless-610 nvidia-utils-610 nvidia-container-toolkit hwinfo
  }
}

configure_nvidia_cdi() {
  echo "==> Generating CDI specifications for Blackwell/Ada hardware..."
  sudo mkdir -p /etc/cdi
  if command -v nvidia-ctk >/dev/null 2>&1; then
    if ! sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml; then
      echo "    nvidia-ctk cdi generate returned non-zero; /etc/cdi/nvidia.yaml was not written at build time." >&2
    fi
    if ! sudo nvidia-ctk runtime configure --runtime=containerd --mode=cdi; then
      echo "    nvidia-ctk runtime configure returned non-zero; containerd was not switched to CDI mode." >&2
    fi
  fi
  sudo usermod -aG render,video ubuntu
}

main() {
  setup_nvidia_repositories
  install_bleeding_driver
  configure_nvidia_cdi
  echo "==> 36-gpu-nvidia-bleeding: Complete."
}

main "$@"
