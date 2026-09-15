// Copyright 2026 Lusoris
// Package manifest parses, loads, and validates the versions.json Single Source of Truth.
package manifest

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Distro defines upstream base distribution coordinates.
type Distro struct {
	Name        string `json:"name"`
	Release     string `json:"release"`
	Version     string `json:"version"`
	ISOUrl      string `json:"iso_url"`
	ISOChecksum string `json:"iso_checksum"`
}

// KubernetesImages maps container images preheated for Kubernetes clusters.
type KubernetesImages struct {
	Pause             string `json:"pause"`
	CoreDNS           string `json:"coredns"`
	Cilium            string `json:"cilium"`
	CiliumOperator    string `json:"cilium_operator"`
	KubeVIP           string `json:"kube_vip"`
	NodeExporter      string `json:"node_exporter"`
	CalicoCNI         string `json:"calico_cni"`
	CalicoNode        string `json:"calico_node"`
	CalicoControllers string `json:"calico_controllers"`
	Flannel           string `json:"flannel"`
	FlannelCNI        string `json:"flannel_cni"`
}

// Kubernetes defines K8s version and preheat images.
type Kubernetes struct {
	Version    string           `json:"version"`
	MajorMinor string           `json:"major_minor"`
	Images     KubernetesImages `json:"images"`
}

// IntelDrivers defines Intel GPU driver coordinates.
type IntelDrivers struct {
	K8sPlugin string `json:"k8s_plugin"`
}

// AMDDrivers defines AMD ROCm versions and K8s plugin.
type AMDDrivers struct {
	ROCmLegacyVersion   string `json:"rocm_legacy_version"`
	ROCmBleedingVersion string `json:"rocm_bleeding_version"`
	K8sPlugin           string `json:"k8s_plugin"`
}

// NVIDIADrivers defines the generational NVIDIA driver matrix.
type NVIDIADrivers struct {
	LegacyDriver     string `json:"legacy_driver"`
	MainstreamDriver string `json:"mainstream_driver"`
	ModernDriver     string `json:"modern_driver"`
	BleedingDriver   string `json:"bleeding_driver"`
	DatacenterDriver string `json:"datacenter_driver"`
	CUDALegacy       string `json:"cuda_legacy"`
	CUDAMainstream   string `json:"cuda_mainstream"`
	CUDAModern       string `json:"cuda_modern"`
	CUDABleeding     string `json:"cuda_bleeding"`
	ContainerToolkit string `json:"container_toolkit"`
	K8sPlugin        string `json:"k8s_plugin"`
}

// Drivers defines GPU hardware acceleration coordinates.
type Drivers struct {
	Intel  IntelDrivers  `json:"intel"`
	AMD    AMDDrivers    `json:"amd"`
	NVIDIA NVIDIADrivers `json:"nvidia"`
}

// K3s defines the lightweight Kubernetes engine version.
type K3s struct {
	Version string `json:"version"`
}

// Runtimes defines container runtime coordinates.
type Runtimes struct {
	Containerd        string `json:"containerd"`
	DockerCE          string `json:"docker_ce"`
	Crun              string `json:"crun,omitempty"`
	StargzSnapshotter string `json:"stargz_snapshotter,omitempty"`
}

// Tools defines diagnostic and sandboxing tooling coordinates.
type Tools struct {
	Cdebug string `json:"cdebug,omitempty"`
	Enroot string `json:"enroot,omitempty"`
}

// Time defines resilient Anycast and Stratum-1 NTS endpoints.
type Time struct {
	AnycastNTS   string   `json:"anycast_nts"`
	Stratum1NTS  []string `json:"stratum1_nts"`
	FallbackPool string   `json:"fallback_pool"`
}

// Manifest represents the complete versions.json specification.
type Manifest struct {
	Schema     string     `json:"$schema,omitempty"`
	Distro     Distro     `json:"distro"`
	Kubernetes Kubernetes `json:"kubernetes"`
	Drivers    Drivers    `json:"drivers"`
	K3s        K3s        `json:"k3s"`
	Runtimes   Runtimes   `json:"runtimes"`
	Tools      Tools      `json:"tools,omitempty"`
	Time       Time       `json:"time"`
}

