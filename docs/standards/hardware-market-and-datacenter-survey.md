# Enterprise Hardware Market and Datacenter Survey Specification

To ensure `lusoris-cloud-images` operates with zero friction across real-world enterprise datacenters, second-hand server markets, and advanced homelabs, this specification codifies hardware baselines, platform quirks, and two distinct datacenter generational tiers.

---

## 1. Enterprise Secondary Market Analysis (Homelab & Edge Racks)

Enterprise hardware decommission cycles (typically 3–5 years in hyperscale and financial institutions) flood the secondary market with high-density compute platforms. Lusoris provides turnkey, pre-tuned driver stacks for the three dominant enterprise original equipment manufacturers (OEMs):

### 1.1 Dell PowerEdge Matrix (13th, 14th, and 15th Generation)

| Generation | Representative Models | CPU Family | Memory | Storage Subsystem | Recommended Lusoris Flavor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **13G** | R730, R730xd, T630 | Intel Xeon E5-2600 v3/v4 (Haswell/Broadwell) | DDR4 ECC Reg | PERC H330 (IT mode) / H730P | `base-generic`, `docker-generic` |
| **14G** | R740, R740xd, R640 | 1st/2nd Gen Xeon Scalable (Skylake/Cascade Lake) | DDR4-2666/2933 | PERC H740P / HBA330, U.2 NVMe backplane | `cloudnative-storage`, `k8s-node-generic` |
| **15G** | R750, R650, C6520 | 3rd Gen Xeon Scalable (Ice Lake-SP) | DDR4-3200 8-channel | PERC H755 / Front NVMe PCIe Gen4 | `ai-infer-generic`, `k8s-node-generic` |

#### Platform Quirks & Mitigations

- **iDRAC Fan Acoustic Curve**: Dell 13G/14G servers increase fan speed to 80–100% duty cycle when non-certified PCIe cards (such as NVIDIA GPUs or Coral TPUs) are inserted. Lusoris documents IPMI raw command mitigations (`ipmitool raw 0x30 0x30 0x01 0x00` to disable dynamic fan control algorithms) in deployment runbooks.
- **SAS HBA IT-Mode**: Hardware RAID controllers (`PERC H730`) should be flashed or set to HBA pass-through mode for OpenZFS in `cloudnative-storage`.

---

### 1.2 HPE ProLiant Matrix (Gen9, Gen10, Gen10 Plus, Gen11)

| Generation | Models | Processor Architecture | Storage Controller | Remote Out-of-Band |
| :--- | :--- | :--- | :--- | :--- |
| **Gen9** | DL360 / DL380 Gen9 | Intel Xeon E5-2600 v3/v4 | Smart Array P440ar (HBA mode) | iLO 4 |
| **Gen10** | DL360 / DL380 Gen10 | Intel Xeon Scalable 1st/2nd Gen | Smart Array P408i-a | iLO 5 |
| **Gen10 Plus** | DL385 Gen10 Plus | AMD EPYC 7002/7003 (Rome/Milan) | Smart Array SR416i-a (PCIe Gen4) | iLO 5 |
| **Gen11** | DL380 / DL385 Gen11 | 4th/5th Gen Xeon / AMD EPYC 9004 | Tri-Mode Controllers (U.3 NVMe) | iLO 6 |

#### Platform Quirks & Mitigations

- **Smart Array CCISS / HPSA Driver**: Lusoris bare-metal kernels configure `hpsa.hpsa_simple_mode=1` to allow direct drive addressing by OpenZFS and Linux software RAID without hardware RAID virtual disks.

---

### 1.3 Supermicro Platforms (X11, X12, H11, H12)

- **Intel Xeon Platforms (X11DPi-N, X12DPi-NT)**: Dual-socket configurations requiring explicit NUMA node binding (`numactl --interleave=all` or `--cpubind=0 --membind=0`) for high-throughput AI inference and packet processing.
- **AMD EPYC Platforms (H11DSi, H12DSi)**: High PCIe lane density (128 PCIe Gen3/Gen4 lanes). Ideal for multi-GPU clusters (`base-nvidia-mainstream`, `ai-infer-nvidia`). Requires `pci=noaer` or `pci=realloc` on older firmware revisions with non-compliant ACPI MCFG tables.

---

### 1.4 High-Speed Networking & Network Interface Card (NIC) Compatibility

