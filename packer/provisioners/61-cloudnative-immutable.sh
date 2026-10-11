#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 61-cloudnative-immutable.sh — Immutable container host tuning & drift prevention
# Implements read-only root protection, ephemeral tmpfs, and containerd CDI standards.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

configure_tmpfs_mounts() {
  echo "==> Configuring volatile tmpfs mounts for /tmp and /var/tmp..."
  # tmp.mount is a loadable unit only on releases that ship it in the unit path;
  # elsewhere the fstab entry below is what mounts /tmp.
  if systemctl cat tmp.mount >/dev/null 2>&1; then
    sudo systemctl enable tmp.mount
  else
    echo "    tmp.mount is not a loadable unit here; /tmp is mounted from the fstab entry." >&2
  fi

  # Add hardened tmpfs mount options in fstab if not present
  if ! grep -q "tmpfs /tmp" /etc/fstab; then
    echo "tmpfs /tmp tmpfs rw,nosuid,nodev,noexec,relatime,size=2G 0 0" | sudo tee -a /etc/fstab
  fi
}

configure_immutable_security() {
  echo "==> Hardening system against runtime configuration drift..."
  # Configure systemd to protect system paths
  sudo mkdir -p /etc/systemd/system.conf.d
  cat <<'EOF' | sudo tee /etc/systemd/system.conf.d/50-immutable.conf >/dev/null
[Manager]
DefaultProtectSystem=strict
DefaultProtectHome=read-only
DefaultPrivateTmp=yes
EOF

  # Lock down apt auto-updates to prevent untracked drift in production
  cat <<'EOF' | sudo tee /etc/apt/apt.conf.d/99-immutable-prevent-drift >/dev/null
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
APT::Periodic::Download-Upgradeable-Packages "0";
APT::Periodic::AutocleanInterval "0";
EOF
}

configure_container_runtime_cdi() {
  echo "==> Pre-configuring Container Device Interface (CDI) directories..."
  sudo mkdir -p /etc/cdi
  sudo mkdir -p /var/run/cdi
  sudo chmod 755 /etc/cdi /var/run/cdi
}

main() {
  configure_tmpfs_mounts
  configure_immutable_security
  configure_container_runtime_cdi
  echo "==> 61-cloudnative-immutable: Complete."
}

main "$@"
