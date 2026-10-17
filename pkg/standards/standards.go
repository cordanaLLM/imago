// Copyright 2026 Lusoris
// Package standards provides machine-verifiable hardening specifications
// and compliance assertions across all 44 image flavors.
package standards

import (
	"strings"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

// Standard describes the hardening and verification requirements for a flavor.
type Standard struct {
	FlavorID         string            `json:"flavor_id"`
	Tier             string            `json:"tier"`
	SecurityBaseline string            `json:"security_baseline"`
	RequiredPackages []string          `json:"required_packages"`
	KernelParameters map[string]string `json:"kernel_parameters"`
	SystemdUnits     []string          `json:"systemd_units"`
	CDISpecRequired  bool              `json:"cdi_spec_required"`
	MaxIdleMemoryMB  int               `json:"max_idle_memory_mb,omitempty"`
}

// Get returns the hardening standard for a specific flavor.
func Get(flavorID string) (Standard, error) {
	fl, err := flavors.Get(flavorID)
	if err != nil {
		return Standard{}, err
	}

	std := Standard{
		FlavorID:         fl.ID,
		Tier:             fl.TierID,
		SecurityBaseline: "CIS Ubuntu Linux 24.04 Benchmark L2 / BSI IT-Grundschutz SYS.1.3",
		RequiredPackages: []string{"chrony", "qemu-guest-agent", "open-vm-tools", "acpid", "zstd"},
		KernelParameters: map[string]string{
			"net.ipv4.tcp_congestion_control": "bbr",
			"net.core.default_qdisc":          "fq",
			"vm.swappiness":                   "10",
			"kernel.sysrq":                    "0",
			"fs.protected_hardlinks":          "1",
			"fs.protected_symlinks":           "1",
		},
		SystemdUnits: []string{
			"chrony.service",
			"qemu-guest-agent.service",
			"acpid.service",
		},
	}

	enrichTierStandard(&std, fl)
	return std, nil
}

// tierRules adds the requirements of each tier on top of the common baseline.
var tierRules = map[string]func(*Standard, flavors.Flavor){
	"containers":  enrichContainers,
	"kubernetes":  enrichKubernetes,
	"k3s":         enrichK3s,
	"cloudnative": enrichCloudNative,
	"ai-infer":    enrichAIInfer,
	"homelab":     enrichHomelab,
}

func enrichTierStandard(std *Standard, fl flavors.Flavor) {
	if rule, ok := tierRules[fl.TierID]; ok {
		rule(std, fl)
	}
}

// hasGPUVendor reports whether the flavor ID names a GPU vendor whose devices need a CDI spec.
func hasGPUVendor(id string) bool {
	return strings.Contains(id, "nvidia") || strings.Contains(id, "intel") || strings.Contains(id, "amd")
}

func enrichContainers(std *Standard, fl flavors.Flavor) {
	if strings.HasPrefix(fl.ID, "podman") {
		std.RequiredPackages = append(std.RequiredPackages, "podman", "buildah", "skopeo")
	} else {
		std.RequiredPackages = append(std.RequiredPackages, "docker-ce", "docker-compose-plugin")
		std.SystemdUnits = append(std.SystemdUnits, "docker.service")
	}
	if hasGPUVendor(fl.ID) {
		std.CDISpecRequired = true
	}
}

func enrichKubernetes(std *Standard, _ flavors.Flavor) {
	std.SecurityBaseline = "CIS Kubernetes Benchmark v1.37 / CIS OS L2"
	std.RequiredPackages = append(std.RequiredPackages, "containerd", "kubelet", "kubeadm", "kubectl")
	std.KernelParameters["net.bridge.bridge-nf-call-iptables"] = "1"
	std.KernelParameters["net.ipv4.ip_forward"] = "1"
	std.SystemdUnits = append(std.SystemdUnits, "containerd.service", "kubelet.service")
}

func enrichK3s(std *Standard, fl flavors.Flavor) {
	std.RequiredPackages = append(std.RequiredPackages, "curl", "iptables")
	if fl.ID == "k3s-server-generic" {
		std.SystemdUnits = append(std.SystemdUnits, "k3s.service")
	} else {
		std.SystemdUnits = append(std.SystemdUnits, "k3s-agent.service")
	}
	std.MaxIdleMemoryMB = 300
}

func enrichCloudNative(std *Standard, fl flavors.Flavor) {
	switch fl.ID {
	case "cloudnative-storage":
		std.RequiredPackages = append(std.RequiredPackages, "zfsutils-linux", "nvme-cli", "multipath-tools")
	case "cloudnative-pg":
		std.KernelParameters["vm.overcommit_memory"] = "2"
		std.KernelParameters["vm.overcommit_ratio"] = "80"
	}
}

func enrichAIInfer(std *Standard, fl flavors.Flavor) {
	std.RequiredPackages = append(std.RequiredPackages, "numactl", "docker-ce")
	std.KernelParameters["vm.zone_reclaim_mode"] = "0"
	if hasGPUVendor(fl.ID) {
		std.CDISpecRequired = true
	}
}

// homelabRules holds the requirements of each appliance; the homelab tier has no common part.
var homelabRules = map[string]func(*Standard){
	"appliance-vision-nvr": func(std *Standard) {
		std.RequiredPackages = append(std.RequiredPackages, "gasket-dkms", "intel-media-va-driver-non-free", "docker-ce")
		std.CDISpecRequired = true
	},
	"appliance-gateway-dns": func(std *Standard) {
		std.RequiredPackages = append(std.RequiredPackages, "wireguard", "iptables")
		std.MaxIdleMemoryMB = 150
	},
	"appliance-game-server": func(std *Standard) {
		std.RequiredPackages = append(std.RequiredPackages, "steamcmd", "docker-ce")
		std.KernelParameters["net.core.rmem_max"] = "16777216"
		std.KernelParameters["net.core.wmem_max"] = "16777216"
	},
	"appliance-media-server": func(std *Standard) {
		std.RequiredPackages = append(std.RequiredPackages, "nfs-common", "cifs-utils", "docker-ce")
	},
	"appliance-ci-runner": func(std *Standard) {
		std.RequiredPackages = append(std.RequiredPackages, "docker-ce", "git-lfs")
	},
}

func enrichHomelab(std *Standard, fl flavors.Flavor) {
	if rule, ok := homelabRules[fl.ID]; ok {
		rule(std)
	}
}

// All returns hardening standards for all 44 flavors.
func All() []Standard {
	allFlavors := flavors.All()
	standards := make([]Standard, 0, len(allFlavors))
	for _, f := range allFlavors {
		if std, err := Get(f.ID); err == nil {
			standards = append(standards, std)
		}
	}
	return standards
}
