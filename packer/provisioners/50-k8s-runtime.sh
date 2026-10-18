#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 50-k8s-runtime.sh — Install containerd CRI runtime and Kubernetes node components
# Consumes K8S_MAJOR_MINOR injected dynamically from versions.json (Ubuntu 26.04).
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

K8S_MAJOR_MINOR="${K8S_MAJOR_MINOR:-1.37}"
IMG_PAUSE="${IMG_PAUSE:-registry.k8s.io/pause:3.10}"
CDEBUG_VERSION="${CDEBUG_VERSION:?CDEBUG_VERSION must come from versions.json}"

setup_containerd() {
  echo "==> Installing and configuring containerd 2.3+ with CRI and crun..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends containerd crun

  sudo mkdir -p /etc/containerd
  sudo containerd config default | sudo tee /etc/containerd/config.toml >/dev/null

  # Enable systemd cgroup driver and set pause sandbox image
  sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
  sudo sed -i "s|sandbox_image = .*|sandbox_image = \"${IMG_PAUSE}\"|" /etc/containerd/config.toml
  sudo sed -i 's/discard_unpacked_layers = false/discard_unpacked_layers = true/' /etc/containerd/config.toml

  # Register crun as alternative high-performance OCI runtime class (containerd 2.x & 1.x compatible)
  if grep -q 'io.containerd.cri.v1.runtime' /etc/containerd/config.toml; then
    cat <<'EOF' | sudo tee -a /etc/containerd/config.toml

[plugins."io.containerd.cri.v1.runtime".containerd.runtimes.crun]
  runtime_type = "io.containerd.runc.v2"
  runtime_engine = ""
  runtime_root = ""
  [plugins."io.containerd.cri.v1.runtime".containerd.runtimes.crun.options]
    BinaryName = "crun"
    SystemdCgroup = true
EOF
  else
    cat <<'EOF' | sudo tee -a /etc/containerd/config.toml

[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.crun]
  runtime_type = "io.containerd.runc.v2"
  runtime_engine = ""
  runtime_root = ""
  [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.crun.options]
    BinaryName = "crun"
    SystemdCgroup = true
EOF
  fi

  # Configure default crictl endpoint
  cat <<'EOF' | sudo tee /etc/crictl.yaml
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 10
debug: false
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable --now containerd
}

setup_kubernetes_packages() {
  echo "==> Setting up Kubernetes official repository (v${K8S_MAJOR_MINOR})..."
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL --max-time 30 "https://pkgs.k8s.io/core:/stable:/v${K8S_MAJOR_MINOR}/deb/Release.key" |
    sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

  echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${K8S_MAJOR_MINOR}/deb/ /" |
    sudo tee /etc/apt/sources.list.d/kubernetes.list

  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    kubelet \
    kubeadm \
    kubectl

  sudo apt-mark hold kubelet kubeadm kubectl
  sudo systemctl enable kubelet
}

install_cdebug() {
  local version="${CDEBUG_VERSION}"
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
  setup_containerd
  setup_kubernetes_packages
  install_cdebug
  echo "==> 50-k8s-runtime: Complete."
}

main "$@"
