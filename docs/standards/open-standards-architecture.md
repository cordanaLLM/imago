# Open Standards and Sovereign Infrastructure Architecture

`lusoris-cloud-images` is engineered on open, vendor-neutral infrastructure standards, eliminating proprietary hypervisor lock-in and complying with European sovereign software regulations. This document defines the architectural standards implemented across the repository.

---

## 1. Discoverable Partitions Specification (DPS)

The **Discoverable Partitions Specification (DPS)**, standardized by `systemd`, assigns deterministic GUIDs to disk partitions. This allows the Linux kernel and `systemd-gpt-auto-generator` to discover and mount `/`, `/boot`, `/home`, and swap automatically without relying on hardcoded device paths (`/dev/sda1`) or static `/etc/fstab` entries.

### 1.1 Standard Type GUIDs Employed

| Partition Mount | Filesystem Format | Architecture | Type GUID |
| :--- | :--- | :--- | :--- |
| **EFI System Partition (ESP)** | VFAT (FAT32) | Universal | `C12A7328-F81F-11D2-BA4B-00A0C93EC93B` |
| **Extended Boot (`/boot`)** | Ext4 | Universal | `BC13C2FF-59E6-4262-A352-B275FD6F7172` |
| **Root (`/`)** | Ext4 / Btrfs | `x86_64` | `4F68BCE3-E8CD-4DB1-96E7-FBCAF984B709` |
| **Root (`/`)** | Ext4 / Btrfs | `arm64` | `B921B045-1DF0-41C3-AF44-4C6F280D3FAE` |
| **Root (`/`)** | Ext4 / Btrfs | `riscv64` | `7250A7D8-9A40-42E4-B4D0-CE1535D16420` |

### 1.2 Operational Benefits

- Partition images can be cloned, resized, or attached as secondary disks without fstab UUID collision conflicts.
- Cloud-init disk expansion (`growpart`) functions deterministically across all virtualization platforms.

---

## 2. Unified Kernel Images (UKI) and systemd-boot

A **Unified Kernel Image (UKI)** packages the UEFI boot stub, Linux kernel binary, initramfs image, microcode bundles, and kernel command line into a single, self-contained PE/COFF EFI executable.

```text
+-----------------------------------------------------------------------------+
|                           UNIFIED KERNEL IMAGE (.efi)                       |
+-----------------------------------------------------------------------------+
| Section .text   : systemd-boot UEFI stub loader                             |
| Section .linux  : Linux Kernel Binary (vmlinuz)                             |
| Section .initrd : Combined Microcode & Zstandard Initramfs                  |
| Section .cmdline: Cryptographically bound kernel command-line parameters    |
| Section .osrel  : /etc/os-release metadata                                  |
| Section .sig    : Authenticode PKCS#7 digital signature (Secure Boot)       |
+-----------------------------------------------------------------------------+
```

### Invariants

- Tamper-Proof: Because the command line is embedded in the signed EFI binary, malicious modification of kernel parameters at runtime is prevented.
- Atomic Updates: UKI updates involve writing a single `.efi` file into `/boot/efi/EFI/Linux/`, preventing broken states from interrupted kernel/initramfs file copies.

---

## 3. System Extensions (systemd-sysext & confext)

For immutable operating systems (`cloudnative-generic`, `cloudnative-k8s`), system software must be updated or layered without mutating the underlying read-only `/usr` partition.

- **systemd-sysext**: Mounts read-only squashfs, erofs, or raw directory images over `/usr` and `/opt` using overlayfs at boot.
- **systemd-confext**: Extends `/etc` with declarative configuration overlays.
- **Runtime Enactment**: Managed via `systemd-sysext merge` and `systemd-sysext unmerge`, allowing live software extension without rebooting.

---

## 4. Container Device Interface (CDI v0.6.0+)

The **Container Device Interface (CDI)** is an open CNCF specification providing declarative, vendor-neutral hardware device passthrough into OCI container engines (Docker CE, Podman, containerd, CRI-O).

Lusoris provisioners generate standard CDI YAML/JSON descriptors located in `/etc/cdi/`:

```yaml
cdiVersion: 0.6.0
kind: vendor.com/device
devices:
  - name: gpu0
    containerEdits:
      deviceNodes:
        - path: /dev/dri/card0
        - path: /dev/dri/renderD128
      hooks:
        - hook: createRuntime
          path: /usr/bin/nvidia-ctk
```

Containers request hardware with standard CLI or Kubernetes arguments:

```bash
docker run --device vendor.com/device=gpu0 my-ai-container
```

---

## 5. VirtIO 1.3 Specification Compliance

Lusoris images enforce compliance with the OASIS VirtIO 1.3 standard across all hypervisors:

- **`virtio-net`**: Multiqueue support enabled (`ethtool -L eth0 combined 4`), checksum offloading, TSO/LRO.
- **`virtio-blk` / `virtio-scsi`**: Multi-queue I/O with `mq-deadline` scheduler.
- **`virtio-fs`**: High-performance host directory sharing for Unraid, macOS UTM, and developer workstations.
- **`virtio-balloon`**: Free page reporting enabled (`free_page_reporting=1`) allowing hypervisors to dynamically reclaim unused guest memory without performance degradation.

---

## 6. Supply Chain Security and European Sovereignty Compliance

### 6.1 EU Cyber Resilience Act (CRA — Regulation EU 2024/2847)

Lusoris images comply with the essential cybersecurity requirements established by the EU Cyber Resilience Act:

- **Security by Default**: Zero open unauthenticated ports, root login via SSH disabled, password authentication disabled in favor of Ed25519 cryptographic keys.
- **Automatic Vulnerability Ledger**: Weekly automated CVE scans via Trivy and Grype with automated alerts on Critical/High disclosures.

### 6.2 Software Bill of Materials (SBOM) & Provenance (SLSA Level 3)

Every published image artifact includes:

- **SPDX 3.0 & CycloneDX 1.6 SBOM**: Machine-readable inventory of all deb packages, kernel modules, and container runtime components.
- **Sigstore Cosign Attestations**: Cryptographically signed SHA256 checksums, enabling zero-trust supply chain validation prior to VM deployment.
- **Hardware-Rooted Attestation**: Optional TPM 2.0 measured boot logging via `systemd-cryptenroll` and PCR sealing.
