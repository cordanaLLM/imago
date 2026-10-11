# NAS & Storage Appliances Integration Guide

> Comprehensive operating guide for deploying, optimizing, and interconnecting `lusoris-cloud-images` with open-source and commercial Network Attached Storage (NAS) platforms.

---

## 1. Open-Source NAS Platforms

### 1.1 OpenMediaVault (OMV)

OpenMediaVault is a Debian-based NAS solution popular in lightweight homelab environments.

- **OMV-KVM Virtualization**:
  - The `openmediavault-kvm` (Cockpit Machines) plugin runs standard QEMU/KVM virtual machines.
  - Download the `.qcow2.zst` artifact into the OMV storage pool:

    ```bash
    zstdcat lusoris-cloud-docker-generic.qcow2.zst > /srv/dev-disk-by-uuid-.../vms/docker-node.qcow2
    ```

  - Attach via Cockpit UI with VirtIO bus and network bridge.
- **Client Mount Optimization**:
  - OMV SMB/NFS exports mount inside Lusoris guests with optimized readahead:

    ```bash
    sudo blockdev --setra 4096 /dev/vda
    ```

### 1.2 CasaOS & ZimaOS (Container-First Home Cloud)

IceWhale's CasaOS and ZimaOS deliver a Docker-first personal cloud experience.

- **Storage Aggregation**:
  - CasaOS aggregates disks via `mergerfs`. Lusoris appliances (`appliance-media-server`, `docker-generic`) can mount CasaOS mergerfs pools over NFSv4.2 or SMB 3.1.1.
- **`appliance-home-cloud` Flavor Roadmap**:
  - Packages a turnkey, hardened Docker CE personal cloud environment with native ZFS / Btrfs subvolume management and CasaOS-compatible App Store APIs.

---

## 2. Commercial Virtual NAS Appliances

### 2.1 QNAP QTScloud

QNAP QTScloud is the official virtualized operating system from QNAP, deploying as a virtual appliance on Proxmox VE, VMware ESXi, Hyper-V, and cloud providers.

- **Architecture with Lusoris**:
  - QTScloud manages raw storage disks (via HBA/PCI passthrough or dedicated virtual disks).
  - Lusoris Kubernetes nodes (`k8s-node-*`) and container hosts (`docker-*`) consume block and file storage from QTScloud via:
    - **iSCSI Target**: Block devices mapped directly to containerd / kubelet via `open-iscsi`.
    - **NFSv4.2**: High-throughput file sharing with ACLs enabled.
- **Client Tuning**:

  ```bash
  # Enable iSCSI daemon and auto-discovery
  sudo systemctl enable --now iscsid
  sudo iscsiadm -m discovery -t sendtargets -p qtscloud.example.com
  ```

### 2.2 Synology Virtual DSM (vDSM)

Synology vDSM runs DSM inside Synology Virtual Machine Manager (VMM) or nested within KVM.

- **Synology VMM Guest Compatibility**:
  - Lusoris images include `qemu-guest-agent`, which is fully compatible with Synology VMM for IP reporting and clean ACPI shutdown.
- **Synology CSI for Kubernetes**:
  - Lusoris Kubernetes flavors (`k8s-node-*`) seamlessly integrate with the Synology CSI driver for dynamic PersistentVolume allocation backed by DSM Storage Pools.

### 2.3 StarWind SAN & NAS

StarWind SAN & NAS is an enterprise-grade virtual storage appliance designed for VMware vSphere and Proxmox VE, offering dual-controller high availability.

- **NVMe-oF (TCP) & iSCSI Multipathing**:
  - Lusoris `cloudnative-storage` and `k8s-node-*` flavors feature pre-installed `multipath-tools` and `nvme-cli`.
  - Configured for active-active round-robin path failover across redundant 10GbE / 25GbE storage networks.

---

## 3. Dedicated Lusoris Storage Appliance: `appliance-nas-zfs`

For operators seeking an ultra-lean, hardened, enterprise ZFS storage appliance without commercial software overhead:

- **Core Engine**: OpenZFS 2.3+ kernel modules, Samba 4.20+, NFSv4.2 kernel server, targetcli (iSCSI LIO), and SPDK NVMe-oF target.
- **Management Web GUI**: Cockpit with 45Drives Houston and Cockpit-ZFS-Manager for declarative dataset, snapshot, and share administration.
- **Automated Data Protection**:
  - Automated atomic snapshots via `sanoid` (hourly/daily/monthly retention).
  - Snapshot replication via `syncoid`.
  - Automated weekly ZFS scrub timer (`zfs-scrub.timer`).
