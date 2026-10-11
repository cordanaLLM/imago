# VMware ESXi & vSphere Deployment Guide

`lusoris-cloud-images` natively supports VMware ESXi, vSphere, and Workstation.

## Hypervisor Integration

- **`open-vm-tools` Pre-Installed**: The official VMware guest tools package is pre-baked into all images. It automatically activates when booted on a VMware hypervisor and handles heartbeat telemetry, IP reporting in vCenter, and graceful power management.
- **GuestInfo Cloud-Init Support**: Cloud-init includes the VMware `GuestInfo` datasource, allowing vSphere customization specifications to configure hostnames, networks, and SSH keys without requiring an external CD-ROM.

## Importing via vmkfstools on ESXi

```bash
# 1. Convert QCOW2 to monolithic VMDK on your workstation
qemu-img convert -O vmdk -o subformat=monolithicFlat image.qcow2 image-flat.vmdk

# 2. Upload image to ESXi datastore via SCP or Datastore Browser
scp image*.vmdk root@esxi-host.example.com:/vmfs/volumes/datastore1/my-vm/

# 3. Clone to thin-provisioned ESXi VMDK
vmkfstools -i /vmfs/volumes/datastore1/my-vm/image.vmdk -d thin /vmfs/volumes/datastore1/my-vm/disk.vmdk
```
