# 18. Open-Source and Virtual Network Attached Storage (NAS) Ecosystem Architecture

Date: 2026-09-10

## Status

Accepted

## Context

Network Attached Storage (NAS) systems form the primary persistent storage backbone across homelab, enterprise edge, and on-premises datacenter deployments. Operators broadly utilize two classes of NAS platforms:

1. **Open-Source & Community Solutions**: TrueNAS SCALE (Debian/Linux ZFS), Unraid (Lime Tech XFS/Btrfs array), OpenMediaVault (OMV Debian-based), and container-first platforms like CasaOS / ZimaOS.
2. **Commercial & Virtual NAS Appliances**: QNAP QTScloud, Synology Virtual DSM (vDSM), and enterprise hyper-converged storage appliances like StarWind SAN & NAS.

In these environments, operating system images interact with NAS platforms in two distinct operational modes:

- **Inbound Guest Mode**: Running Lusoris virtual machines on top of the NAS host hypervisor (TrueNAS KVM, Unraid KVM, Synology VMM, QNAP Virtualization Station).
- **Outbound Storage Consumer Mode**: Running compute nodes (Docker, Kubernetes, AI inference) that consume block (iSCSI, NVMe-oF) and file (NFSv4.2, SMB 3.1.1) storage exported by the NAS.
- **Turnkey Storage Appliance Mode**: Providing dedicated, hardened OS images that act as the storage server itself, eliminating heavy proprietary bloat while preserving enterprise ZFS integrity.

## Decision

We establish an architectural framework formalizing NAS integration across three dimensions:

### 1. Dual-Mode Operational Strategy

- **Mode A (Inbound Guest Optimization)**:
  - All 44 Lusoris flavors are pre-baked with `qemu-guest-agent`, `acpid`, and VirtIO drivers.
  - Linux kernels load `virtiofs`, `9p`, and `9pnet` kernel modules at boot for instant Unraid and KVM host-to-guest directory sharing.
  - NFSv4.2 client-side persistent caching (`fscache` / `cachefilesd`) and SMB 3.1.1 multi-channel bonding are pre-configured to maximize bandwidth across 10GbE / 25GbE NAS connections.
- **Mode B (Outbound Storage Appliance Flavors)**:
  - We formalize two specialized appliance flavors:
    - **`appliance-nas-zfs`**: A hardened headless/Cockpit-managed storage appliance combining OpenZFS 2.3+, Samba 4.20+, NFSv4.2 kernel server, targetcli iSCSI LIO, and `sanoid`/`syncoid` automated snapshot lifecycle management.
    - **`appliance-home-cloud`**: A turnkey Docker personal cloud appliance (CasaOS/ZimaOS style) featuring automated local storage pooling and container application management.

### 2. Commercial NAS Interoperability Specifications

- **QNAP QTScloud**: Lusoris Kubernetes nodes support dynamic iSCSI mapping via `open-iscsi` and multipath failover.
- **Synology vDSM**: Seamless integration with Synology CSI drivers for dynamic Kubernetes PersistentVolume provisioning.
- **StarWind SAN & NAS**: Dual-controller active-active NVMe-oF (TCP) and iSCSI multipathing configured in `cloudnative-storage`.

### 3. Dedicated Platform Documentation

- Authored [`docs/platforms/truenas.md`](../platforms/truenas.md) detailing TrueNAS SCALE zvol streaming, KVM configuration, and NFSv4.2 caching.
- Authored [`docs/platforms/nas-appliances.md`](../platforms/nas-appliances.md) covering OpenMediaVault, CasaOS/ZimaOS, QTScloud, vDSM, and StarWind.

## Consequences

### Positive

- **First-Class Storage Ergonomics**: TrueNAS and Unraid operators achieve sub-second VM provisioning and zero-lag file access.
- **Enterprise Storage Diversity**: Seamlessly accommodates both open-source ZFS purists and commercial appliance environments.
- **High-Performance Data Path**: Eliminates client-side NFS bottlenecks via `fscache` and multi-channel SMB.
- **Zero-Leak Compliance**: All documentation and examples strictly adhere to RFC 1918 zero-leak invariants.

### Negative / Neutral

- Adds maintenance coverage for dedicated NAS platform documentation and future appliance flavors.
