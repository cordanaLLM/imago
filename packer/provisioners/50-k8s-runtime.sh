#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 50-k8s-runtime.sh — Install containerd CRI runtime and Kubernetes node components
# Consumes K8S_MAJOR_MINOR, K8S_VERSION and CRUN_VERSION injected from versions.json (Ubuntu 26.04).
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

K8S_MAJOR_MINOR="${K8S_MAJOR_MINOR:-1.37}"
K8S_VERSION="${K8S_VERSION:?K8S_VERSION must come from versions.json}"
CRUN_VERSION="${CRUN_VERSION:?CRUN_VERSION must come from versions.json}"
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

# crun comes from the distribution archive; runtimes.crun in versions.json is the lowest
# release the image accepts, so an archive older than the pin fails the build.
verify_crun_version() {
  local installed
  installed="$(dpkg-query -W -f='${Version}' crun)"
  if ! dpkg --compare-versions "${installed}" ge "${CRUN_VERSION}"; then
    echo "crun ${installed} from the archive is older than the pinned ${CRUN_VERSION}" >&2
    return 1
  fi
  echo "    crun ${installed} satisfies the pin ${CRUN_VERSION}."
}

setup_kubernetes_packages() {
  echo "==> Setting up Kubernetes official repository (v${K8S_MAJOR_MINOR})..."
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL --max-time 30 "https://pkgs.k8s.io/core:/stable:/v${K8S_MAJOR_MINOR}/deb/Release.key" |
    sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

  echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${K8S_MAJOR_MINOR}/deb/ /" |
    sudo tee /etc/apt/sources.list.d/kubernetes.list

  sudo apt-get update
  # pkgs.k8s.io versions read <patch>-<revision> (1.37.0-1.1); the glob pins the patch release.
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "kubelet=${K8S_VERSION}-*" \
    "kubeadm=${K8S_VERSION}-*" \
    "kubectl=${K8S_VERSION}-*"

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
  verify_crun_version
  setup_kubernetes_packages
  install_cdebug
  echo "==> 50-k8s-runtime: Complete."
}

main "$@"