| Chipset Family | Manufacturer | Link Speeds | Linux In-Tree Driver | Lusoris Offload Tuning |
| :--- | :--- | :--- | :--- | :--- |
| **ConnectX-4 / 5 / 6** | NVIDIA / Mellanox | 25G / 40G / 100G / 200G | `mlx5_core` | RoCE v2, SR-IOV, Hardware TSO/LRO |
| **Intel X520 / X540 / X550** | Intel | 10GbE SFP+ / 10GBase-T | `ixgbe` | Rx/Tx ring buffers 4096, RSS |
| **Intel X710 / XL710** | Intel | 10G / 40G QSFP+ | `i40e` | Dynamic Device Personalization (DDP) |
| **Intel E810** | Intel | 25G / 100G | `ice` | RoCE / iWARP RDMA, Application Device Queues |
| **Broadcom NetXtreme** | Broadcom | 10G / 25G | `bnxt_en` | Hardware VLAN stripping, GRO |

---

## 2. The Two Datacenter Generational Tiers

Modern cloud infrastructure and sovereign AI datacenters present divergent requirements between production stability and bleeding-edge acceleration throughput. Lusoris formalizes two distinct tiers:

```text
+-----------------------------------------------------------------------------------------+
|                                 LUSORIS DATACENTER TIERS                                |
+---------------------------------------------+-------------------------------------------+
| TIER A: Established Enterprise Production   | TIER B: Bleeding-Edge Generational AI     |
+---------------------------------------------+-------------------------------------------+
| Target: 99.999% High-Availability Clusters  | Target: Maximum FLOPs / Multi-Node LLM    |
| Primary Hardware: NVIDIA Ampere / Hopper    | Primary Hardware: NVIDIA Hopper / Blackwell|
| GPUs: A100 (40/80GB), L40S, H100 SXM5       | GPUs: H200 (141GB HBM3e), B200 (192GB HBM3e)|
| Host CPUs: AMD EPYC 7003/9004, Intel Xeon 4th| Host CPUs: Grace CPU, Emerald/Granite Rapids|
| Driver Baseline: NVIDIA 595 Branch (LTSB)   | Driver Baseline: NVIDIA 615 server open + Fabric |
| Networking: Mellanox HDR (200Gb/s) InfiniBand| Networking: Mellanox NDR (400G) / XDR (800G)|
| Topologies: Standalone PCIe, Standard CNI   | Topologies: NVLink 5 (1.8TB/s), Rail-Optim|
+---------------------------------------------+-------------------------------------------+
```

### 2.1 Tier A: Established Enterprise Production (Hopper / Ampere)

- **Design Objective**: Rock-solid stability for multi-tenant Kubernetes clusters, private cloud infrastructure, and enterprise inference.
- **Software Stack**:
  - NVIDIA 595 Mainstream driver branch.
  - CUDA 13.2 runtime libraries.
  - Standard Container Device Interface (CDI) device mapping.
  - In-tree InfiniBand / RoCE drivers (`rdma-core`, `mlx5_core`).
- **Primary Flavors**: `base-nvidia-mainstream`, `docker-nvidia`, `k8s-node-nvidia`, `ai-infer-nvidia`.

### 2.2 Tier B: Bleeding-Edge Generational AI (Blackwell / Hopper Open)

- **Design Objective**: Extreme-scale foundation model training, multi-node vLLM FP4/FP8 inference, and multi-GPU tensor-parallel workloads.
- **Software Stack**:
  - NVIDIA 615 Open Kernel Modules driver branch.
  - CUDA 13.4 bleeding-edge runtime libraries.
  - NVIDIA Fabric Manager service enabled for cross-GPU NVLink bridging.
  - Unified Memory (`nvidia-uvm`) with NUMA node striping.
- **Primary Flavors**: `base-nvidia-bleeding`, `base-nvidia-datacenter`, `docker-nvidia-bleeding`, `k8s-node-nvidia-bleeding`, `ai-infer-nvidia-bleeding`.

---

## 3. Recurring Hardware Survey Synchronization Methodology

Hardware market trends and consumer hardware deployments evolve continuously. Lusoris establishes an automated and procedural synchronization cadence:

1. **Steam Hardware & Software Survey (Monthly Sync)**:
   - Tracks consumer GPU adoption shifts (e.g., transition from RTX 3060/4060 to RTX 50-series).
   - Sync Action: Adjust desktop and homelab transcoding presets (`appliance-media-server`, `base-nvidia-mainstream`).
2. **r/homelab & ServeTheHome (STH) Enterprise Survey (Quarterly Sync)**:
   - Tracks secondary market pricing and decommission cycles of enterprise servers (e.g., transition from Dell 13G E5-v4 to 14G Xeon Scalable).
   - Sync Action: Review default sysctl tuning, CPU microcode bundles, and kernel driver inclusions in `25-baremetal-tuning.sh`.
3. **Top500 & Green500 Supercomputing List (Semi-Annual Sync — June & November)**:
   - Tracks dominant enterprise accelerator architectures and interconnect standards (NVLink, Slingshot, InfiniBand).
   - Sync Action: Validate Fabric Manager configurations and CUDA version support windows in `versions.json`.
