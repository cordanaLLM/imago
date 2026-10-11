#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 77-appliance-media.sh — Jellyfin, Plex, and Tdarr high-throughput transcoding appliance
# Dual-vendor VA-API drivers (Intel QuickSync + AMD Mesa), NAS mount tools, and streaming readahead.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

install_dual_vendor_vaapi() {
  echo "==> Configuring dual-vendor hardware acceleration (Intel + AMD VA-API)..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    intel-media-va-driver-non-free \
    mesa-va-drivers \
    mesa-vulkan-drivers \
    vainfo \
    libva-drm2 \
    libva2

  # Ensure consistent render and video group membership
  sudo usermod -aG render,video ubuntu
}

install_nas_storage_clients() {
  echo "==> Installing network storage client packages (NFS & CIFS/SMB)..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nfs-common \
    cifs-utils \
    autofs \
    fuse3
}

tune_disk_streaming_readahead() {
  echo "==> Configuring 4096KB block readahead for continuous media streaming..."
  cat <<'RULES' | sudo tee /etc/udev/rules.d/60-readahead.rules >/dev/null
SUBSYSTEM=="block", ACTION=="add|change", ATTR{bdi/read_ahead_kb}="4096"
RULES

  # Apply streaming kernel buffer defaults
  cat <<'SYSCTL' | sudo tee /etc/sysctl.d/99-media-streaming.conf >/dev/null
fs.inotify.max_user_watches = 524288
fs.file-max = 2097152
SYSCTL
}

main() {
  install_dual_vendor_vaapi
  install_nas_storage_clients
  tune_disk_streaming_readahead
  echo "==> 77-appliance-media: Complete."
}

main "$@"
