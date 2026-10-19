// Copyright 2026 Lusoris
package manifest_test

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago"
	"github.com/cordanaLLM/imago/pkg/manifest"
	"github.com/google/jsonschema-go/jsonschema"
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
				K8sPlugin: "docker.io/intel/intel-device-plugins-operator:0.32.0",
			},
			AMD: manifest.AMDDrivers{
				ROCmBleedingVersion: "10.0",
				K8sPlugin:           "docker.io/rocm/k8s-device-plugin:1.32.0",
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
		{"empty_distro_name", func(m *manifest.Manifest) { m.Distro.Name = "" }, "distro name and release must not be empty"},
		{"empty_distro_release", func(m *manifest.Manifest) { m.Distro.Release = "" }, "distro name and release must not be empty"},
		{"invalid_iso_url_scheme", func(m *manifest.Manifest) { m.Distro.ISOUrl = "ftp://example.com/iso.iso" }, "must be an HTTP/HTTPS URL"},
		{"invalid_iso_checksum", func(m *manifest.Manifest) { m.Distro.ISOChecksum = "invalid-non-hex" }, "must be a 64-char hex"},
		{"invalid_k8s_semver", func(m *manifest.Manifest) { m.Kubernetes.Version = "invalid-semver" }, "is not valid semver"},
		{"missing_pause_image", func(m *manifest.Manifest) { m.Kubernetes.Images.Pause = "" }, "core images (pause, coredns, cilium) must be defined"},
		{"empty_k3s_version", func(m *manifest.Manifest) { m.K3s.Version = "" }, "k3s version must not be empty"},
		{"missing_intel_plugin", func(m *manifest.Manifest) { m.Drivers.Intel.K8sPlugin = "" }, "intel k8s_plugin must not be empty"},
		{"missing_amd_rocm", func(m *manifest.Manifest) { m.Drivers.AMD.ROCmBleedingVersion = "" }, "amd rocm coordinates must not be empty"},
		{"missing_nvidia_drivers", func(m *manifest.Manifest) { m.Drivers.NVIDIA.MainstreamDriver = "" }, "nvidia generational driver branches must not be empty"},
		{"missing_containerd_runtime", func(m *manifest.Manifest) { m.Runtimes.Containerd = "" }, "containerd and docker_ce runtimes must not be empty"},
		{"missing_cdebug_tool", func(m *manifest.Manifest) { m.Tools.Cdebug = "" }, "cdebug tool version must not be empty"},
		{"missing_anycast_nts", func(m *manifest.Manifest) { m.Time.AnycastNTS = "" }, "time anycast_nts must not be empty"},
		{"empty_stratum1_nts", func(m *manifest.Manifest) { m.Time.Stratum1NTS = nil }, "time stratum1_nts mesh must contain at least one endpoint"},
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

func pinnedKernel() *manifest.Kernel {
	return &manifest.Kernel{
		Provider:      "cordanaLLM/nucleus",
		Contract:      "imago.nucleus.kernel-artifact.v1",
		DispatchEvent: "kernel_release_published",
		Streams: map[string]manifest.KernelStream{
			"mainstream": {
				Version:        "7.2.4-lusoris1",
				ArtifactDigest: "sha256:" + strings.Repeat("a", 64),
				Provenance: manifest.KernelProvenance{
					Tag:      "v7.2.4-lusoris1",
					Revision: "188c35d188c35d188c35d188c35d188c35d18800",
					Bundle:   "SHA256SUMS.bundle",
				},
			},
		},
	}
}

func TestValidateKernelPin(t *testing.T) {
	m := validTestManifest()
	require.NoError(t, m.Validate(), "kernel section is optional")

	m.Kernel = pinnedKernel()
	require.NoError(t, m.Validate(), "a fully pinned stream is accepted")

	m.Kernel.Streams = map[string]manifest.KernelStream{}
	require.NoError(t, m.Validate(), "zero pinned streams is the state before the first verified release")

	actual, err := manifest.Load("../../versions.json")
	require.NoError(t, err)
	require.NotNil(t, actual.Kernel, "versions.json must carry the kernel contract pin")
	assert.Equal(t, "cordanaLLM/nucleus", actual.Kernel.Provider)
	assert.Equal(t, "imago.nucleus.kernel-artifact.v1", actual.Kernel.Contract)
}

func TestValidateKernelPinNegative(t *testing.T) {
	tests := []struct {
		name      string
		mutate    func(k *manifest.Kernel)
		expectErr string
	}{
		{"provider_not_slug", func(k *manifest.Kernel) { k.Provider = "nucleus" }, "kernel provider must be an owner/repository slug"},
		{"empty_contract", func(k *manifest.Kernel) { k.Contract = "" }, "kernel contract must not be empty"},
		{"nil_streams", func(k *manifest.Kernel) { k.Streams = nil }, "kernel streams must be an object"},
		{"stream_name", func(k *manifest.Kernel) { k.Streams["Nightly"] = k.Streams["mainstream"] }, "must be a lowercase token"},
		{"missing_artifact_digest", func(k *manifest.Kernel) {
			s := k.Streams["mainstream"]
			s.ArtifactDigest = ""
			k.Streams["mainstream"] = s
		}, "artifact_digest must be sha256:<64 hex>"},
		{"tag_without_v", func(k *manifest.Kernel) {
			s := k.Streams["mainstream"]
			s.Provenance.Tag = "7.2.4-lusoris1"
			k.Streams["mainstream"] = s
		}, "must be a v-prefixed release tag"},
		{"short_revision", func(k *manifest.Kernel) {
			s := k.Streams["mainstream"]
			s.Provenance.Revision = "188c35d"
			k.Streams["mainstream"] = s
		}, "provenance revision must be a 40-character commit hash"},
		{"empty_bundle", func(k *manifest.Kernel) {
			s := k.Streams["mainstream"]
			s.Provenance.Bundle = ""
			k.Streams["mainstream"] = s
		}, "provenance bundle must not be empty"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			m := validTestManifest()
			m.Kernel = pinnedKernel()
			tc.mutate(m.Kernel)
			err := m.Validate()
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.expectErr)
		})
	}
}

