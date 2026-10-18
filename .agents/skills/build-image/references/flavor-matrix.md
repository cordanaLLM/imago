# Lusoris 44-Flavor Build Matrix Reference

> Complete catalog of all 44 production image flavors, categorized across the 7 workload tiers with corresponding Packer target flags and hardware dependencies.

---

## Tier 1: Minimal Base Cloud OS (8 Flavors)

| Flavor ID | Hardware Target | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `base-generic` | VirtIO / CPU | `-only="base-generic.qemu.image"` | Hardened minimal OS, Anycast NTS, QEMU+VMware agents |
| `base-intel` | Intel Arc / Xe / iGPU | `-only="base-intel.qemu.image"` | Intel Media Driver (`iHD`), Level Zero, vainfo, Battlemage Xe2 |
| `base-amd` | AMD Radeon / APU | `-only="base-amd.qemu.image"` | AMD Mesa VA-API (`radeonsi`), RADV Vulkan, AMDGPU DRM |
| `base-nvidia-legacy` | NVIDIA Pascal / Volta | `-only="base-nvidia-legacy.qemu.image"` | NVIDIA 535 driver branch, CUDA 12.2 |
| `base-nvidia-mainstream` | NVIDIA Turing / Ampere | `-only="base-nvidia-mainstream.qemu.image"` | NVIDIA 565 driver branch, CUDA 12.8 |
| `base-nvidia-modern` | NVIDIA Ada / Hopper | `-only="base-nvidia-modern.qemu.image"` | NVIDIA 610 driver branch, CUDA 13.3 |
| `base-nvidia-bleeding` | NVIDIA Blackwell / B200 | `-only="base-nvidia-bleeding.qemu.image"` | NVIDIA 615 driver branch, CUDA 13.4 |
| `base-nvidia-datacenter` | NVIDIA Hopper/Blackwell HGX | `-only="base-nvidia-datacenter.qemu.image"` | NVIDIA Open Kernel Modules, Fabric Manager |

---

## Tier 2: Container Hosts — Docker & Podman (7 Flavors)

| Flavor ID | Runtime Target | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `docker-generic` | Docker CE | `-only="docker-generic.qemu.image"` | Docker CE 29.8, Docker Compose v2, containerd 2.3.5 |
| `docker-intel` | Docker CE + Intel | `-only="docker-intel.qemu.image"` | Docker CE + Intel QuickSync / Level Zero passthrough |
| `docker-amd` | Docker CE + AMD | `-only="docker-amd.qemu.image"` | Docker CE + AMD ROCm 7.2 compute runtime |
| `docker-nvidia` | Docker CE + NVIDIA 565 | `-only="docker-nvidia.qemu.image"` | Docker CE + NVIDIA Container Toolkit + CDI specifications |
| `docker-nvidia-modern` | Docker CE + NVIDIA 610 | `-only="docker-nvidia-modern.qemu.image"` | Docker CE + NVIDIA 610 + NVIDIA Container Toolkit CDI |
| `docker-nvidia-bleeding`| Docker CE + NVIDIA 615 | `-only="docker-nvidia-bleeding.qemu.image"`| Docker CE + NVIDIA 615 + NVIDIA Container Toolkit CDI |
| `podman-generic` | Podman Quadlet | `-only="podman-generic.qemu.image"` | Podman 5.x, Buildah, Skopeo, Quadlet, Netavark CNI |

---

## Tier 3: Enterprise Kubernetes Worker Nodes (9 Flavors)

| Flavor ID | CNI / Hardware | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `k8s-node-generic` | Lean / Custom CNI | `-only="k8s-node-generic.qemu.image"` | containerd 2.3.5, kubelet/kubeadm 1.37.0, zero-preheat |
| `k8s-node-cilium` | Preheated Cilium | `-only="k8s-node-cilium.qemu.image"` | containerd 2.3.5, pre-cached Cilium 1.20.1 & kube-vip 1.2.3 |
| `k8s-node-calico` | Preheated Calico | `-only="k8s-node-calico.qemu.image"` | containerd 2.3.5, pre-cached Calico 3.32.2 & kube-vip 1.2.3 |
| `k8s-node-flannel` | Preheated Flannel | `-only="k8s-node-flannel.qemu.image"` | containerd 2.3.5, pre-cached Flannel 0.28.9 & kube-vip 1.2.3 |
| `k8s-node-intel` | Intel GPU Plugin | `-only="k8s-node-intel.qemu.image"` | containerd 2.3.5 + Intel drivers + Intel K8s Device Plugin |
| `k8s-node-amd` | AMD GPU Plugin | `-only="k8s-node-amd.qemu.image"` | containerd 2.3.5 + AMD ROCm 7.2 + AMD K8s Device Plugin |
| `k8s-node-nvidia` | NVIDIA Mainstream | `-only="k8s-node-nvidia.qemu.image"` | containerd 2.3.5 + NVIDIA 565 + NVIDIA K8s Device Plugin |
| `k8s-node-nvidia-modern`| NVIDIA Modern | `-only="k8s-node-nvidia-modern.qemu.image"` | containerd 2.3.5 + NVIDIA 610 + NVIDIA K8s Device Plugin |
| `k8s-node-nvidia-bleeding`| NVIDIA Bleeding | `-only="k8s-node-nvidia-bleeding.qemu.image"`| containerd 2.3.5 + NVIDIA 615 + NVIDIA K8s Device Plugin |

