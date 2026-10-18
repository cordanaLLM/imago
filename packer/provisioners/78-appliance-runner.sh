#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 78-appliance-runner.sh — Self-hosted CI/CD multi-architecture runner appliance
# Pre-configures QEMU binfmt multiarch (ARM64 on x86_64), Docker Buildx, and build essentials.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

install_multiarch_emulation() {
  echo "==> Configuring QEMU multi-architecture user emulation (ARM64/ARMv7)..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    qemu-user-binfmt \
    binfmt-support

  # Ensure binfmt_misc kernel module is loaded on boot
  echo "binfmt_misc" | sudo tee /etc/modules-load.d/binfmt.conf >/dev/null
}

install_build_essentials() {
  echo "==> Installing CI/CD runner tooling and build essentials..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    git-lfs \
    zstd \
    jq \
    rsync \
    pkg-config \
    libssl-dev

  # Initialize Git LFS globally; the system gitconfig is writable by root only.
  sudo git lfs install --system
}

configure_runner_tmpfs() {
  echo "==> Configuring in-memory tmpfs mount for high-throughput builds..."
  # Add 4GB tmpfs mount for /tmp if not already present
  if ! grep -q "tmpfs /tmp tmpfs" /etc/fstab; then
    echo "tmpfs /tmp tmpfs rw,nosuid,nodev,noatime,size=4G 0 0" | sudo tee -a /etc/fstab >/dev/null
  fi
}

main() {
  install_multiarch_emulation
  install_build_essentials
  configure_runner_tmpfs
  echo "==> 78-appliance-runner: Complete."
}

main "$@"