func TestVersionsSchemaResolves(t *testing.T) {
	require.NotEmpty(t, imago.VersionsSchema)

	rs, err := manifest.ResolvedSchema()
	require.NoError(t, err)
	require.NotNil(t, rs)

	var s jsonschema.Schema
	require.NoError(t, json.Unmarshal(imago.VersionsSchema, &s))
	resolved, err := s.Resolve(&jsonschema.ResolveOptions{})
	require.NoError(t, err)
	require.NotNil(t, resolved)
}

func loadBaseVersionsMap(t *testing.T) map[string]any {
	t.Helper()
	rootPath, err := filepath.Abs("../../versions.json")
	require.NoError(t, err)

	data, err := os.ReadFile(rootPath)
	require.NoError(t, err)

	var doc map[string]any
	require.NoError(t, json.Unmarshal(data, &doc))
	return doc
}

func writeTempJSON(t *testing.T, doc any) string {
	t.Helper()
	data, err := json.Marshal(doc)
	require.NoError(t, err)

	tmpFile := filepath.Join(t.TempDir(), "manifest-test.json")
	require.NoError(t, os.WriteFile(tmpFile, data, 0o600))
	return tmpFile
}

func TestLoadPlantedSchemaErrors(t *testing.T) {
	tests := []struct {
		name      string
		mutate    func(doc map[string]any)
		expectErr string
	}{
		{
			name: "missing_required_build",
			mutate: func(doc map[string]any) {
				delete(doc, "build")
			},
			expectErr: `validating root: required: missing properties: ["build"]`,
		},
		{
			name: "missing_nested_k8s_plugin",
			mutate: func(doc map[string]any) {
				delete(doc["drivers"].(map[string]any)["intel"].(map[string]any), "k8s_plugin")
			},
			expectErr: `validating /properties/drivers/properties/intel: required: missing properties: ["k8s_plugin"]`,
		},
		{
			// ctr has no docker.io default; this reference failed the k8s-node-intel build.
			name: "image_without_registry_host",
			mutate: func(doc map[string]any) {
				intel := doc["drivers"].(map[string]any)["intel"].(map[string]any)
				intel["k8s_plugin"] = "intel/intel-gpu-plugin:0.36.0"
			},
			expectErr: `validating /properties/drivers/properties/intel/properties/k8s_plugin: validating /$defs/imageRef: pattern: "intel/intel-gpu-plugin:0.36.0"`,
		},
		{
			name: "wrong_pattern_distro_version",
			mutate: func(doc map[string]any) {
				distro := doc["distro"].(map[string]any)
				distro["version"] = "v26.04"
			},
			expectErr: `validating /properties/distro/properties/version: pattern: "v26.04"`,
		},
		{
			name: "unknown_type_stratum1_nts",
			mutate: func(doc map[string]any) {
				timeMap := doc["time"].(map[string]any)
				timeMap["stratum1_nts"] = "ptbtime1.ptb.de"
			},
			expectErr: `validating /properties/time/properties/stratum1_nts: type:`,
		},
		{
			name: "empty_stratum1_nts",
			mutate: func(doc map[string]any) {
				timeMap := doc["time"].(map[string]any)
				timeMap["stratum1_nts"] = []any{}
			},
			expectErr: `validating /properties/time/properties/stratum1_nts: minItems:`,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			doc := loadBaseVersionsMap(t)
			tc.mutate(doc)
			path := writeTempJSON(t, doc)

			m, err := manifest.Load(path)
			require.Error(t, err)
			assert.Nil(t, m)
			assert.Contains(t, err.Error(), "manifest: schema")
			assert.Contains(t, err.Error(), tc.expectErr)
		})
	}
}

