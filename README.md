# imago

[![HISS-16 Adopted](https://img.shields.io/badge/Standards-HISS--16%20Adopted%20(6%20baselined)-yellow)](AGENTS.md)

<div align="center">

[![CI Quality Gates](https://img.shields.io/github/actions/workflow/status/cordanaLLM/imago/ci.yml?branch=main&label=CI%20Gates&logo=githubactions&logoColor=white&style=flat-square)](https://github.com/cordanaLLM/imago/actions/workflows/ci.yml)
[![Security Scans](https://img.shields.io/github/actions/workflow/status/cordanaLLM/imago/security-scans.yml?branch=main&label=Security%20Scans&logo=github&logoColor=white&style=flat-square)](https://github.com/cordanaLLM/imago/actions/workflows/security-scans.yml)
[![Supply Chain](https://img.shields.io/github/actions/workflow/status/cordanaLLM/imago/supply-chain.yml?branch=main&label=Scorecard&logo=securityscorecards&logoColor=white&style=flat-square)](https://github.com/cordanaLLM/imago/actions/workflows/supply-chain.yml)
[![Release Matrix](https://img.shields.io/github/actions/workflow/status/cordanaLLM/imago/release-matrix.yml?branch=main&label=Release%20Engine&logo=packer&logoColor=white&style=flat-square)](https://github.com/cordanaLLM/imago/actions/workflows/release-matrix.yml)

[![Flavors](https://img.shields.io/badge/Flavors-44%20Production%20Targets-blue?logo=linux&logoColor=white&style=flat-square)](FLAVORS.md)
[![Base OS](https://img.shields.io/badge/Base%20OS-Ubuntu%2026.04%20LTS%20Resolute-E95420?logo=ubuntu&logoColor=white&style=flat-square)](versions.json)
[![Packer](https://img.shields.io/badge/Packer-1.11%2B-02A8EF?logo=packer&logoColor=white&style=flat-square)](https://www.packer.io/)
[![SSOT Schema](https://img.shields.io/badge/SSOT-Draft%202020--12-success?logo=json&style=flat-square)](versions.schema.json)
[![Time Security](https://img.shields.io/badge/Time%20Security-NTS%20RFC%208915-informational?style=flat-square)](docs/security/time-nts.md)

[![Accelerators](https://img.shields.io/badge/Accelerators-NVIDIA%20CUDA%20%7C%20Intel%20Xe%20%7C%20AMD%20ROCm-76B900?logo=nvidia&logoColor=white&style=flat-square)](docs/hardware/nvidia.md)
[![Hypervisors](https://img.shields.io/badge/Hypervisors-Proxmox%20%7C%20Unraid%20%7C%20ESXi%20%7C%20KVM-orange?style=flat-square)](docs/platforms/proxmox.md)
[![Open Standards](https://img.shields.io/badge/Open%20Standards-CDI%20%7C%20OCI%20%7C%20CNI%20%7C%20CSI-purple?style=flat-square)](docs/principles.md)
[![Documentation](https://img.shields.io/badge/Docs-MkDocs%20Material-teal?logo=materialformkdocs&logoColor=white&style=flat-square)](https://cordanallm.github.io/imago)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

<br/>

**Enterprise-grade, hardened, hardware-accelerated cloud and bare-metal OS image forge with pre-baked runtimes.**

> **Fleet identity**: this repository is **`cordanaLLM/imago`** (formerly `lusoris/lusoris-cloud-images`), the reusable image builder named in the [Aegis-OS connected stack contract](https://github.com/cordanallm/Aegis-OS/blob/main/docs/integration/stack.md); its kernel forge is [`cordanaLLM/nucleus`](https://github.com/cordanaLLM/nucleus). Governance, golusoris adoption and the remaining migration steps are tracked in the [routed planning graph](planning/TODO.md) (see [ADR-0019](docs/adr/0019-imago-fleet-migration-praetor-golusoris-planning-graph.md)).

[📖 Documentation Portal](https://cordanallm.github.io/imago) &nbsp;•&nbsp;
[📋 Complete Flavor Catalog (44 Flavors)](FLAVORS.md) &nbsp;•&nbsp;
[📐 Architecture & Principles](docs/principles.md) &nbsp;•&nbsp;
[🔒 Security Advisories](https://github.com/cordanaLLM/imago/security/advisories)

</div>

---

## Why imago?

Stock cloud distributions waste minutes downloading gigabytes of kernel modules, GPU drivers, and container runtimes on first boot. `imago` bakes these dependencies into production-ready, verified images (`.qcow2`, `.raw`, `.vmdk`, and Proxmox/Unraid/VMware templates).

- **Zero Base Bloat**: Complete elimination of Canonical snaps, telemetry services (`ubuntu-pro-client`, `landscape-common`, `popularity-contest`), motd news, and unneeded documentation.
- **Single Source of Truth (`versions.json`)**: Every upstream URL, driver branch, and container tag originates from a single declarative manifest validated against `versions.schema.json`.
- **Multi-Generational Hardware**: Tailored driver stacks for Intel Arc/Flex/Xe2, AMD Mesa/ROCm 10, and NVIDIA generational CUDA (Pascal 535, Ampere/Ada 565, Hopper/Blackwell 610/615).
- **Hypervisor & Bare-Metal Speed Engine**: Coexisting `qemu-guest-agent` + `open-vm-tools`, Unraid `virtiofs`/`9p` host sharing, fast-boot `NoCloud` discovery (< 2s), ZRAM compressed swap guard, weekly `fstrim.timer`, and VirtIO `mq-deadline` I/O scheduling.
- **Multi-Distribution Upstream Roadmap**: Standardized on Ubuntu 26.04/24.04 LTS for accelerator-rich workloads, with an active architectural roadmap ([ADR-0009](docs/adr/0009-multi-distribution-base-roadmap.md)) targeting Debian Bookworm/Trixie for lean microVMs and storage appliances, and Alpine for ultra-lean edge gateways.
- **Resilient Global Time**: Cryptographically authenticated Network Time Security (NTS RFC 8915) combining Cloudflare Anycast and European national metrology laboratories (PTB, Netnod, SIDN, 3eck).

---

## Build Architecture

```mermaid
flowchart TD
    %% Semantic class definitions with vibrant, high-contrast jewel palettes
    classDef ssot fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#ffffff
    classDef foundation fill:#d97706,stroke:#b45309,stroke-width:2px,color:#ffffff
    classDef packer fill:#7c3aed,stroke:#6d28d9,stroke-width:2px,color:#ffffff
    classDef imageless fill:#059669,stroke:#047857,stroke-width:2px,color:#ffffff
    classDef tiers fill:#e11d48,stroke:#be123c,stroke-width:2px,color:#ffffff
    classDef artifacts fill:#4338ca,stroke:#3730a3,stroke-width:2px,color:#ffffff

    subgraph SSOT["Declarative Source of Truth & Upstream Matrix"]
        SRC["Upstream Base OS Matrix<br/><small>Ubuntu LTS Core · Debian · Alpine Roadmap</small>"]:::ssot
        BOM[("versions.json<br/><small>Pinned Upstream BOM & SSOT</small>")]:::ssot
    end

    subgraph Foundation["Hardened Foundation Pipeline (Stages 00–25)"]
        S0["00-base-strip<br/><small>Purge snapd & telemetry</small>"]:::foundation
        S1["05-hypervisor<br/><small>QEMU + VMware + VirtFS</small>"]:::foundation
        S2["10-time<br/><small>Multi-peer Anycast NTS</small>"]:::foundation
        S3["20-sysctl<br/><small>CIS Baseline & BBR</small>"]:::foundation
        S4["25-baremetal<br/><small>NVMe mq-deadline & ZRAM</small>"]:::foundation
        S0 --> S1 --> S2 --> S3 --> S4
    end

    subgraph DualPath["Dual Build & Provisioning Engine"]
        direction TB
        subgraph TrackPacker["Track A: Packer Image Factory"]
            PE["Packer Engine<br/><small>QEMU / Proxmox VE</small>"]:::packer
            Tiers["44 Production Flavors<br/><small>7 Workload Tiers × Hardware Matrix</small>"]:::tiers
            Artifacts[".qcow2.zst · .raw.zst · .vmdk.zst<br/><small>High-Ratio Zstandard Artifacts</small>"]:::artifacts
            PE --> Tiers
            Tiers --> Artifacts
        end
        subgraph TrackImageless["Track B: Imageless & MicroVMs"]
            CLI["imago CLI / MCP<br/><small>Go 1.27 Engine</small>"]:::imageless
            Apply["In-Place Provisioning<br/><small>SSH / Local Host Apply</small>"]:::imageless
            Boot["MicroVM Direct Kernel Boot<br/><small>Cloud-Hypervisor & Firecracker</small>"]:::imageless
            CLI --> Apply
            CLI --> Boot
        end
    end

    SSOT --> Foundation
    Foundation --> PE
    Foundation -.-> CLI

    style SSOT fill:none,stroke:#0284c7,stroke-width:2px,stroke-dasharray: 4 4
    style Foundation fill:none,stroke:#d97706,stroke-width:2px,stroke-dasharray: 4 4
    style TrackPacker fill:none,stroke:#7c3aed,stroke-width:2px,stroke-dasharray: 4 4
    style TrackImageless fill:none,stroke:#059669,stroke-width:2px,stroke-dasharray: 4 4
    style DualPath fill:none,stroke:#64748b,stroke-width:2px
```

---

## Workload Tier Summary (44 Flavors)

To keep maintenance low and usability high, flavors are partitioned into 7 distinct tiers. 

| Tier | Flavors | Hardware Acceleration | Key Runtime Components | Documentation |
| :--- | :---: | :--- | :--- | :--- |
| **1. Base Cloud** | 8 | Generic, Intel Xe, AMD Mesa, NVIDIA (535 to 615) | Hardened OS, Anycast NTS, QEMU/VMware agents | [📖 Base Guide](docs/flavors/base.md) |
| **2. Container Hosts** | 7 | Generic, Intel QuickSync, AMD ROCm, NVIDIA CDI | Docker CE 29.8, Docker Compose v2, Podman 5.x | [📖 Containers Guide](docs/flavors/containers.md) |
| **3. Enterprise K8s** | 9 | Generic, Intel Arc, AMD ROCm 10, NVIDIA Mainstream/Bleeding | containerd 2.3.5, kubelet 1.37.0, Cilium/Calico preheat | [📖 Kubernetes Guide](docs/flavors/kubernetes.md) |
| **4. K3s Edge Fleet** | 5 | Generic, Intel QuickSync, AMD ROCm 10, NVIDIA CDI | Lightweight K3s (< 300MB RAM), Flannel, SQLite | [📖 K3s Guide](docs/flavors/k3s.md) |
| **5. CloudNative & Storage** | 4 | Generic, Baremetal, NVMe-oF, OpenZFS 2.3 | Read-only root immutability, OpenZFS, CloudNativePG | [📖 CloudNative Guide](docs/flavors/cloudnative.md) |
| **6. AI & LLM Inference** | 6 | AMX/AVX-512, Intel Xe2, AMD ROCm 10, NVIDIA (565/610/615) | Transparent Hugepages, NUMA, vLLM / Ollama | [📖 AI Inference Guide](docs/flavors/ai-infer.md) |
| **7. Homelab Appliances** | 5 | Coral TPU, QuickSync, Dual VA-API, ARM64 binfmt, i386 | Frigate NVR, AdGuard/Pi-hole, Jellyfin, CI runner, SteamCMD | [📖 Homelab Guide](docs/flavors/homelab-appliances.md) |

> 📋 **Detailed Specifications**: Browse the complete list of all 44 target configurations in [**`FLAVORS.md`**](FLAVORS.md) or explore them interactively in the [**Documentation Portal Matrix**](https://cordanallm.github.io/imago/flavors/matrix/).

---

## Quickstart

### Prerequisites

- [Packer](https://developer.hashicorp.com/packer/install) $\ge$ 1.9.0
- [QEMU](https://www.qemu.org/) with KVM support (`qemu-system-x86_64`)
- ShellCheck, Shfmt, and Yamllint

### Build Locally (Standalone QEMU)

```bash
# Clone the repository
git clone https://github.com/cordanaLLM/imago.git
cd imago

# Initialize plugins and run quality gates
make init
make lint
make test

# Build images (or specify any flavor from FLAVORS.md)
make build-base-generic        # Minimal hardened OS
make build-docker-nvidia       # Docker CE + NVIDIA 565 Container Toolkit
make build-k8s-cilium          # Enterprise K8s + preheated Cilium
make build-k3s-agent-generic   # Lightweight Edge K3s worker (< 300MB RAM)
make build-cloudnative-generic # Immutable container host (read-only root)
make build-cloudnative-storage # CNCF storage appliance (NVMe-oF / ZFS)
make build-ai-infer-nvidia     # AI inference appliance (vLLM / NUMA tuning)
```

---

## Repository & Documentation Map

```text
.
├── versions.json              # Single Source of Truth (SSOT) for all versions
├── versions.schema.json       # JSON Schema (Draft 2020-12) validating SSOT
├── FLAVORS.md                 # Segmented catalog of all 44 production flavors & make targets
├── mkdocs.yml                 # Documentation portal configuration
├── docs/                      # Comprehensive engineering documentation
│   ├── flavors/               # Detailed guides for each workload tier
│   ├── platforms/             # Hypervisors: Proxmox, Unraid, VMware, Bare-Metal
│   ├── hardware/              # Acceleration: NVIDIA CUDA, Intel Arc, AMD ROCm
│   ├── security/              # CIS Benchmarks, Anycast NTS, Supply Chain
│   ├── adr/                   # Architecture Decision Records (0001–0011)
│   └── community/             # Contributing, Security, Audits, Governance
├── packer/                    # Modular Packer HCL2 templates & shell provisioners
├── tests/                     # Automated pytest verification suite
└── Makefile                   # Unified local targets (lint, test, build-*)
```

---

## Governance & Security

- **Security Advisories**: To report security vulnerabilities, open a [GitHub Private Security Advisory](https://github.com/cordanaLLM/imago/security/advisories/new).
- **Engineering Principles**: All changes must satisfy [Engineering Principles](docs/principles.md) and [Rule Crosswalk](docs/repository-rule-crosswalk.md).
- **License**: [Apache 2.0](LICENSE) — Copyright &copy; 2026 The Lusoris Authors.

## Standards & Governance

This repository conforms to High-Integrity Systems Standards (HISS-16)
and modernized NASA JPL Power-of-10 rules.

| Gate | Command | Description |
| :--- | :--- | :--- |
| **Verification** | `make verify-all` | Runs full audit, test suite, and context integrity check |
| **HISS Audit** | `standardsctl audit` | Enforces zero technical debt regression against baseline |
| **Context Sync** | `standardsctl compile-context` | Transpiles canonical `AGENTS.md` to all AI targets |