---

## Tier 4: K3s Edge Fleet (5 Flavors)

| Flavor ID | Role / Hardware | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `k3s-agent-generic` | Generic Edge Worker | `-only="k3s-agent-generic.qemu.image"` | Lightweight K3s agent, containerd, Flannel (< 300MB RAM) |
| `k3s-agent-intel` | Intel GPU Worker | `-only="k3s-agent-intel.qemu.image"` | K3s agent + Intel QuickSync passthrough (`iHD`) + Level Zero |
| `k3s-agent-amd` | AMD GPU Worker | `-only="k3s-agent-amd.qemu.image"` | K3s agent + AMD ROCm 7.2 compute runtime + RADV Vulkan |
| `k3s-agent-nvidia` | NVIDIA GPU Worker | `-only="k3s-agent-nvidia.qemu.image"` | K3s agent + NVIDIA 565 + Container Toolkit CDI |
| `k3s-server-generic` | Master Control Plane | `-only="k3s-server-generic.qemu.image"` | K3s standalone master, embedded SQLite, local-path storage |

---

## Tier 5: Cloud-Native Immutable & Storage Appliances (4 Flavors)

| Flavor ID | Specialization | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `cloudnative-generic` | Immutable Host | `-only="cloudnative-generic.qemu.image"` | Immutable read-only root, ephemeral tmpfs mounts, containerd CDI |
| `cloudnative-k8s` | Immutable K8s Node | `-only="cloudnative-k8s.qemu.image"` | Immutable Kubernetes node, read-only root, containerd 2.3.5 |
| `cloudnative-storage` | CNCF Storage Head | `-only="cloudnative-storage.qemu.image"` | NVMe-oF (TCP), OpenZFS 2.3, iSCSI target, multipath, NFS server |
| `cloudnative-pg` | Database Host | `-only="cloudnative-pg.qemu.image"` | PostgreSQL / CloudNativePG kernel tuning, hugepages, strict overcommit |

---

## Tier 6: AI & LLM Inference Appliances (6 Flavors)

| Flavor ID | Compute Engine | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `ai-infer-generic` | CPU (AVX-512 / AMX) | `-only="ai-infer-generic.qemu.image"` | AMX, AVX-512, NUMA tuning, vLLM/Ollama CPU, Docker CE |
| `ai-infer-intel` | Intel Level Zero / XPU | `-only="ai-infer-intel.qemu.image"` | Intel Level Zero, OpenVINO, IPEX-LLM, CDI, Docker CE |
| `ai-infer-amd` | AMD ROCm 7.2 Instinct | `-only="ai-infer-amd.qemu.image"` | AMD ROCm 7.2, `/dev/kfd`, RDNA 3/4 & Instinct, CDI, Docker CE |
| `ai-infer-nvidia` | NVIDIA Mainstream 565 | `-only="ai-infer-nvidia.qemu.image"` | Transparent hugepages, numactl, vLLM/Ollama (NVIDIA 565) |
| `ai-infer-nvidia-modern`| NVIDIA Modern 610 | `-only="ai-infer-nvidia-modern.qemu.image"` | Transparent hugepages, numactl, vLLM/Ollama (NVIDIA 610) |
| `ai-infer-nvidia-bleeding`| NVIDIA Bleeding 615 | `-only="ai-infer-nvidia-bleeding.qemu.image"`| Transparent hugepages, Blackwell RTX 5090 / B200 (NVIDIA 615) |

---

## Tier 7: Specialized Homelab Appliances (5 Flavors)

| Flavor ID | Appliance Mission | Packer Build Target | Key Components |
| :--- | :--- | :--- | :--- |
| `appliance-vision-nvr` | Coral TPU + QuickSync | `-only="appliance-vision-nvr.qemu.image"` | Coral Edge TPU (`gasket-dkms`), Intel QuickSync (`iHD`), Docker CE |
| `appliance-gateway-dns` | Line-Rate Routing | `-only="appliance-gateway-dns.qemu.image"` | Port 53 stub disabled, WireGuard, line-rate forwarding (< 150MB RAM) |
| `appliance-media-server`| Dual Transcode + NAS | `-only="appliance-media-server.qemu.image"`| Intel QuickSync + AMD Mesa VA-API, `nfs-common`, `cifs-utils` |
| `appliance-ci-runner` | Multi-Arch DinD | `-only="appliance-ci-runner.qemu.image"` | QEMU ARM64/ARMv7 binfmt, Docker Buildx, `git-lfs`, 4GB tmpfs `/tmp` |
| `appliance-game-server` | Low-Jitter UDP Game | `-only="appliance-game-server.qemu.image"` | 32-bit `i386` glibc, `steamcmd`, 16MB UDP socket buffer tuning |