func minimalKubernetesDoc() map[string]any {
	return map[string]any{
		"version":     "1.37.0",
		"major_minor": "1.37",
		"images": map[string]any{
			"pause":              "registry.example.com/pause:3.10",
			"coredns":            "registry.example.com/coredns:1.12.0",
			"cilium":             "registry.example.com/cilium:1.20.1",
			"cilium_operator":    "registry.example.com/operator:1.20.1",
			"kube_vip":           "registry.example.com/kube-vip:1.2.3",
			"node_exporter":      "registry.example.com/node-exporter:1.12.1",
			"calico_cni":         "registry.example.com/calico-cni:3.32.2",
			"calico_node":        "registry.example.com/calico-node:3.32.2",
			"calico_controllers": "registry.example.com/calico-controllers:3.32.2",
			"flannel":            "registry.example.com/flannel:0.28.9",
			"flannel_cni":        "registry.example.com/flannel-cni:1.6.2",
		},
	}
}

func minimalDriversDoc() map[string]any {
	return map[string]any{
		"intel": map[string]any{
			"k8s_plugin": "registry.example.com/intel-plugin:1.0",
		},
		"amd": map[string]any{
			"rocm_legacy_version":   "6.0",
			"rocm_bleeding_version": "7.2.4",
			"rocm_repo":             "https://repo.example.com/rocm",
			"rocm_apt_suite":        "noble",
			"k8s_plugin":            "registry.example.com/amd-plugin:1.0",
		},
		"nvidia": map[string]any{
			"legacy_driver":     "535",
			"mainstream_driver": "565",
			"modern_driver":     "610",
			"bleeding_driver":   "615",
			"datacenter_driver": "565-open",
			"cuda_legacy":       "12.2",
			"cuda_mainstream":   "12.8",
			"cuda_modern":       "13.3",
			"cuda_bleeding":     "13.4",
			"container_toolkit": "1.17",
			"k8s_plugin":        "registry.example.com/nvidia-plugin:1.0",
		},
	}
}

func minimalBuildDoc() map[string]any {
	return map[string]any{
		"packer": map[string]any{
			"version":                "1.11.2",
			"sha256_linux_amd64":     strings.Repeat("b", 64),
			"zip_sha256_linux_amd64": strings.Repeat("c", 64),
		},
		"packer_plugins": map[string]any{
			"qemu": map[string]any{
				"source":             "github.com/hashicorp/qemu",
				"version":            "1.1.1",
				"sha256_linux_amd64": strings.Repeat("d", 64),
			},
			"proxmox": map[string]any{
				"source":             "github.com/hashicorp/proxmox",
				"version":            "1.2.1",
				"sha256_linux_amd64": strings.Repeat("e", 64),
			},
		},
	}
}

