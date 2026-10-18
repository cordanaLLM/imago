// Copyright 2026 Lusoris
// Package flavors provides the definitive catalog and query engine for all 44
// production image flavors across the 7 workload tiers.
package flavors

import (
	"fmt"
	"strings"
)

// Tier represents one of the 7 workload tiers.
type Tier struct {
	Number      int    `json:"number"`
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// Flavor encapsulates the metadata, hardware profile, and provisioner pipeline of an image.
type Flavor struct {
	ID             string   `json:"id"`
	TierID         string   `json:"tier_id"`
	TierNumber     int      `json:"tier_number"`
	Name           string   `json:"name"`
	HardwareStack  string   `json:"hardware_stack"`
	KernelProfile  string   `json:"kernel_profile"`
	PreheatProfile string   `json:"preheat_profile,omitempty"`
	Description    string   `json:"description"`
	Provisioners   []string `json:"provisioners"`
}

var allTiers = []Tier{
	{Number: 1, ID: "base", Name: "Minimal Base Cloud OS", Description: "Clean, bloat-free foundation with NTS and hypervisor coexistence"},
	{Number: 2, ID: "containers", Name: "Container Hosts", Description: "Docker CE and Podman hosts with systemd cgroups and CDI"},
	{Number: 3, ID: "kubernetes", Name: "Enterprise Kubernetes Nodes", Description: "Production K8s workers with containerd and optional CNI preheat"},
	{Number: 4, ID: "k3s", Name: "K3s Edge Fleet", Description: "Lightweight K3s agents and server under 300MB idle RAM"},
	{Number: 5, ID: "cloudnative", Name: "Cloud-Native Immutable & Storage", Description: "Read-only root immutable hosts, OpenZFS 2.3, and CNPG database tuning"},
	{Number: 6, ID: "ai-infer", Name: "AI & LLM Inference Appliances", Description: "High-throughput CPU/GPU inference with Transparent Hugepages and NUMA"},
	{Number: 7, ID: "homelab", Name: "Specialized Homelab Appliances", Description: "Turnkey homelab appliances for Coral TPU, DNS, media, CI, and Steam"},
}

var allFlavors = []Flavor{
	// Tier 1: Base (8 flavors)
	{
		ID:            "base-generic",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base Generic",
		HardwareStack: "VirtIO / Generic CPU",
		KernelProfile: "generic",
		Description:   "Minimal hardened OS, Anycast NTS, QEMU+VMware agents",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-intel",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base Intel GPU",
		HardwareStack: "Intel Xe / Arc / Xe2",
		KernelProfile: "generic",
		Description:   "Intel Media Driver (iHD), Level Zero, vainfo",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "30-gpu-intel.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-amd",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base AMD GPU",
		HardwareStack: "AMD Radeon / APU",
		KernelProfile: "generic",
		Description:   "Mesa Gallium radeonsi, RADV Vulkan, AMDGPU DRM",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "31-gpu-amd-mesa.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-nvidia-legacy",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base NVIDIA Legacy",
		HardwareStack: "NVIDIA Pascal / Volta",
		KernelProfile: "generic",
		Description:   "NVIDIA 580 driver, CUDA 13.0 (GTX 1080, P4, P40, V100)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "33-gpu-nvidia-legacy.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-nvidia-mainstream",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base NVIDIA Mainstream",
		HardwareStack: "NVIDIA Turing / Ampere",
		KernelProfile: "generic",
		Description:   "NVIDIA 595 driver, CUDA 13.2 (RTX 20/30/40, A100, L4)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "34-gpu-nvidia-mainstream.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-nvidia-modern",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base NVIDIA Modern",
		HardwareStack: "NVIDIA Ada / Hopper",
		KernelProfile: "generic",
		Description:   "NVIDIA 615 driver, CUDA 13.4 (RTX 4080/4090, L40S, H100)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "37-gpu-nvidia-modern.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-nvidia-bleeding",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base NVIDIA Bleeding",
		HardwareStack: "NVIDIA Blackwell",
		KernelProfile: "generic",
		Description:   "NVIDIA 615 driver, CUDA 13.4 (RTX 5090, B200)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "36-gpu-nvidia-bleeding.sh", "99-cleanup.sh"},
	},
	{
		ID:            "base-nvidia-datacenter",
		TierID:        "base",
		TierNumber:    1,
		Name:          "Base NVIDIA Datacenter",
		HardwareStack: "NVIDIA Hopper / Blackwell",
		KernelProfile: "baremetal",
		Description:   "NVIDIA Open Kernel Modules, Fabric Manager for NVLink",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "35-gpu-nvidia-datacenter.sh", "99-cleanup.sh"},
	},

	// Tier 2: Containers (7 flavors)
	{
		ID:            "docker-generic",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Docker Generic",
		HardwareStack: "VirtIO / Generic CPU",
		KernelProfile: "generic",
		Description:   "Docker CE 29.8, Docker Compose v2, systemd cgroups",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "docker-intel",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Docker Intel GPU",
		HardwareStack: "Intel Xe / Arc / Xe2",
		KernelProfile: "generic",
		Description:   "Docker CE + Intel QuickSync passthrough + CDI spec",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "30-gpu-intel.sh", "40-docker-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "docker-amd",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Docker AMD GPU",
		HardwareStack: "AMD Radeon / Instinct",
		KernelProfile: "generic",
		Description:   "Docker CE + AMD ROCm 10 compute runtime + CDI spec",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "32-gpu-amd-rocm.sh", "40-docker-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "docker-nvidia",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Docker NVIDIA Mainstream",
		HardwareStack: "NVIDIA Mainstream",
		KernelProfile: "generic",
		Description:   "Docker CE + NVIDIA 595 + Container Toolkit CDI",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "34-gpu-nvidia-mainstream.sh", "40-docker-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "docker-nvidia-modern",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Docker NVIDIA Modern",
		HardwareStack: "NVIDIA Modern",
		KernelProfile: "generic",
		Description:   "Docker CE + NVIDIA 615 + Container Toolkit CDI",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "37-gpu-nvidia-modern.sh", "40-docker-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "docker-nvidia-bleeding",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Docker NVIDIA Bleeding",
		HardwareStack: "NVIDIA Bleeding",
		KernelProfile: "generic",
		Description:   "Docker CE + NVIDIA 615 + Container Toolkit CDI",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "36-gpu-nvidia-bleeding.sh", "40-docker-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "podman-generic",
		TierID:        "containers",
		TierNumber:    2,
		Name:          "Podman Generic",
		HardwareStack: "VirtIO / Generic CPU",
		KernelProfile: "generic",
		Description:   "Podman 5.x, Buildah, Skopeo, Quadlet, Netavark CNI",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "41-podman-runtime.sh", "99-cleanup.sh"},
	},

	// Tier 3: Kubernetes (9 flavors)
	{
		ID:             "k8s-node-generic",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node Generic",
		HardwareStack:  "VirtIO / CPU",
		KernelProfile:  "k8s",
		PreheatProfile: "lean",
		Description:    "containerd 2.3.5, kubelet 1.37.0, zero preheat",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-cilium",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node Cilium",
		HardwareStack:  "VirtIO / CPU",
		KernelProfile:  "k8s",
		PreheatProfile: "cilium",
		Description:    "containerd 2.3.5, preheated Cilium 1.20.1 & kube-vip 1.2.3",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-calico",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node Calico",
		HardwareStack:  "VirtIO / CPU",
		KernelProfile:  "k8s",
		PreheatProfile: "calico",
		Description:    "containerd 2.3.5, preheated Calico 3.32.2 & kube-vip 1.2.3",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-flannel",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node Flannel",
		HardwareStack:  "VirtIO / CPU",
		KernelProfile:  "k8s",
		PreheatProfile: "flannel",
		Description:    "containerd 2.3.5, preheated Flannel 0.28.9 & kube-vip 1.2.3",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-intel",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node Intel GPU",
		HardwareStack:  "Intel Arc / Xe2",
		KernelProfile:  "k8s",
		PreheatProfile: "cilium",
		Description:    "containerd 2.3.5 + Intel drivers + Intel K8s Plugin",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "30-gpu-intel.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-amd",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node AMD GPU",
		HardwareStack:  "AMD ROCm 10",
		KernelProfile:  "k8s",
		PreheatProfile: "cilium",
		Description:    "containerd 2.3.5 + AMD ROCm 10 + AMD K8s Plugin",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "32-gpu-amd-rocm.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-nvidia",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node NVIDIA Mainstream",
		HardwareStack:  "NVIDIA Mainstream",
		KernelProfile:  "k8s",
		PreheatProfile: "cilium",
		Description:    "containerd 2.3.5 + NVIDIA 595 + NVIDIA K8s Plugin",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "34-gpu-nvidia-mainstream.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-nvidia-modern",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node NVIDIA Modern",
		HardwareStack:  "NVIDIA Modern",
		KernelProfile:  "k8s",
		PreheatProfile: "cilium",
		Description:    "containerd 2.3.5 + NVIDIA 615 + NVIDIA K8s Plugin",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "37-gpu-nvidia-modern.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},
	{
		ID:             "k8s-node-nvidia-bleeding",
		TierID:         "kubernetes",
		TierNumber:     3,
		Name:           "K8s Node NVIDIA Bleeding",
		HardwareStack:  "NVIDIA Bleeding",
		KernelProfile:  "k8s",
		PreheatProfile: "cilium",
		Description:    "containerd 2.3.5 + NVIDIA 615 + NVIDIA K8s Plugin",
		Provisioners:   []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "36-gpu-nvidia-bleeding.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "99-cleanup.sh"},
	},

	// Tier 4: K3s Edge Fleet (5 flavors)
	{
		ID:            "k3s-agent-generic",
		TierID:        "k3s",
		TierNumber:    4,
		Name:          "K3s Agent Generic",
		HardwareStack: "VirtIO / CPU",
		KernelProfile: "generic",
		Description:   "Lightweight K3s agent, containerd, Flannel (< 300MB RAM)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "52-k3s-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "k3s-agent-intel",
		TierID:        "k3s",
		TierNumber:    4,
		Name:          "K3s Agent Intel GPU",
		HardwareStack: "Intel GPU",
		KernelProfile: "generic",
		Description:   "K3s agent + Intel QuickSync (iHD) + Level Zero",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "30-gpu-intel.sh", "52-k3s-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "k3s-agent-amd",
		TierID:        "k3s",
		TierNumber:    4,
		Name:          "K3s Agent AMD GPU",
		HardwareStack: "AMD GPU",
		KernelProfile: "generic",
		Description:   "K3s agent + AMD ROCm 10 compute runtime + RADV Vulkan",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "32-gpu-amd-rocm.sh", "52-k3s-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "k3s-agent-nvidia",
		TierID:        "k3s",
		TierNumber:    4,
		Name:          "K3s Agent NVIDIA",
		HardwareStack: "NVIDIA Mainstream",
		KernelProfile: "generic",
		Description:   "K3s agent + NVIDIA 595 + Container Toolkit CDI",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "34-gpu-nvidia-mainstream.sh", "52-k3s-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "k3s-server-generic",
		TierID:        "k3s",
		TierNumber:    4,
		Name:          "K3s Server Generic",
		HardwareStack: "VirtIO / CPU",
		KernelProfile: "generic",
		Description:   "K3s standalone master, embedded SQLite, local-path storage",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "52-k3s-runtime.sh", "99-cleanup.sh"},
	},

	// Tier 5: CloudNative (4 flavors)
	{
		ID:            "cloudnative-generic",
		TierID:        "cloudnative",
		TierNumber:    5,
		Name:          "CloudNative Generic",
		HardwareStack: "VirtIO / Generic CPU",
		KernelProfile: "generic",
		Description:   "Immutable container host, read-only root, ephemeral tmpfs",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "61-cloudnative-immutable.sh", "99-cleanup.sh"},
	},
	{
		ID:            "cloudnative-k8s",
		TierID:        "cloudnative",
		TierNumber:    5,
		Name:          "CloudNative K8s",
		HardwareStack: "VirtIO / Generic CPU",
		KernelProfile: "k8s",
		Description:   "Immutable Kubernetes node, read-only root, containerd 2.3.5",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "50-k8s-runtime.sh", "55-k8s-precache.sh", "61-cloudnative-immutable.sh", "99-cleanup.sh"},
	},
	{
		ID:            "cloudnative-storage",
		TierID:        "cloudnative",
		TierNumber:    5,
		Name:          "CloudNative Storage",
		HardwareStack: "CNCF Storage",
		KernelProfile: "baremetal",
		Description:   "NVMe-oF (TCP), OpenZFS 2.3, iSCSI, multipath, NFS",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "65-storage-cncf.sh", "99-cleanup.sh"},
	},
	{
		ID:            "cloudnative-pg",
		TierID:        "cloudnative",
		TierNumber:    5,
		Name:          "CloudNative PG",
		HardwareStack: "Database (CNPG)",
		KernelProfile: "ai-infer",
		Description:   "CloudNativePG kernel tuning, hugepages, strict overcommit",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "70-cloudnative-pg.sh", "99-cleanup.sh"},
	},

	// Tier 6: AI Inference (6 flavors)
	{
		ID:            "ai-infer-generic",
		TierID:        "ai-infer",
		TierNumber:    6,
		Name:          "AI Infer Generic",
		HardwareStack: "CPU High-Throughput",
		KernelProfile: "ai-infer",
		Description:   "AMX, AVX-512, NUMA, vLLM/Ollama CPU, Docker CE",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "60-ai-infer-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "ai-infer-intel",
		TierID:        "ai-infer",
		TierNumber:    6,
		Name:          "AI Infer Intel",
		HardwareStack: "Intel Xe / Arc / Xe2",
		KernelProfile: "ai-infer",
		Description:   "Intel Level Zero, OpenVINO, IPEX-LLM, CDI, Docker CE",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "30-gpu-intel.sh", "40-docker-runtime.sh", "60-ai-infer-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "ai-infer-amd",
		TierID:        "ai-infer",
		TierNumber:    6,
		Name:          "AI Infer AMD",
		HardwareStack: "AMD ROCm 10",
		KernelProfile: "ai-infer",
		Description:   "AMD ROCm 10, /dev/kfd, RDNA 3/4 & Instinct, CDI, Docker CE",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "32-gpu-amd-rocm.sh", "40-docker-runtime.sh", "60-ai-infer-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "ai-infer-nvidia",
		TierID:        "ai-infer",
		TierNumber:    6,
		Name:          "AI Infer NVIDIA Mainstream",
		HardwareStack: "NVIDIA Mainstream",
		KernelProfile: "ai-infer",
		Description:   "Transparent hugepages, numactl, vLLM/Ollama (NVIDIA 595)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "34-gpu-nvidia-mainstream.sh", "40-docker-runtime.sh", "60-ai-infer-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "ai-infer-nvidia-modern",
		TierID:        "ai-infer",
		TierNumber:    6,
		Name:          "AI Infer NVIDIA Modern",
		HardwareStack: "NVIDIA Modern",
		KernelProfile: "ai-infer",
		Description:   "Transparent hugepages, numactl, vLLM/Ollama (NVIDIA 615)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "37-gpu-nvidia-modern.sh", "40-docker-runtime.sh", "60-ai-infer-runtime.sh", "99-cleanup.sh"},
	},
	{
		ID:            "ai-infer-nvidia-bleeding",
		TierID:        "ai-infer",
		TierNumber:    6,
		Name:          "AI Infer NVIDIA Bleeding",
		HardwareStack: "NVIDIA Bleeding",
		KernelProfile: "ai-infer",
		Description:   "Transparent hugepages, Blackwell RTX 5090 / B200 (NVIDIA 615)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "36-gpu-nvidia-bleeding.sh", "40-docker-runtime.sh", "60-ai-infer-runtime.sh", "99-cleanup.sh"},
	},

	// Tier 7: Homelab Appliances (5 flavors)
	{
		ID:            "appliance-vision-nvr",
		TierID:        "homelab",
		TierNumber:    7,
		Name:          "Appliance Vision NVR",
		HardwareStack: "Intel GPU + Coral TPU",
		KernelProfile: "generic",
		Description:   "Coral Edge TPU (gasket-dkms, udev), Intel QuickSync (iHD), CDI, Docker CE",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "75-appliance-vision.sh", "99-cleanup.sh"},
	},
	{
		ID:            "appliance-gateway-dns",
		TierID:        "homelab",
		TierNumber:    7,
		Name:          "Appliance Gateway DNS",
		HardwareStack: "VirtIO / Low-Power CPU",
		KernelProfile: "generic",
		Description:   "Port 53 stub disabled, WireGuard, line-rate forwarding (< 150MB RAM)",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "76-appliance-gateway.sh", "99-cleanup.sh"},
	},
	{
		ID:            "appliance-media-server",
		TierID:        "homelab",
		TierNumber:    7,
		Name:          "Appliance Media Server",
		HardwareStack: "Intel + AMD GPU + NAS",
		KernelProfile: "baremetal",
		Description:   "Intel QuickSync + AMD Mesa VA-API, nfs-common, cifs-utils, 4096KB readahead",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "77-appliance-media.sh", "99-cleanup.sh"},
	},
	{
		ID:            "appliance-ci-runner",
		TierID:        "homelab",
		TierNumber:    7,
		Name:          "Appliance CI Runner",
		HardwareStack: "Multi-Core CPU / DinD",
		KernelProfile: "generic",
		Description:   "QEMU ARM64/ARMv7 binfmt, Docker Buildx, git-lfs, 4GB tmpfs /tmp",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "78-appliance-runner.sh", "99-cleanup.sh"},
	},
	{
		ID:            "appliance-game-server",
		TierID:        "homelab",
		TierNumber:    7,
		Name:          "Appliance Game Server",
		HardwareStack: "High Clock CPU",
		KernelProfile: "generic",
		Description:   "32-bit i386 glibc, steamcmd, 16MB UDP socket buffer tuning, 1M file limits",
		Provisioners:  []string{"00-base-strip.sh", "05-hypervisor-agents.sh", "10-network-time.sh", "20-kernel-sysctl.sh", "25-baremetal-tuning.sh", "40-docker-runtime.sh", "79-appliance-game.sh", "99-cleanup.sh"},
	},
}

