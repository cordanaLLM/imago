# lusoris-cloud-images — Flavor Catalog (44 Flavors)

`lusoris-cloud-images` structures operating system images across four orthogonal dimensions: **Platform**, **Workload Tier**, **Hardware Acceleration**, and **Kernel/Preheat Profile**.

This catalog segments all **44 production-ready flavors** into 7 clear workload tiers.

---

## Workload Tier Index

1. [Tier 1: Minimal Base Cloud OS (8 Flavors)](#tier-1-minimal-base-cloud-os-8-flavors)
2. [Tier 2: Container Hosts — Docker & Podman (7 Flavors)](#tier-2-container-hosts--docker--podman-7-flavors)
3. [Tier 3: Enterprise Kubernetes Nodes (9 Flavors)](#tier-3-enterprise-kubernetes-nodes-9-flavors)
4. [Tier 4: K3s Edge Fleet (5 Flavors)](#tier-4-k3s-edge-fleet-5-flavors)
5. [Tier 5: Cloud-Native Immutable & Storage Appliances (4 Flavors)](#tier-5-cloud-native-immutable--storage-appliances-4-flavors)
6. [Tier 6: AI & LLM Inference Appliances (6 Flavors)](#tier-6-ai--llm-inference-appliances-6-flavors)
7. [Tier 7: Specialized Homelab Appliances (5 Flavors)](#tier-7-specialized-homelab-appliances-5-flavors)

---

## Tier 1: Minimal Base Cloud OS (8 Flavors)

> **Purpose**: Clean, bloat-free foundation with coexisting hypervisor agents (`qemu-guest-agent`, `open-vm-tools`), resilient Network Time Security (NTS), and GPU driver runtimes.
>
> 📖 **Deep Dive**: [`docs/flavors/base.md`](docs/flavors/base.md)

| Flavor Target | Hardware Stack | Kernel Profile | Key Components | Local Make Target |
| :--- | :--- | :--- | :--- | :--- |
| **`base-generic`** | VirtIO / Generic CPU | `generic` | Minimal OS, Anycast NTS, QEMU+VMware agents | `make build-base-generic` |
| **`base-intel`** | Intel Xe / Arc / Xe2 | `generic` | Intel Media Driver (`iHD`), Level Zero, vainfo | `make build-base-intel` |
| **`base-amd`** | AMD Radeon / APU | `generic` | Mesa Gallium `radeonsi`, RADV Vulkan, AMDGPU DRM | `make build-base-amd` |
| **`base-nvidia-legacy`** | NVIDIA Pascal / Volta | `generic` | NVIDIA 535 driver, CUDA 12.2 (GTX 1080, P4, P40, V100) | `make build-base-nvidia-legacy` |
| **`base-nvidia-mainstream`** | NVIDIA Turing / Ampere | `generic` | NVIDIA 565 driver, CUDA 12.8 (RTX 20/30/40, A100, L4) | `make build-base-nvidia-mainstream` |
| **`base-nvidia-modern`** | NVIDIA Ada / Hopper | `generic` | NVIDIA 610 driver, CUDA 13.3 (RTX 4080/4090, L40S, H100) | `make build-base-nvidia-modern` |
| **`base-nvidia-bleeding`** | NVIDIA Blackwell | `generic` | NVIDIA 615 driver, CUDA 13.4 (RTX 5090, B200) | `make build-base-nvidia-bleeding` |
| **`base-nvidia-datacenter`** | NVIDIA Hopper / Blackwell | `baremetal` | NVIDIA 615 Open Kernel Modules, Fabric Manager | `make build-base-nvidia-datacenter` |

---

## Tier 2: Container Hosts — Docker & Podman (7 Flavors)

> **Purpose**: Production container runtimes with systemd cgroups, log rotation, and declarative Container Device Interface (CDI) passthrough.
>
> 📖 **Deep Dive**: [`docs/flavors/containers.md`](docs/flavors/containers.md)

| Flavor Target | Hardware Stack | Kernel Profile | Key Components | Local Make Target |
| :--- | :--- | :--- | :--- | :--- |
| **`docker-generic`** | VirtIO / Generic CPU | `generic` | Docker CE 29.8, Docker Compose v2, systemd cgroup | `make build-docker-generic` |
| **`docker-intel`** | Intel Xe / Arc / Xe2 | `generic` | Docker CE + Intel QuickSync passthrough + CDI spec | `make build-docker-intel` |
| **`docker-amd`** | AMD Radeon / Instinct | `generic` | Docker CE + AMD ROCm 7.2 compute runtime + CDI spec | `make build-docker-amd` |
| **`docker-nvidia`** | NVIDIA Mainstream | `generic` | Docker CE + NVIDIA 565 + Container Toolkit CDI | `make build-docker-nvidia` |
| **`docker-nvidia-modern`** | NVIDIA Modern | `generic` | Docker CE + NVIDIA 610 + Container Toolkit CDI | `make build-docker-nvidia-modern` |
| **`docker-nvidia-bleeding`** | NVIDIA Bleeding | `generic` | Docker CE + NVIDIA 615 + Container Toolkit CDI | `make build-docker-nvidia-bleeding` |
| **`podman-generic`** | VirtIO / Generic CPU | `generic` | Podman 5.x, Buildah, Skopeo, Quadlet, Netavark CNI | `make build-podman-generic` |

---

## Tier 3: Enterprise Kubernetes Nodes (9 Flavors)

> **Purpose**: Production Kubernetes worker nodes pre-baked with `containerd 2.3.5`, `kubelet 1.37.0`, `kubeadm`, and optional CNI preheating (Cilium, Calico, Flannel, kube-vip).
>
> 📖 **Deep Dive**: [`docs/flavors/kubernetes.md`](docs/flavors/kubernetes.md)

| Flavor Target | Hardware Stack | Kernel Profile | Preheat Profile | Key Components | Local Make Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`k8s-node-generic`** | VirtIO / CPU | `k8s` | `lean` | containerd 2.3.5, kubelet 1.37.0, zero pre-cache | `make build-k8s-generic` |
| **`k8s-node-cilium`** | VirtIO / CPU | `k8s` | `cilium` | containerd 2.3.5, preheated Cilium 1.20.1 & kube-vip 1.2.3 | `make build-k8s-cilium` |
| **`k8s-node-calico`** | VirtIO / CPU | `k8s` | `calico` | containerd 2.3.5, preheated Calico 3.32.2 & kube-vip 1.2.3 | `make build-k8s-calico` |
| **`k8s-node-flannel`** | VirtIO / CPU | `k8s` | `flannel` | containerd 2.3.5, preheated Flannel 0.28.9 & kube-vip 1.2.3 | `make build-k8s-flannel` |
| **`k8s-node-intel`** | Intel Arc / Xe2 | `k8s` | `cilium` | containerd 2.3.5 + Intel drivers + Intel K8s Plugin v0.36.0 | `make build-k8s-intel` |
| **`k8s-node-amd`** | AMD ROCm 7.2 | `k8s` | `cilium` | containerd 2.3.5 + AMD ROCm 7.2 + AMD K8s Plugin v1.37.0 | `make build-k8s-amd` |
| **`k8s-node-nvidia`** | NVIDIA Mainstream | `k8s` | `cilium` | containerd 2.3.5 + NVIDIA 565 + NVIDIA K8s Plugin v0.20.0 | `make build-k8s-nvidia` |
| **`k8s-node-nvidia-modern`** | NVIDIA Modern | `k8s` | `cilium` | containerd 2.3.5 + NVIDIA 610 + NVIDIA K8s Plugin v0.20.0 | `make build-k8s-nvidia-modern` |
| **`k8s-node-nvidia-bleeding`** | NVIDIA Bleeding | `k8s` | `cilium` | containerd 2.3.5 + NVIDIA 615 + NVIDIA K8s Plugin v0.20.0 | `make build-k8s-nvidia-bleeding` |

---

## Tier 4: K3s Edge Fleet (5 Flavors)

> **Purpose**: Lightweight Kubernetes nodes ($\le 300\text{MB}$ idle RAM) optimized for Intel N100 Alder Lake-N mini-PCs, single-board computers, and homelab transcoding/inference.
>
> 📖 **Deep Dive**: [`docs/flavors/k3s.md`](docs/flavors/k3s.md)

| Flavor Target | Role | Hardware Stack | Key Components | Local Make Target |
| :--- | :--- | :--- | :--- | :--- |
| **`k3s-agent-generic`** | Worker | VirtIO / CPU | Lightweight K3s agent, containerd, Flannel (< 300MB RAM) | `make build-k3s-agent-generic` |
| **`k3s-agent-intel`** | Worker | Intel GPU | K3s agent + Intel QuickSync (`iHD`) + Level Zero | `make build-k3s-agent-intel` |
| **`k3s-agent-amd`** | Worker | AMD GPU | K3s agent + AMD ROCm 7.2 compute runtime + RADV Vulkan | `make build-k3s-agent-amd` |
| **`k3s-agent-nvidia`** | Worker | NVIDIA Mainstream | K3s agent + NVIDIA 565 + Container Toolkit CDI | `make build-k3s-agent-nvidia` |
| **`k3s-server-generic`** | Control Plane | VirtIO / CPU | K3s standalone master, embedded SQLite, local-path storage | `make build-k3s-server-generic` |

---

## Tier 5: Cloud-Native Immutable & Storage Appliances (4 Flavors)

> **Purpose**: Zero-drift read-only root filesystems, distributed CNCF storage fabrics (NVMe-oF TCP, OpenZFS 2.3, iSCSI), and tuned PostgreSQL / CloudNativePG database hosts.
>
> 📖 **Deep Dive**: [`docs/flavors/cloudnative.md`](docs/flavors/cloudnative.md)

| Flavor Target | Role | Kernel Profile | Key Components | Local Make Target |
| :--- | :--- | :--- | :--- | :--- |
| **`cloudnative-generic`** | Immutable Host | `generic` | Read-only root protection, ephemeral tmpfs, containerd CDI | `make build-cloudnative-generic` |
| **`cloudnative-k8s`** | Immutable Worker | `k8s` | Read-only root protection, containerd 2.3.5, kubelet 1.37.0 | `make build-cloudnative-k8s` |
| **`cloudnative-storage`** | CNCF Storage | `baremetal` | NVMe-oF (TCP), OpenZFS 2.3, iSCSI, multipath, NFS | `make build-cloudnative-storage` |
| **`cloudnative-pg`** | Database Host | `ai-infer` | CloudNativePG tuning, hugepages, strict memory overcommit | `make build-cloudnative-pg` |

---

## Tier 6: AI & LLM Inference Appliances (6 Flavors)

> **Purpose**: High-throughput CPU/GPU inference appliances tuned with Transparent Hugepages, NUMA balancing, elevated memlock, and vLLM/Ollama execution hooks.
>
> 📖 **Deep Dive**: [`docs/flavors/ai-infer.md`](docs/flavors/ai-infer.md)

| Flavor Target | Hardware Stack | Kernel Profile | Key Acceleration Components | Local Make Target |
| :--- | :--- | :--- | :--- | :--- |
| **`ai-infer-generic`** | CPU High-Throughput | `ai-infer` | Intel AMX, AVX-512, NUMA tuning, Docker CE | `make build-ai-infer-generic` |
| **`ai-infer-intel`** | Intel Xe / Arc / Xe2 | `ai-infer` | Intel Level Zero, OpenVINO, IPEX-LLM, CDI, Docker CE | `make build-ai-infer-intel` |
| **`ai-infer-amd`** | AMD ROCm 7.2 | `ai-infer` | AMD ROCm 7.2, `/dev/kfd` permissions, RDNA 3/4 & Instinct | `make build-ai-infer-amd` |
| **`ai-infer-nvidia`** | NVIDIA Mainstream | `ai-infer` | NVIDIA 565, Transparent Hugepages, NUMA, vLLM, Docker CE | `make build-ai-infer-nvidia` |
| **`ai-infer-nvidia-modern`** | NVIDIA Modern | `ai-infer` | NVIDIA 610, Transparent Hugepages, NUMA, vLLM, Docker CE | `make build-ai-infer-nvidia-modern` |
| **`ai-infer-nvidia-bleeding`** | NVIDIA Bleeding | `ai-infer` | NVIDIA 615, Blackwell RTX 5090 / B200, vLLM, Docker CE | `make build-ai-infer-nvidia-bleeding` |

---

## Tier 7: Specialized Homelab Appliances (5 Flavors)

> **Purpose**: Turn-key, hardened homelab appliances resolving the most common pain points identified on r/homelab and the Steam Hardware Survey (Google Coral TPU, port 53 DNS collisions, dual-vendor VA-API media transcoding, multi-arch CI runners, and 32-bit SteamCMD game servers).
>
> 📖 **Deep Dive**: [`docs/flavors/homelab-appliances.md`](docs/flavors/homelab-appliances.md)

| Flavor Target | Primary Workload | Hardware Stack | Kernel Profile | Key Appliance Stack | Local Make Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`appliance-vision-nvr`** | Frigate NVR, Scrypted | Intel GPU + Coral TPU | `generic` | Coral Edge TPU (`gasket-dkms`, udev), Intel QuickSync (`iHD`), CDI spec, Docker CE | `make build-appliance-vision-nvr` |
| **`appliance-gateway-dns`** | AdGuard Home, Pi-hole | VirtIO / Low-Power CPU | `generic` | Port 53 stub disabled (`DNSStubListener=no`), WireGuard, IP forward (< 150MB RAM) | `make build-appliance-gateway-dns` |
| **`appliance-media-server`** | Jellyfin, Plex, Tdarr | Intel + AMD GPU + NAS | `baremetal` | Intel QuickSync + AMD Mesa VA-API, `nfs-common`, `cifs-utils`, 4096KB readahead | `make build-appliance-media-server` |
| **`appliance-ci-runner`** | Self-Hosted CI Runner | Multi-Core CPU / DinD | `generic` | QEMU ARM64/ARMv7 binfmt, Docker Buildx, `git-lfs`, 4GB tmpfs `/tmp` | `make build-appliance-ci-runner` |
| **`appliance-game-server`** | SteamCMD, Pterodactyl | High Clock CPU | `generic` | 32-bit `i386` glibc, `steamcmd`, 16MB UDP socket buffer tuning, 1M file limits | `make build-appliance-game-server` |
