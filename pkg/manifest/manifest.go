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

// KernelProvenance pins the kernel forge release a stream was verified from.
type KernelProvenance struct {
	Tag      string `json:"tag"`
	Revision string `json:"revision"`
	Bundle   string `json:"bundle"`
}

// KernelStream is one verified kernel stream pin. ArtifactDigest is the
// sha256: digest of the release SHA256SUMS the artifacts were checked against.
type KernelStream struct {
	Version        string           `json:"version"`
	ArtifactDigest string           `json:"artifact_digest"`
	Provenance     KernelProvenance `json:"provenance"`
}

// Kernel pins the kernel artifact contract with the kernel forge
// (cordanaLLM/nucleus). Streams is empty until a release has been verified.
type Kernel struct {
	Provider      string                  `json:"provider"`
	Contract      string                  `json:"contract"`
	DispatchEvent string                  `json:"dispatch_event,omitempty"`
	Streams       map[string]KernelStream `json:"streams"`
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
	Kernel     *Kernel    `json:"kernel,omitempty"`
	Time       Time       `json:"time"`
}

var (
	semverRegex        = regexp.MustCompile(`^[0-9]+\.[0-9]+(\.[0-9]+)?.*$`)
	sha256Regex        = regexp.MustCompile(`^[a-fA-F0-9]{64}$`)
	repoSlugRegex      = regexp.MustCompile(`^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`)
	streamNameRegex    = regexp.MustCompile(`^[a-z][a-z0-9-]{0,31}$`)
	kernelVersionRegex = regexp.MustCompile(`^[0-9][A-Za-z0-9._+-]{0,63}$`)
	kernelDigestRegex  = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)
	gitRevisionRegex   = regexp.MustCompile(`^[a-f0-9]{40}$`)
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
	if err := m.validateKernel(); err != nil {
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

// validateKernel checks the optional kernel contract pin. The section may pin
// zero streams (no kernel forge release verified yet) but never a partial one.
func (m *Manifest) validateKernel() error {
	if m.Kernel == nil {
		return nil
	}
	if !repoSlugRegex.MatchString(m.Kernel.Provider) {
		return fmt.Errorf("kernel provider must be an owner/repository slug, got %q", m.Kernel.Provider)
	}
	if m.Kernel.Contract == "" {
		return fmt.Errorf("kernel contract must not be empty")
	}
	if m.Kernel.Streams == nil {
		return fmt.Errorf("kernel streams must be an object (empty until a release is verified)")
	}
	for name, stream := range m.Kernel.Streams {
		if err := validateKernelStream(name, stream); err != nil {
			return err
		}
	}
	return nil
}

func validateKernelStream(name string, s KernelStream) error {
	if !streamNameRegex.MatchString(name) {
		return fmt.Errorf("kernel stream name %q must be a lowercase token", name)
	}
	if !kernelVersionRegex.MatchString(s.Version) {
		return fmt.Errorf("kernel stream %s version %q is not a bounded version token", name, s.Version)
	}
	if !kernelDigestRegex.MatchString(s.ArtifactDigest) {
		return fmt.Errorf("kernel stream %s artifact_digest must be sha256:<64 hex>, got %q", name, s.ArtifactDigest)
	}
	if !strings.HasPrefix(s.Provenance.Tag, "v") || len(s.Provenance.Tag) < 2 {
		return fmt.Errorf("kernel stream %s provenance tag %q must be a v-prefixed release tag", name, s.Provenance.Tag)
	}
	if !gitRevisionRegex.MatchString(s.Provenance.Revision) {
		return fmt.Errorf("kernel stream %s provenance revision must be a 40-character commit hash", name)
	}
	if s.Provenance.Bundle == "" {
		return fmt.Errorf("kernel stream %s provenance bundle must not be empty", name)
	}
	return nil
}
