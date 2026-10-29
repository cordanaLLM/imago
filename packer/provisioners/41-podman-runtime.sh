#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 41-podman-runtime.sh — Install Podman 5.x, Buildah, Skopeo, and Quadlet systemd support
# Configures daemonless, rootless container stack with automated Quadlet generators.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

CDEBUG_VERSION="${CDEBUG_VERSION:-0.0.19}"
CRUN_VERSION="${CRUN_VERSION:?CRUN_VERSION must come from versions.json}"

install_podman_packages() {
  echo "==> Installing Podman, Buildah, Skopeo, Netavark, and crun on Ubuntu 26.04..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    podman \
    buildah \
    skopeo \
    crun \
    netavark \
    aardvark-dns \
    slirp4netns \
    uidmap
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

configure_quadlet_and_rootless() {
  echo "==> Configuring Quadlet systemd directory and rootless subordinate IDs..."
  sudo mkdir -p /etc/containers/systemd
  sudo mkdir -p /home/ubuntu/.config/containers/systemd

  if ! grep -q "^ubuntu:" /etc/subuid 2>/dev/null; then
    echo "ubuntu:100000:65536" | sudo tee -a /etc/subuid
  fi
  if ! grep -q "^ubuntu:" /etc/subgid 2>/dev/null; then
    echo "ubuntu:100000:65536" | sudo tee -a /etc/subgid
  fi

  sudo chown -R ubuntu:ubuntu /home/ubuntu/.config
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
  install_podman_packages
  verify_crun_version
  configure_quadlet_and_rootless
  install_cdebug
  echo "==> 41-podman-runtime: Complete."
}

main "$@"
