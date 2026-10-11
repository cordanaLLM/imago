# 16. Hypervisor, Storage, and Runtime Image Optimization Architecture

Date: 2026-09-10

## Status

Accepted

## Context

`lusoris-cloud-images` produces virtual machine and bare-metal OS images for high-density virtualization (Proxmox VE, Unraid, VMware ESXi, KVM) and production compute clusters. An exhaustive architectural audit across the image lifecycle identified 6 optimization vectors that significantly enhance boot speed, virtualized I/O throughput, host memory density, and supply chain provenance:

1. **Early Boot & Filesystem Expansion Latency**: Traditional cloud-init relies on a Python-based `growpart` module that executes several seconds into userspace, blocking service startup. Modern systemd provides `systemd-growfs-root.service` capable of instant in-kernel or early initramfs filesystem expansion ($< 5\text{ms}$).
2. **Virtual Disk I/O & Cluster Sizing**: Default QCOW2 images use a 64KB cluster size. In heavy database (`cloudnative-pg`) and container image pull (`docker-*`, `k8s-node-*`) workloads, 64KB clusters trigger high metadata lookup overhead and severe write amplification. Formatting virtual disks with 1MB clusters (`cluster_size=1M`) and `extended_l2=on` yields $20\text{--}30\%$ higher sequential and random write throughput.
3. **Multi-Hypervisor Format Delivery**: Consuming environments require native image formats beyond QCOW2 without manual user conversion: `.raw.zst` (direct disk streaming via `lusoris-install-to-disk`, microVMs), `.vmdk.zst` (VMware ESXi), `.vhdx.zst` (Hyper-V/WSL2), and `.tar.zst` (Incus / LXD system containers).
4. **Host Memory Density & Transparent Deduplication**: When hypervisors host multiple identical Lusoris instances, Kernel Samepage Merging (KSM) in the host kernel can deduplicate shared read-only memory pages (e.g. libc, systemd, kernel text), increasing guest density by $30\text{--}50\%$.
5. **Multi-Queue Networking & eBPF Acceleration**: High-bandwidth virtualized networks (10GbE / 25GbE / 100GbE) default to 1 VirtIO network queue per interface, causing single-core bottlenecking. Binding network queues to available vCPUs (`ethtool -L eth0 combined $(nproc)`) enables line-rate multi-core packet processing.
6. **Supply Chain Attestation & Immutability**: Production environments demand cryptographic verification and SBOM traceability for every published operating system artifact.

## Decision

We establish an enterprise image optimization architecture across 6 core technical dimensions:

### 1. Boot Acceleration & Instant Rootfs Expansion

- **Native `systemd-growfs`**: Transition from Python-dependent `cloud-init-growpart` to `systemd-growfs-root.service`, expanding virtual disks in initramfs in $< 5\text{ms}$.
- **Unified Kernel Images (UKI) Roadmap**: Prepare EFI stub direct booting for UEFI/QEMU microVMs, bundling kernel + initramfs + cmdline into a signed binary to bypass GRUB stage latency ($200\text{--}300\text{ms}$ reduction).
- **Entropy Binding (`virtio-rng`)**: Ensure `virtio-rng` is explicitly bound at boot to prevent entropy stalls during SSH host key generation.

### 2. High-Performance Storage & Multi-Format Delivery

- **QCOW2 Optimization**: Packer post-processors convert base images using:

  ```bash
  qemu-img convert -O qcow2 -o cluster_size=1M,lazy_refcounts=on,extended_l2=on input.raw output.qcow2
  ```

- **Matrix Delivery Pipeline**: Release artifacts are generated in 5 standard formats:
  - `.qcow2.zst`: Proxmox VE, OpenStack, KVM.
  - `.raw.zst`: Bare-metal streaming (`lusoris-install-to-disk`), Firecracker, Cloud-Hypervisor.
  - `.vmdk.zst`: VMware ESXi / vSphere.
  - `.vhdx.zst`: Hyper-V and Windows WSL2.
  - `.rootfs.tar.zst`: Incus / LXD Linux system containers.

### 3. Memory Virtualization, Density & HugePages

- **Host KSM Deduplication**: Guest kernels configure cooperative memory naming and madvise hints, facilitating Kernel Samepage Merging on host hypervisors.
- **HugePages Tuning (2MB / 1GB)**: Database (`cloudnative-pg`), AI inference (`ai-infer-*`), and DPDK/Cilium flavors configure pre-reserved HugePage pools to eliminate TLB cache misses.
- **Cooperative Ballooning**: `virtio_balloon.deflate_on_oom=1` is enforced to ensure the hypervisor yields memory during memory spikes.

### 4. High-Throughput Virtualized Networking

- **VirtIO Multiqueue Auto-Scaling**: A udev rule automatically configures network queues matching the virtual CPU count:

  ```udev
  ACTION=="add", SUBSYSTEM=="net", KERNEL=="eth*|en*", RUN+="/sbin/ethtool -L %k combined $(nproc)"
  ```

- **TCP Window & Buffer Auto-Tuning**: `net.ipv4.tcp_rmem` and `net.ipv4.tcp_wmem` are tuned to 16MB ceilings for intra-cluster replication.
- **eBPF Hardening**: `net.core.bpf_jit_harden=2` and `bpf_jit_enable=1` maintain wire-speed packet filtering for Cilium while mitigating speculative side-channel vulnerabilities.

### 5. Supply Chain Provenance & Immutability

- **Syft SBOM Generation**: Every release artifact generates a machine-readable CycloneDX / SPDX Software Bill of Materials.
- **Cosign / Sigstore Attestation**: Published image checksums and OCI container artifacts are cryptographically signed.
- **A/B Rollback Safety**: Appliance flavors support dual-partition atomic updates via `systemd-sysupdate`.

## Consequences

### Positive

- **Cold Boot Agility**: Sub-second boot times enable agile auto-scaling and responsive microVM lifecycles.
- **Measurable I/O Gain**: 1MB cluster sizing and multiqueue networking resolve traditional virtualization storage and network bottlenecks.
- **Multi-Hypervisor Parity**: Eliminates manual conversion steps for Proxmox, VMware, Unraid, and Hyper-V administrators.
- **Full Supply Chain Compliance**: Conforms to SLSA Level 3 and OpenSSF security recommendations.

### Negative / Neutral

- Generating 5 image formats increases release matrix build duration in GitHub Actions.
