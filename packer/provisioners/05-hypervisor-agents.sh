#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 05-hypervisor-agents.sh — Multi-hypervisor guest agents and Unraid VirtFS integration
# Coexistence of QEMU guest agent, VMware open-vm-tools, and Unraid host sharing.
set -euo pipefail

install_hypervisor_packages() {
  echo "==> Installing hypervisor guest agents and ACPI power management..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    qemu-guest-agent \
    open-vm-tools \
    spice-vdagent \
    acpid

  # hyperv-daemons is a Debian package name that not every Ubuntu archive publishes.
  if apt-cache show hyperv-daemons >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      hyperv-daemons
  else
    echo "    hyperv-daemons is not in the package index; no Hyper-V guest daemons are installed." >&2
  fi
}

configure_unraid_virtfs() {
  echo "==> Enabling Unraid virtiofs and 9p host-sharing kernel modules..."
  cat <<'EOF' | sudo tee /etc/modules-load.d/unraid-virtfs.conf
# Unraid & KVM Host-to-Guest Directory Passthrough
9p
9pnet
9pnet_virtio
virtiofs
EOF

  local module
  for module in 9p 9pnet 9pnet_virtio virtiofs; do
    if ! sudo modprobe "${module}"; then
      echo "    Module ${module} did not load in the build environment; it stays listed in modules-load.d." >&2
    fi
  done
}

configure_agent_services() {
  echo "==> Enabling hypervisor daemons with dormant condition guards..."
  # spice-vdagent needs no enable: its udev rule starts spice-vdagentd.socket when the
  # SPICE virtio port appears, and the package ships no system unit with an install section.
  local unit
  for unit in qemu-guest-agent.service open-vm-tools.service acpid.service; do
    sudo systemctl enable "${unit}"
  done

  sudo mkdir -p /etc/systemd/system/open-vm-tools.service.d
  cat <<'EOF' | sudo tee /etc/systemd/system/open-vm-tools.service.d/10-condition-virt.conf
[Unit]
ConditionVirtualization=vmware
EOF
}

main() {
  install_hypervisor_packages
  configure_unraid_virtfs
  configure_agent_services
  echo "==> 05-hypervisor-agents: Complete."
}

main "$@"
