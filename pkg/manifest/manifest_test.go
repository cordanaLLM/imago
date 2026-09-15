// Copyright 2026 Lusoris
package manifest_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/manifest"
)

func validTestManifest() *manifest.Manifest {
	return &manifest.Manifest{
		Distro: manifest.Distro{
			Name:        "ubuntu",
			Release:     "resolute",
			Version:     "26.04",
			ISOUrl:      "https://releases.ubuntu.com/resolute/ubuntu-26.04-live-server-amd64.iso",
			ISOChecksum: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		},
		Kubernetes: manifest.Kubernetes{
			Version: "1.37.0",
			Images: manifest.KubernetesImages{
				Pause:   "registry.k8s.io/pause:3.10",
				CoreDNS: "registry.k8s.io/coredns/coredns:v1.12.0",
				Cilium:  "quay.io/cilium/cilium:v1.20.1",
			},
		},
		K3s: manifest.K3s{
			Version: "v1.31.5+k3s1",
		},
		Drivers: manifest.Drivers{
			Intel: manifest.IntelDrivers{
				K8sPlugin: "intel/intel-device-plugins-operator:0.32.0",
			},
			AMD: manifest.AMDDrivers{
				ROCmBleedingVersion: "10.0",
				K8sPlugin:           "rocm/k8s-device-plugin:1.32.0",
			},
			NVIDIA: manifest.NVIDIADrivers{
				MainstreamDriver: "565",
				ModernDriver:     "610",
				BleedingDriver:   "615",
			},
		},
		Runtimes: manifest.Runtimes{
			Containerd: "2.3.5",
			DockerCE:   "29.8.0",
			Crun:       "1.20",
		},
		Tools: manifest.Tools{
			Cdebug: "0.5.1",
			Enroot: "3.4.1",
		},
		Time: manifest.Time{
			AnycastNTS:   "time.cloudflare.com",
			Stratum1NTS:  []string{"ptbtime1.ptb.de", "nts.netnod.se"},
			FallbackPool: "pool.ntp.org",
		},
	}
}

func TestLoadActualVersionsJSON(t *testing.T) {
	rootPath, err := filepath.Abs("../../versions.json")
	require.NoError(t, err)

	m, err := manifest.Load(rootPath)
	require.NoError(t, err)
	require.NotNil(t, m)

	assert.Equal(t, "ubuntu", m.Distro.Name)
	assert.Equal(t, "resolute", m.Distro.Release)
	assert.NotEmpty(t, m.Distro.ISOUrl)
	assert.NotEmpty(t, m.Distro.ISOChecksum)

	assert.NotEmpty(t, m.Kubernetes.Version)
	assert.NotEmpty(t, m.Kubernetes.Images.Cilium)
	assert.NotEmpty(t, m.Kubernetes.Images.CalicoCNI)
	assert.NotEmpty(t, m.Kubernetes.Images.Flannel)

	assert.NotEmpty(t, m.Drivers.NVIDIA.MainstreamDriver)
	assert.NotEmpty(t, m.Drivers.NVIDIA.ModernDriver)
	assert.NotEmpty(t, m.Drivers.NVIDIA.BleedingDriver)

	assert.NotEmpty(t, m.K3s.Version)
	assert.NotEmpty(t, m.Runtimes.Containerd)
	assert.NotEmpty(t, m.Runtimes.DockerCE)
	assert.NotEmpty(t, m.Runtimes.Crun)
	assert.NotEmpty(t, m.Runtimes.StargzSnapshotter)
	assert.NotEmpty(t, m.Tools.Cdebug)
	assert.NotEmpty(t, m.Tools.Enroot)

	assert.NotEmpty(t, m.Time.AnycastNTS)
	assert.NotEmpty(t, m.Time.Stratum1NTS)
}

func TestLoadInvalidFilePaths(t *testing.T) {
	_, err := manifest.Load("non-existent-path.json")
	assert.Error(t, err)

	// Corrupted JSON file
	tmp, err := os.CreateTemp("", "invalid-*.json")
	require.NoError(t, err)
	defer func() { _ = os.Remove(tmp.Name()) }()

	_, err = tmp.WriteString("{invalid-json")
	require.NoError(t, err)
	_ = tmp.Close()

	_, err = manifest.Load(tmp.Name())
	assert.Error(t, err)
}

func TestValidateDeepNegativeCases(t *testing.T) {
	tests := []struct {
		name      string
		mutate    func(m *manifest.Manifest)
		expectErr string
	}{
		{
			name: "empty_distro_name",
			mutate: func(m *manifest.Manifest) {
				m.Distro.Name = ""
			},
			expectErr: "distro name and release must not be empty",
		},
		{
			name: "empty_distro_release",
			mutate: func(m *manifest.Manifest) {
				m.Distro.Release = ""
			},
			expectErr: "distro name and release must not be empty",
		},
		{
			name: "invalid_iso_url_scheme",
			mutate: func(m *manifest.Manifest) {
				m.Distro.ISOUrl = "ftp://example.com/iso.iso"
			},
			expectErr: "must be an HTTP/HTTPS URL",
		},
		{
			name: "invalid_iso_checksum",
			mutate: func(m *manifest.Manifest) {
				m.Distro.ISOChecksum = "invalid-non-hex"
			},
			expectErr: "must be a 64-char hex",
		},
		{
			name: "invalid_k8s_semver",
			mutate: func(m *manifest.Manifest) {
				m.Kubernetes.Version = "invalid-semver"
			},
			expectErr: "is not valid semver",
		},
		{
			name: "missing_pause_image",
			mutate: func(m *manifest.Manifest) {
				m.Kubernetes.Images.Pause = ""
			},
			expectErr: "core images (pause, coredns, cilium) must be defined",
		},
		{
			name: "empty_k3s_version",
			mutate: func(m *manifest.Manifest) {
				m.K3s.Version = ""
			},
			expectErr: "k3s version must not be empty",
		},
		{
			name: "missing_intel_plugin",
			mutate: func(m *manifest.Manifest) {
				m.Drivers.Intel.K8sPlugin = ""
			},
			expectErr: "intel k8s_plugin must not be empty",
		},
		{
			name: "missing_amd_rocm",
			mutate: func(m *manifest.Manifest) {
				m.Drivers.AMD.ROCmBleedingVersion = ""
			},
			expectErr: "amd rocm coordinates must not be empty",
		},
		{
			name: "missing_nvidia_drivers",
			mutate: func(m *manifest.Manifest) {
				m.Drivers.NVIDIA.MainstreamDriver = ""
			},
			expectErr: "nvidia generational driver branches must not be empty",
		},
		{
			name: "missing_containerd_runtime",
			mutate: func(m *manifest.Manifest) {
				m.Runtimes.Containerd = ""
			},
			expectErr: "containerd and docker_ce runtimes must not be empty",
		},
		{
			name: "missing_cdebug_tool",
			mutate: func(m *manifest.Manifest) {
				m.Tools.Cdebug = ""
			},
			expectErr: "cdebug tool version must not be empty",
		},
		{
			name: "missing_anycast_nts",
			mutate: func(m *manifest.Manifest) {
				m.Time.AnycastNTS = ""
			},
			expectErr: "time anycast_nts must not be empty",
		},
		{
			name: "empty_stratum1_nts",
			mutate: func(m *manifest.Manifest) {
				m.Time.Stratum1NTS = nil
			},
			expectErr: "time stratum1_nts mesh must contain at least one endpoint",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			m := validTestManifest()
			tc.mutate(m)
			err := m.Validate()
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.expectErr)
		})
	}
}
