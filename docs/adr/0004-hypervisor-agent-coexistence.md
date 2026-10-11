# ADR 0004: Hypervisor Guest Agent Coexistence (QEMU + VMware)

## Status

Accepted

## Context

Operators run images on a mix of hypervisors: Proxmox VE, Unraid, and VMware ESXi. Maintaining distinct image builds solely for guest agents creates unnecessary build explosion.

## Decision

We install both `qemu-guest-agent` and `open-vm-tools` in all base images via `05-hypervisor-agents.sh`. Both daemons check hypervisor DMI/udev conditions and remain dormant with zero CPU utilization when their respective hypervisor is absent. Additionally, Unraid `virtiofs` and `9p` kernel modules are pre-loaded at boot.

## Consequences

- A single `.qcow2` or `.vmdk` image boots with full telemetry and clean ACPI shutdowns on Proxmox, Unraid, and VMware ESXi without manual agent installation.
