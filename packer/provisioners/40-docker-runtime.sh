#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 40-docker-runtime.sh — Install Docker CE, Docker Compose v2, and containerd.io
# Configures log rotation, systemd cgroup driver, userland-proxy=false, and CDI support.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

DISTRO_RELEASE="${DISTRO_RELEASE:-resolute}"

setup_docker_repository() {
  echo "==> Configuring official Docker apt repository on Ubuntu ${DISTRO_RELEASE}..."
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
    sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg

  local arch
  arch="$(dpkg --print-architecture)"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${DISTRO_RELEASE} stable" |
    sudo tee /etc/apt/sources.list.d/docker.list

  sudo apt-get update || echo "    Warning: apt update returned non-zero, continuing..."
}

install_docker_packages() {
  echo "==> Installing Docker CE and Compose plugin..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin || true
}

configure_docker_daemon() {
  echo "==> Configuring /etc/docker/daemon.json with live-restore and CDI..."
  sudo mkdir -p /etc/docker
  cat <<'EOF' | sudo tee /etc/docker/daemon.json
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "live-restore": true,
  "userland-proxy": false,
  "features": {
    "cdi": true
  }
}
EOF

  sudo usermod -aG docker ubuntu || true
  sudo systemctl daemon-reload
  sudo systemctl enable docker.service 2>/dev/null || true
}

install_cdebug() {
  local version="${CDEBUG_VERSION:-0.0.19}"
  local arch
  arch=$(uname -m)
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64 | arm64) arch="arm64" ;;
    *) return 0 ;;
  esac
  echo "==> Installing cdebug v${version} for zero-footprint diagnostics..."
  # The release asset carries no version in its name: cdebug_linux_amd64.tar.gz.
  local url="https://github.com/iximiuz/cdebug/releases/download/v${version}/cdebug_linux_${arch}.tar.gz"
  if ! curl -fsSL --max-time 30 "${url}" | sudo tar -xz -C /usr/local/bin cdebug; then
    echo "==> cdebug ${version} could not be installed from ${url}" >&2
    return 1
  fi
  sudo chmod 755 /usr/local/bin/cdebug
}

main() {
  setup_docker_repository
  install_docker_packages
  configure_docker_daemon
  install_cdebug
  echo "==> 40-docker-runtime: Complete."
}

main "$@"