var (
	semverRegex = regexp.MustCompile(`^[0-9]+\.[0-9]+(\.[0-9]+)?.*$`)
	sha256Regex = regexp.MustCompile(`^[a-fA-F0-9]{64}$`)
)

// Load reads and parses a versions.json file.
func Load(path string) (*Manifest, error) {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("manifest: read %s: %w", path, err)
	}

	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("manifest: parse %s: %w", path, err)
	}

	if err := m.Validate(); err != nil {
		return nil, fmt.Errorf("manifest: validate %s: %w", path, err)
	}

	return &m, nil
}

// Validate asserts that all mandatory semantic invariants are fulfilled.
func (m *Manifest) Validate() error {
	if err := m.validateDistro(); err != nil {
		return err
	}
	if err := m.validateKubernetes(); err != nil {
		return err
	}
	if err := m.validateDrivers(); err != nil {
		return err
	}
	if err := m.validateRuntimes(); err != nil {
		return err
	}
	if err := m.validateTools(); err != nil {
		return err
	}
	return m.validateTime()
}

func (m *Manifest) validateDistro() error {
	if m.Distro.Name == "" || m.Distro.Release == "" {
		return fmt.Errorf("distro name and release must not be empty")
	}
	if !strings.HasPrefix(m.Distro.ISOUrl, "http://") && !strings.HasPrefix(m.Distro.ISOUrl, "https://") {
		return fmt.Errorf("distro iso_url must be an HTTP/HTTPS URL, got %q", m.Distro.ISOUrl)
	}
	chk := m.Distro.ISOChecksum
	if !sha256Regex.MatchString(chk) && !strings.HasPrefix(chk, "file:") && !strings.HasPrefix(chk, "sha256:") {
		return fmt.Errorf("distro iso_checksum must be a 64-char hex or file:/sha256: specifier, got %q", chk)
	}
	return nil
}

func (m *Manifest) validateKubernetes() error {
	if !semverRegex.MatchString(m.Kubernetes.Version) {
		return fmt.Errorf("kubernetes version %q is not valid semver", m.Kubernetes.Version)
	}
	if m.Kubernetes.Images.Pause == "" || m.Kubernetes.Images.CoreDNS == "" || m.Kubernetes.Images.Cilium == "" {
		return fmt.Errorf("kubernetes core images (pause, coredns, cilium) must be defined")
	}
	if m.K3s.Version == "" {
		return fmt.Errorf("k3s version must not be empty")
	}
	return nil
}

func (m *Manifest) validateDrivers() error {
	if m.Drivers.Intel.K8sPlugin == "" {
		return fmt.Errorf("intel k8s_plugin must not be empty")
	}
	if m.Drivers.AMD.ROCmBleedingVersion == "" || m.Drivers.AMD.K8sPlugin == "" {
		return fmt.Errorf("amd rocm coordinates must not be empty")
	}
	if m.Drivers.NVIDIA.MainstreamDriver == "" || m.Drivers.NVIDIA.ModernDriver == "" || m.Drivers.NVIDIA.BleedingDriver == "" {
		return fmt.Errorf("nvidia generational driver branches must not be empty")
	}
	return nil
}

func (m *Manifest) validateRuntimes() error {
	if m.Runtimes.Containerd == "" || m.Runtimes.DockerCE == "" {
		return fmt.Errorf("containerd and docker_ce runtimes must not be empty")
	}
	return nil
}

func (m *Manifest) validateTools() error {
	if m.Tools.Cdebug == "" {
		return fmt.Errorf("cdebug tool version must not be empty")
	}
	return nil
}

func (m *Manifest) validateTime() error {
	if m.Time.AnycastNTS == "" {
		return fmt.Errorf("time anycast_nts must not be empty")
	}
	if len(m.Time.Stratum1NTS) == 0 {
		return fmt.Errorf("time stratum1_nts mesh must contain at least one endpoint")
	}
	return nil
}
