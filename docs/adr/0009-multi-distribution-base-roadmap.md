# 9. Multi-Distribution Base OS Architecture and Roadmap

Date: 2026-09-10

## Status

Accepted

## Context

`imago` was bootstrapped with Ubuntu LTS (currently Ubuntu 26.04 LTS Resolute Minimal, maintaining Ubuntu 24.04 LTS compatibility) as its foundational distribution. Ubuntu was selected because of its comprehensive driver support for modern hardware accelerators (NVIDIA 535–615 CUDA stacks, Intel Xe/Xe2 Media & Level Zero runtimes, AMD ROCm 10) and robust upstream cloud-init integration.

However, relying exclusively on a single base distribution creates structural limitations:

1. **Footprint Overhead for Non-GPU Appliances**: Lightweight microVMs, DNS gateways (`appliance-gateway-dns`), and storage heads (`cloudnative-storage`) do not require Ubuntu's accelerated driver ecosystem and benefit significantly from Debian's minimal package surface or Alpine's sub-50MB rootfs.
2. **Upstream Stability Demands**: CNCF storage and database appliances require predictable kernel stability and minimal package churn, for which Debian (Bookworm 12 / Trixie 13) is an industry gold standard.
3. **Declarative Immutable Root Paradigm**: Modern immutable container hosts (`cloudnative-generic`) increasingly move toward OCI image-based boot (`bootc` on Fedora/CentOS Stream) rather than traditional package-based rootfs installations.
4. **Architectural Confusion in Documentation**: Presenting Ubuntu as the only possible upstream base obscures the long-term design contract of `imago` as a multi-distribution OS image forge.

## Decision

We formalize a phased **Multi-Distribution Upstream Base Architecture** segmented across four workload and hardware tiers:

### 1. Upstream Base Segmentation Matrix

| Base OS Track | Release Target | Workload Tier Alignment | Rationale |
| :--- | :--- | :--- | :--- |
| **Ubuntu LTS (Production Core)** | 26.04 Resolute / 24.04 Noble | Tier 1 (Base GPU), Tier 2 (Docker/Podman GPU), Tier 3 (K8s GPU), Tier 6 (AI Inference) | Broadest hardware acceleration, first-party NVIDIA/Intel/AMD vendor repositories, and UKI support. |
| **Debian Minimal (Phase 2)** | 13 Trixie / 12 Bookworm | Tier 1 (Base Generic), Tier 5 (CloudNative Storage & PG), Tier 7 (Gateway DNS) | Extreme stability, predictable lifecycle, zero vendor telemetry, ideal for non-GPU appliances. |
| **Alpine Linux (Phase 3)** | 3.21+ / Edge | MicroVMs, Tier 4 (K3s Edge Worker), Tier 7 (Gateway DNS) | Sub-50MB idle footprint, musl libc, sub-second firecracker/cloud-hypervisor boot. |
| **bootc / OSTree (Phase 4)** | CentOS Stream 10 / Fedora CoreOS | Tier 5 (CloudNative Immutable Host) | Declarative container-native OS updates via standard OCI registries (`bootc switch`). |

### 2. Single Source of Truth (`versions.json`) Evolution

To maintain backward compatibility while supporting multi-distribution upstream manifests, `versions.schema.json` and `versions.json` will transition from a flat `distro` object to a partitioned `distros` dictionary in Phase 2:

```json
{
  "distros": {
    "ubuntu": {
      "release": "resolute",
      "version": "26.04",
      "iso_url": "https://cloud-images.ubuntu.com/daily/server/resolute/current/resolute-server-cloudimg-amd64.img",
      "iso_checksum": "file:https://cloud-images.ubuntu.com/daily/server/resolute/current/SHA256SUMS"
    },
    "debian": {
      "release": "bookworm",
      "version": "12.9",
      "iso_url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2",
      "iso_checksum": "file:https://cloud.debian.org/images/cloud/bookworm/latest/SHA512SUMS"
    },
    "alpine": {
      "release": "v3.21",
      "version": "3.21.3",
      "iso_url": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/alpine-virt-3.21.3-x86_64.iso",
      "iso_checksum": "sha256:..."
    }
  }
}
```

The current `distro` block remains as the canonical default pointing to `ubuntu` until multi-distro Packer sources are fully introduced.

### 3. Provisioner Abstraction & Power of 10 Contract

Shell provisioners will retain strict Holzmann Power of 10 constraints ($\le 60$ lines, `set -euo pipefail`). Provisioners targeting multi-distro tiers will source a lightweight package manager wrapper (`lib/pkg-manager.sh`) to normalize package installation commands (`apt-get` vs. `apk` vs. `dnf`) without duplicating hardening logic.

## Consequences

### Positive

- Establishes a transparent, authoritative roadmap for expanding beyond Ubuntu LTS.
- Clearly delineates which workloads stay on Ubuntu (hardware-accelerated GPU and AI inference) versus those that migrate to Debian or Alpine (minimal microVMs, DNS, storage).
- Ensures future schema expansions to `versions.json` remain structured, typed, and backwards-compatible.
- Eliminates documentation and architectural ambiguity regarding the scope of `imago`.

### Negative / Trade-offs

- Multi-distribution support requires maintaining packaging abstraction layers across `apt`, `apk`, and `dnf`.
- CI build matrices will expand to validate non-Debian package managers as subsequent phases are merged.
