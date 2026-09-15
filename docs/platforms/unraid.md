# Unraid VM & VirtFS Integration Guide

All `lusoris-cloud-images` flavors are engineered for seamless operation in Unraid's KVM environment.

## 1. Importing the Image to Unraid

1. Download and decompress the release image into your Unraid domains share:
   ```bash
   cd /mnt/user/domains/my-appliance/
   curl -fsSL https://github.com/cordanaLLM/imago/releases/latest/download/lusoris-cloud-docker-generic.qcow2.zst | zstdcat > vdisk1.qcow2
   ```
2. In the Unraid Web GUI:
   - Navigate to **VMs -> Add VM -> Linux**.
   - **Primary vDisk Location**: Select **Manual** and browse to `/mnt/user/domains/my-appliance/vdisk1.qcow2`.
   - **Primary vDisk Bus**: `VirtIO` (or `SATA`).
   - **Network Bridge**: `br0` (VirtIO).
   - **Graphics / Sound**: VNC or GPU Passthrough.

## 2. Guest Agent & ACPI Clean Shutdown

- `qemu-guest-agent` is pre-installed and enabled. Once the VM boots, its IP address appears directly in the Unraid VM management table.
- `acpid` is installed, ensuring that clicking **Stop** in the Unraid GUI triggers a clean, graceful ACPI shutdown.

## 3. Host Share Passthrough (VirtFS & virtiofs)

All `lusoris-cloud-images` kernels load `9p`, `9pnet`, and `virtiofs` modules at boot.

### Using virtiofs:
1. In Unraid VM settings, add a **virtiofs** share tag:
   - **Share Name**: `media`
   - **Source Path**: `/mnt/user/data`
2. Inside the guest VM:
   ```bash
   sudo mkdir -p /mnt/unraid
   sudo mount -t virtiofs media /mnt/unraid
   ```
3. To mount automatically on boot, add to `/etc/fstab`:
   ```text
   media  /mnt/unraid  virtiofs  defaults,_netdev  0  0
   ```

