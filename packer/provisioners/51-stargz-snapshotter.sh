#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 51-stargz-snapshotter.sh — Install stargz-snapshotter for on-demand lazy image pulling
# Consumes STARGZ_VERSION injected dynamically from versions.json.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

: "${STARGZ_VERSION:?STARGZ_VERSION environment variable must be set}"

install_stargz_snapshotter() {
  local version="${STARGZ_VERSION}"
  local arch
  arch=$(uname -m)
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64 | arm64) arch="arm64" ;;
    *)
      echo "==> Unsupported architecture: ${arch}" >&2
      return 1
      ;;
  esac

  echo "==> Installing stargz-snapshotter v${version} (${arch})..."
  local tmpdir
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT

  local base_url="https://github.com/containerd/stargz-snapshotter/releases/download/v${version}"
  local tarball="stargz-snapshotter-v${version}-linux-${arch}.tar.gz"
  local sha_file="${tarball}.sha256sum"

  echo "==> Downloading ${tarball}..."
  if ! curl -fsSL --max-time 30 "${base_url}/${tarball}" -o "${tmpdir}/${tarball}"; then
    echo "==> Failed to download stargz-snapshotter tarball from ${base_url}/${tarball}" >&2
    return 1
  fi

  echo "==> Downloading ${sha_file}..."
  if ! curl -fsSL --max-time 30 "${base_url}/${sha_file}" -o "${tmpdir}/${sha_file}"; then
    echo "==> Failed to download stargz-snapshotter checksum from ${base_url}/${sha_file}" >&2
    return 1
  fi

  echo "==> Verifying checksum for ${tarball}..."
  if ! (cd "${tmpdir}" && sha256sum -c "${sha_file}"); then
    echo "==> Checksum verification failed for ${tarball}" >&2
    return 1
  fi

  echo "==> Installing stargz binaries to /usr/local/bin..."
  if ! sudo tar -xzf "${tmpdir}/${tarball}" -C /usr/local/bin; then
    echo "==> Failed to extract stargz binaries to /usr/local/bin" >&2
    return 1
  fi

  sudo chmod 755 \
    /usr/local/bin/containerd-stargz-grpc \
    /usr/local/bin/ctr-remote \
    /usr/local/bin/stargz-fuse-manager \
    /usr/local/bin/stargz-store \
    /usr/local/bin/stargz-store-helper

  rm -rf "${tmpdir}"
  trap - EXIT
}

configure_stargz_service() {
  echo "==> Configuring stargz-snapshotter service..."
  sudo mkdir -p /etc/containerd-stargz-grpc
  if [ ! -f /etc/containerd-stargz-grpc/config.toml ]; then
    sudo touch /etc/containerd-stargz-grpc/config.toml
  fi

  cat <<'EOF' | sudo tee /etc/systemd/system/stargz-snapshotter.service >/dev/null
[Unit]
Description=stargz-snapshotter
Documentation=https://github.com/containerd/stargz-snapshotter
Before=containerd.service

[Service]
Type=notify
Environment=HOME=/root
ExecStart=/usr/local/bin/containerd-stargz-grpc --log-level=info --config=/etc/containerd-stargz-grpc/config.toml
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable stargz-snapshotter
}

configure_containerd_proxy_plugin() {
  echo "==> Configuring containerd proxy plugin for stargz..."
  sudo mkdir -p /etc/containerd
  if [ ! -f /etc/containerd/config.toml ]; then
    sudo touch /etc/containerd/config.toml
  fi

  if ! grep -q 'proxy_plugins.stargz' /etc/containerd/config.toml; then
    cat <<'EOF' | sudo tee -a /etc/containerd/config.toml

[proxy_plugins.stargz]
  type = "snapshot"
  address = "/run/containerd-stargz-grpc/containerd-stargz-grpc.sock"
EOF
  fi
}

main() {
  install_stargz_snapshotter
  configure_stargz_service
  configure_containerd_proxy_plugin
  echo "==> 51-stargz-snapshotter: Complete."
}

main "$@"