// All returns a slice of all 44 defined flavors.
func All() []Flavor {
	return append([]Flavor(nil), allFlavors...)
}

// Tiers returns all 7 workload tiers.
func Tiers() []Tier {
	return append([]Tier(nil), allTiers...)
}

var (
	flavorIndex = make(map[string]Flavor, len(allFlavors))
	tierIndex   = make(map[string][]Flavor)
)

func init() {
	for _, f := range allFlavors {
		flavorIndex[f.ID] = f
		tID := strings.ToLower(f.TierID)
		tierIndex[tID] = append(tierIndex[tID], f)
	}
}

// Get finds a flavor by exact ID.
func Get(id string) (Flavor, error) {
	if f, ok := flavorIndex[id]; ok {
		return f, nil
	}
	return Flavor{}, fmt.Errorf("flavor %q not found across 44 targets", id)
}

// FilterByTier returns all flavors belonging to a given tier.
func FilterByTier(tierID string) []Flavor {
	if list, ok := tierIndex[strings.ToLower(tierID)]; ok {
		return append([]Flavor(nil), list...)
	}
	return nil
}

// Search queries flavors by substring matching against ID, name, hardware stack, or description.
func Search(query string) []Flavor {
	q := strings.ToLower(query)
	var result []Flavor
	for _, f := range allFlavors {
		if strings.Contains(strings.ToLower(f.ID), q) ||
			strings.Contains(strings.ToLower(f.Name), q) ||
			strings.Contains(strings.ToLower(f.HardwareStack), q) ||
			strings.Contains(strings.ToLower(f.Description), q) {
			result = append(result, f)
		}
	}
	return result
}
