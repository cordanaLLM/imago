#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 98-structure-test.sh — In-guest filesystem verification via container-structure-test
# Runs Google container-structure-test with host driver against flavor configurations.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

: "${CST_VERSION:?CST_VERSION environment variable must be set}"
: "${FLAVOR:?FLAVOR environment variable must be set}"

TMPDIR_CST=""

cleanup() {
  echo "==> Cleaning up container-structure-test artifacts..."
  sudo rm -f /usr/local/bin/container-structure-test
  sudo rm -rf /tmp/structure-tests
  if [ -n "${TMPDIR_CST:-}" ] && [ -d "${TMPDIR_CST}" ]; then
    rm -rf "${TMPDIR_CST}"
  fi
}
trap cleanup EXIT

install_cst() {
  local version="${CST_VERSION}"
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

  echo "==> Installing container-structure-test v${version} (${arch})..."
  TMPDIR_CST=$(mktemp -d)

  local base_url="https://github.com/GoogleContainerTools/container-structure-test/releases/download/v${version}"
  local binary="container-structure-test-linux-${arch}"
  local checksums_file="checksums.txt"

  echo "==> Downloading ${binary}..."
  if ! curl -fsSL --max-time 30 "${base_url}/${binary}" -o "${TMPDIR_CST}/${binary}"; then
    echo "==> Failed to download container-structure-test binary from ${base_url}/${binary}" >&2
    return 1
  fi

  echo "==> Downloading ${checksums_file}..."
  if ! curl -fsSL --max-time 30 "${base_url}/${checksums_file}" -o "${TMPDIR_CST}/${checksums_file}"; then
    echo "==> Failed to download checksums from ${base_url}/${checksums_file}" >&2
    return 1
  fi

  echo "==> Verifying checksum for ${binary}..."
  local match_line
  if ! match_line=$(grep -E "[[:space:]]${binary}\$" "${TMPDIR_CST}/${checksums_file}"); then
    echo "==> Asset ${binary} not found in ${checksums_file}" >&2
    return 1
  fi

  if [ -z "${match_line}" ]; then
    echo "==> Checksum line for ${binary} is empty" >&2
    return 1
  fi

  if ! (cd "${TMPDIR_CST}" && echo "${match_line}" | sha256sum -c -); then
    echo "==> Checksum verification failed for ${binary}" >&2
    return 1
  fi

  echo "==> Installing container-structure-test binary to /usr/local/bin..."
  if ! sudo install -m 0755 "${TMPDIR_CST}/${binary}" /usr/local/bin/container-structure-test; then
    echo "==> Failed to install container-structure-test to /usr/local/bin" >&2
    return 1
  fi

  rm -rf "${TMPDIR_CST}"
  TMPDIR_CST=""
}

run_structure_tests() {
  local configs=("/tmp/structure-tests/common.yaml")

  if [ -f /etc/systemd/system/stargz-snapshotter.service ]; then
    echo "==> Detected stargz-snapshotter service marker; adding k8s.yaml..."
    configs+=("/tmp/structure-tests/k8s.yaml")
  fi

  if command -v enroot >/dev/null 2>&1; then
    echo "==> Detected enroot binary marker; adding enroot.yaml..."
    configs+=("/tmp/structure-tests/enroot.yaml")
  fi

  local config_args=()
  local cfg
  for cfg in "${configs[@]}"; do
    if [ ! -f "${cfg}" ]; then
      echo "==> Required structure test configuration missing: ${cfg}" >&2
      return 1
    fi
    config_args+=(--config "${cfg}")
  done

  echo "==> Executing container-structure-test for flavor '${FLAVOR}'..."
  if ! sudo container-structure-test test --driver host --force --metadata /dev/null "${config_args[@]}"; then
    echo "==> Container structure tests failed for flavor '${FLAVOR}'" >&2
    return 1
  fi
  echo "==> Container structure tests passed successfully for flavor '${FLAVOR}'."
}

main() {
  install_cst
  run_structure_tests
  echo "==> 98-structure-test: Complete."
}

main "$@"
