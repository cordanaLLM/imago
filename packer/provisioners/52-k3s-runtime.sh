#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 52-k3s-runtime.sh — Install K3s lightweight Kubernetes engine for edge & homelabs
# Consumes K3S_VERSION and K3S_ROLE injected dynamically from versions.json.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

K3S_VERSION="${K3S_VERSION:-v1.36.4+k3s1}"
K3S_ROLE="${K3S_ROLE:-agent}"

setup_k3s_prerequisites() {
  echo "==> Setting up K3s prerequisites and directories..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    conntrack \
    ebtables \
    ethtool \
    iptables \
    socat

  sudo mkdir -p /etc/rancher/k3s
  sudo mkdir -p /etc/rancher/k3s/config.yaml.d
  sudo mkdir -p /var/lib/rancher/k3s
  sudo mkdir -p /etc/cdi
}

install_k3s_binaries() {
  echo "==> Installing K3s ${K3S_VERSION} (${K3S_ROLE} role)..."
  local install_script
  install_script=$(mktemp)

  curl -fsSL --max-time 60 https://get.k3s.io -o "${install_script}"
  chmod +x "${install_script}"

  if [ "${K3S_ROLE}" = "server" ]; then
    INSTALL_K3S_SKIP_START=true \
      INSTALL_K3S_VERSION="${K3S_VERSION}" \
      sh "${install_script}"
  else
    INSTALL_K3S_SKIP_START=true \
      INSTALL_K3S_VERSION="${K3S_VERSION}" \
      INSTALL_K3S_EXEC="agent" \
      sh "${install_script}"
  fi

  rm -f "${install_script}"
}

configure_k3s_defaults() {
  echo "==> Configuring K3s registries and containerd CDI integration..."
  cat <<'EOF' | sudo tee /etc/rancher/k3s/registries.yaml >/dev/null
mirrors:
  docker.io:
    endpoint:
      - "https://registry-1.docker.io"
EOF

  # Pre-configure containerd template directory for CDI
  sudo mkdir -p /var/lib/rancher/k3s/agent/etc/containerd
  cat <<'EOF' | sudo tee /etc/rancher/k3s/config.yaml.d/10-default.yaml >/dev/null
# Lusoris K3s baseline configuration
protect-kernel-defaults: true
EOF

  # Keep service stopped until cloud-init provisions credentials/token on first boot
  if systemctl list-unit-files | grep -q "k3s-agent.service"; then
    sudo systemctl disable k3s-agent.service
  fi
  if systemctl list-unit-files | grep -q "k3s.service"; then
    sudo systemctl disable k3s.service
  fi
}

main() {
  setup_k3s_prerequisites
  install_k3s_binaries
  configure_k3s_defaults
  echo "==> 52-k3s-runtime: K3s ${K3S_VERSION} installation complete (${K3S_ROLE})."
}

main "$@"
