#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 65-storage-cncf.sh — CNCF and homelab storage protocol preparation
# Installs and configures NVMe-oF (TCP), OpenZFS 2.3, iSCSI, multipath, and NFS.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

install_storage_packages() {
  echo "==> Installing CNCF storage protocol utilities..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    multipath-tools \
    nfs-common \
    nvme-cli \
    open-iscsi \
    zfsutils-linux
}

configure_nvme_over_fabrics() {
  echo "==> Enabling NVMe over TCP kernel module autoload..."
  sudo mkdir -p /etc/modules-load.d
  cat <<'EOF' | sudo tee /etc/modules-load.d/65-nvme-fabrics.conf >/dev/null
nvme-core
nvme-fabrics
nvme-tcp
EOF
}

configure_storage_services() {
  echo "==> Configuring multipath and iSCSI services..."
  sudo systemctl enable iscsid.service
  sudo systemctl enable multipathd.service

  # Set default multipath configuration if absent
  if [ ! -f /etc/multipath.conf ]; then
    cat <<'EOF' | sudo tee /etc/multipath.conf >/dev/null
defaults {
  user_friendly_names yes
  find_multipaths yes
}
EOF
  fi
}

main() {
  install_storage_packages
  configure_nvme_over_fabrics
  configure_storage_services
  echo "==> 65-storage-cncf: Complete."
}

main "$@"
