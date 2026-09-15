# lusoris-cloud-images

> Enterprise-grade, hardened, hardware-accelerated cloud and bare-metal OS images with pre-baked runtimes.
>
> Migrating to the fleet identity `cordanaLLM/imago`; see [ADR-0019](adr/0019-imago-fleet-migration-praetor-golusoris-planning-graph.md) and the [planning graph](tools/planning-graph.md).

---

## What is lusoris-cloud-images?

`lusoris-cloud-images` is an automated OS image forge that builds production-ready, zero-bloat images for **virtualization** (Proxmox VE, Unraid, VMware ESXi, QEMU/KVM), **bare-metal servers**, and **public clouds**.

Instead of deploying generic stock distributions that spend minutes pulling gigabytes of packages and container layers on first boot, `lusoris-cloud-images` provides:

- **Zero Base Bloat**: Complete purge of `snapd`, `lxd`, Ubuntu Pro telemetry, and unneeded documentation.
- **Hardware Acceleration Tiers**: Tailored GPU driver stacks for Intel Arc/Xe, AMD Mesa & ROCm, and NVIDIA generational CUDA (Pascal 535, Ampere/Ada 565, Hopper/Blackwell Open Modules + Fabric Manager).
- **Multi-Hypervisor Portability**: Coexisting `qemu-guest-agent` and `open-vm-tools` plus Unraid `virtiofs` and `9p` host sharing out of the box.
- **Bare-Metal Performance Engine**: NVMe low-latency I/O scheduling, BBR congestion control, auto-growroot on first boot, and streaming direct flash (`lusoris-install-to-disk`).
- **Resilient Global Time**: Cryptographically authenticated Network Time Security (NTS) using Cloudflare Anycast and European national metrology institutes (PTB, Netnod, SIDN, 3eck).
- **Multi-Distribution Upstream Matrix**: Production foundation on Ubuntu 26.04/24.04 LTS for high-velocity hardware acceleration, backed by an authoritative roadmap ([ADR-0009](adr/0009-multi-distribution-base-roadmap.md)) expanding to Debian Bookworm/Trixie and Alpine Linux.
- **Single Source of Truth (`versions.json`)**: Every upstream package, container image tag, and driver branch is centrally defined and automated via Renovate.

---

## Architecture Overview

```mermaid
flowchart TD
    %% Semantic class definitions with vibrant, high-contrast jewel palettes
    classDef ssot fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#ffffff
    classDef foundation fill:#d97706,stroke:#b45309,stroke-width:2px,color:#ffffff
    classDef tiers fill:#e11d48,stroke:#be123c,stroke-width:2px,color:#ffffff
    classDef artifacts fill:#4338ca,stroke:#3730a3,stroke-width:2px,color:#ffffff
    classDef platforms fill:#059669,stroke:#047857,stroke-width:2px,color:#ffffff

    subgraph Inputs["1. Upstream & Declarative SSOT"]
        Upstream["Upstream Base OS Matrix<br/><small>Ubuntu LTS Core · Debian · Alpine Roadmap</small>"]:::ssot
        SSOT[("versions.json<br/><small>Single Source of Truth (BOM)</small>")]:::ssot
    end

    subgraph Core["2. Hardened Foundation (Stages 00–25)"]
        S0["00-base-strip<br/><small>Purge snapd & telemetry</small>"]:::foundation
        S1["05-hypervisor-agents<br/><small>QEMU + VMware + VirtFS</small>"]:::foundation
        S2["10-network-time<br/><small>Multi-peer Anycast NTS</small>"]:::foundation
        S3["20-kernel-sysctl<br/><small>CIS L2 & BBR Congestion</small>"]:::foundation
        S4["25-baremetal-tuning<br/><small>NVMe mq-deadline & ZRAM</small>"]:::foundation
        S0 --> S1 --> S2 --> S3 --> S4
    end

    subgraph Tiers["3. The 4D Production Matrix (44 Flavors across 7 Tiers)"]
        direction TB
        T1["Tier 1: Minimal Base OS<br/><small>Generic · Intel · AMD · NVIDIA 535/565/610/615/Open (8)</small>"]:::tiers
        T2["Tier 2: Container Hosts<br/><small>Docker CE · Podman Quadlet · GPU Passthrough (7)</small>"]:::tiers
        T3["Tier 3: Enterprise K8s Nodes<br/><small>containerd 2.3.5 · Cilium / Calico / Flannel · kube-vip (9)</small>"]:::tiers
        T4["Tier 4: K3s Edge Fleet<br/><small>Agent Flavors · Server Master · GPU Passthrough (5)</small>"]:::tiers
        T5["Tier 5: CloudNative & Storage<br/><small>Immutable Read-Only · NVMe-oF · ZFS · CNPG (4)</small>"]:::tiers
        T6["Tier 6: AI & LLM Inference<br/><small>NUMA · THP · vLLM · Ollama · OpenVINO (6)</small>"]:::tiers
        T7["Tier 7: Homelab Appliances<br/><small>Vision NVR · Gateway DNS · Media · CI Runner · Game Server (5)</small>"]:::tiers
    end

    subgraph Delivery["4. Universal Hypervisor & Bare-Metal Delivery"]
        Artifacts[("Production Artifacts<br/><small>.qcow2.zst · .raw.zst · .vmdk.zst</small>")]:::artifacts
        Platforms(["Proxmox VE · Unraid · VMware ESXi · Cloud Providers · Bare-Metal Install"]):::platforms
        Artifacts --> Platforms
    end

    Inputs --> Core
    Core --> Tiers
    Tiers --> Artifacts

    style Inputs fill:none,stroke:#0284c7,stroke-width:2px,stroke-dasharray: 4 4
    style Core fill:none,stroke:#d97706,stroke-width:2px,stroke-dasharray: 4 4
    style Tiers fill:none,stroke:#e11d48,stroke-width:2px,stroke-dasharray: 4 4
    style Delivery fill:none,stroke:#4338ca,stroke-width:2px,stroke-dasharray: 4 4
```

---

## Quick Navigation

- [Explore the 4D Flavor Matrix](flavors/matrix.md)
- [Proxmox VE Deployment Guide](platforms/proxmox.md)
- [Unraid VM & VirtFS Guide](platforms/unraid.md)
- [VMware ESXi Import Guide](platforms/vmware.md)
- [Bare-Metal NVMe Flashing Guide](platforms/baremetal.md)
- [Architecture Decision Records (ADRs)](adr/README.md)