func minimalValidDoc() map[string]any {
	return map[string]any{
		"distro": map[string]any{
			"name":         "ubuntu",
			"release":      "resolute",
			"version":      "26.04",
			"iso_url":      "https://example.com/iso.iso",
			"iso_checksum": strings.Repeat("a", 64),
		},
		"kubernetes": minimalKubernetesDoc(),
		"drivers":    minimalDriversDoc(),
		"k3s":        map[string]any{"version": "v1.31.5+k3s1"},
		"runtimes": map[string]any{
			"containerd": "2.3.5",
			"docker_ce":  "29.8.0",
			"crun":       "1.20",
		},
		"tools": map[string]any{"cdebug": "0.5.1"},
		"build": minimalBuildDoc(),
		"time": map[string]any{
			"anycast_nts":   "time.cloudflare.com",
			"stratum1_nts":  []any{"ptbtime1.ptb.de"},
			"fallback_pool": "pool.ntp.org",
		},
	}
}

func TestLoadMinimalValidDoc(t *testing.T) {
	doc := minimalValidDoc()
	path := writeTempJSON(t, doc)

	m, err := manifest.Load(path)
	require.NoError(t, err)
	require.NotNil(t, m)
	assert.Equal(t, "ubuntu", m.Distro.Name)
	assert.Equal(t, "1.37.0", m.Kubernetes.Version)
}

func TestLoadRefusesDocValidForStructChecksButInvalidForSchema(t *testing.T) {
	doc := loadBaseVersionsMap(t)
	// Delete top-level "build", which the schema requires but Manifest struct does not model.
	delete(doc, "build")
	path := writeTempJSON(t, doc)

	data, err := os.ReadFile(path)
	require.NoError(t, err)

	var structManifest manifest.Manifest
	require.NoError(t, json.Unmarshal(data, &structManifest))
	// Proves Go struct checks alone consider this document valid:
	require.NoError(t, structManifest.Validate())

	// Proves Load enforces the JSON Schema and refuses the document:
	m, err := manifest.Load(path)
	require.Error(t, err)
	assert.Nil(t, m)
	assert.Contains(t, err.Error(), "manifest: schema")
}

func TestLoadPlantedDuplicateKeyErrors(t *testing.T) {
	tests := []struct {
		name      string
		mutate    func(raw []byte) []byte
		expectKey string
	}{
		{
			name: "duplicate_top_level_build",
			mutate: func(raw []byte) []byte {
				return bytes.Replace(raw, []byte(`"build": {`), []byte(`"build": {}, "build": {`), 1)
			},
			expectKey: "build",
		},
		{
			name: "duplicate_nested_distro_key",
			mutate: func(raw []byte) []byte {
				return bytes.Replace(raw, []byte(`"name": "ubuntu",`), []byte(`"name": "ubuntu", "name": "debian",`), 1)
			},
			expectKey: "name",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			rootPath, err := filepath.Abs("../../versions.json")
			require.NoError(t, err)

			orig, err := os.ReadFile(rootPath)
			require.NoError(t, err)

			corrupted := tc.mutate(orig)
			require.NotEqual(t, orig, corrupted, "mutation must alter versions.json bytes")

			tmpFile := filepath.Join(t.TempDir(), "versions-duplicate.json")
			require.NoError(t, os.WriteFile(tmpFile, corrupted, 0o600))

			m, err := manifest.Load(tmpFile)
			require.Error(t, err)
			assert.Nil(t, m)
			assert.Contains(t, err.Error(), "manifest: parse")
			assert.Contains(t, err.Error(), tc.expectKey)
		})
	}
}

func TestLoadVersionsJSONMatchesV1(t *testing.T) {
	rootPath, err := filepath.Abs("../../versions.json")
	require.NoError(t, err)

	m, err := manifest.Load(rootPath)
	require.NoError(t, err)
	require.NotNil(t, m)

	data, err := os.ReadFile(rootPath)
	require.NoError(t, err)

	var v1Manifest manifest.Manifest
	require.NoError(t, json.Unmarshal(data, &v1Manifest))

	assert.Equal(t, &v1Manifest, m)
}
