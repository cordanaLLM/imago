#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 99-cleanup.sh — Template sanitization, security cleanup, and thin-provision trimming
# Ensures clean first boot, password lock, regenerated machine-id, and minimal disk footprint.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

clean_cloud_init_and_auth() {
  echo "==> Sanitizing cloud-init state..."
  sudo cloud-init clean --logs --seed || true

  echo "==> Enforcing PasswordAuthentication no on final snapshot sealing..."
  echo "PasswordAuthentication no" | sudo tee -a /etc/ssh/sshd_config.d/00-hardened-sshd.conf
  sudo chmod 0600 /etc/ssh/sshd_config.d/00-hardened-sshd.conf

  echo "==> Restricting low-level binary permissions..."
  sudo chmod 0700 /usr/bin/as /usr/bin/byacc 2>/dev/null || true
}

clean_apt_cache() {
  echo "==> Cleaning apt caches and index files..."
  sudo apt-get autoremove --purge -y || true
  sudo apt-get clean
  sudo rm -rf /var/lib/apt/lists/*
}

clean_machine_identities() {
  echo "==> Resetting machine-id and regenerating on next boot..."
  sudo truncate -s 0 /etc/machine-id
  sudo rm -f /var/lib/dbus/machine-id
  sudo ln -sf /etc/machine-id /var/lib/dbus/machine-id

  echo "==> Removing host SSH keys for unique regeneration on first boot..."
  sudo rm -f /etc/ssh/ssh_host_*
}

clean_logs_and_histories() {
  echo "==> Truncating log files and clearing bash histories..."
  sudo rm -f /root/.bash_history /home/ubuntu/.bash_history
  sudo journalctl --rotate 2>/dev/null || true
  sudo journalctl --vacuum-time=1s 2>/dev/null || true
  sudo rm -rf /var/log/journal/*

  sudo find /var/log -type f -exec truncate -s 0 {} \; 2>/dev/null || true
  sudo rm -rf /tmp/* /var/tmp/*
}

zero_free_space() {
  echo "==> Zero-filling unallocated blocks for sparse compression..."
  sudo dd if=/dev/zero of=/EMPTY bs=1M status=none 2>/dev/null || true
  sudo sync
  sudo rm -f /EMPTY
  echo "==> Running fstrim to reclaim thin-provisioned storage..."
  sudo fstrim -av 2>/dev/null || true
}

# The build account is not sealed here. Locking its password and removing its sudoers
# grant is done by the builder's shutdown_command, which is the last privileged act of
# the build: it authenticates with the build password, so sealing before it would make
# the machine unable to power off, and there is nothing after it to seal from.
# See shutdown_command in packer/sources.pkr.hcl.

main() {
  clean_cloud_init_and_auth
  clean_apt_cache
  clean_machine_identities
  clean_logs_and_histories
  zero_free_space
  echo "==> 99-cleanup: Template cleanup complete."
}

main "$@"
