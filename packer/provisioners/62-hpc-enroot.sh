#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 62-hpc-enroot.sh — Install NVIDIA Enroot unprivileged container runtime for HPC/AI
# Consumes ENROOT_VERSION injected dynamically from versions.json.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

: "${ENROOT_VERSION:?ENROOT_VERSION environment variable must be set}"

install_enroot() {
  local version="${ENROOT_VERSION}"
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

  echo "==> Installing NVIDIA Enroot v${version} (${arch})..."
  local tmpdir
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT

  local base_url="https://github.com/NVIDIA/enroot/releases/download/v${version}"
  local deb_main="enroot_${version}-1_${arch}.deb"
  local deb_caps="enroot+caps_${version}-1_${arch}.deb"

  echo "==> Downloading ${deb_main}..."
  if ! curl -fsSL --max-time 30 "${base_url}/${deb_main}" -o "${tmpdir}/${deb_main}"; then
    echo "==> Failed to download ${deb_main} from ${base_url}/${deb_main}" >&2
    return 1
  fi

  echo "==> Downloading ${deb_caps}..."
  if ! curl -fsSL --max-time 30 "${base_url}/${deb_caps}" -o "${tmpdir}/${deb_caps}"; then
    echo "==> Failed to download ${deb_caps} from ${base_url}/${deb_caps}" >&2
    return 1
  fi

  echo "==> Installing enroot packages with apt-get..."
  if ! (cd "${tmpdir}" && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "./${deb_main}" "./${deb_caps}"); then
    echo "==> Failed to install enroot deb packages" >&2
    return 1
  fi

  rm -rf "${tmpdir}"
  trap - EXIT
}

verify_enroot() {
  echo "==> Verifying enroot version..."
  local installed_version
  if ! installed_version=$(enroot version 2>&1); then
    echo "==> enroot version failed: ${installed_version}" >&2
    return 1
  fi
  if [[ "${installed_version}" != "${ENROOT_VERSION}" ]]; then
    echo "==> enroot version check failed: expected '${ENROOT_VERSION}', got '${installed_version}'" >&2
    return 1
  fi
}

main() {
  install_enroot
  verify_enroot
  echo "==> 62-hpc-enroot: Complete."
}

main "$@"
