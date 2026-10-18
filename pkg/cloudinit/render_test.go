// Copyright 2026 Lusoris
package cloudinit

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.yaml.in/yaml/v3"
)

var knownTopLevelKeys = map[string]bool{
	"hostname": true, "fqdn": true, "manage_etc_hosts": true, "users": true,
	"ssh_pwauth": true, "disable_root": true, "timezone": true, "growpart": true,
	"packages": true, "final_message": true, "mounts": true, "write_files": true,
}

func TestRenderUserDataPlantedHostileValues(t *testing.T) {
	cfg := DefaultConfig("base-generic")
	cfg.Hostname = "x\nmalicious: 1"
	cfg.SSHAuthorizedKeys = []string{"ssh-ed25519 AAAA\nruncmd: [reboot]"}
	cfg.ExtraPackages = []string{"a\"]\nruncmd: [x]"}

	require.Error(t, Validate(cfg), "Validate must refuse planted hostile values")

	text, err := renderUserData(cfg)
	require.NoError(t, err)

	var topKeys map[string]any
	require.NoError(t, yaml.Unmarshal([]byte(text), &topKeys))
	for k := range topKeys {
		assert.True(t, knownTopLevelKeys[k], "unexpected top-level key: %s", k)
	}

	var parsed struct {
		Hostname string `yaml:"hostname"`
		FQDN     string `yaml:"fqdn"`
		Users    []struct {
			SSHAuthorizedKeys []string `yaml:"ssh_authorized_keys"`
		} `yaml:"users"`
		Packages []string `yaml:"packages"`
	}
	require.NoError(t, yaml.Unmarshal([]byte(text), &parsed))
	assert.Equal(t, "x\nmalicious: 1", parsed.Hostname)
	assert.Equal(t, "x\nmalicious: 1.local", parsed.FQDN)
	require.Len(t, parsed.Users, 1)
	assert.Equal(t, []string{"ssh-ed25519 AAAA\nruncmd: [reboot]"}, parsed.Users[0].SSHAuthorizedKeys)
	assert.Equal(t, []string{"a\"]\nruncmd: [x]"}, parsed.Packages)
}

func TestRenderUserDataBoundaryEmptyKeysAndPackages(t *testing.T) {
	cfg := DefaultConfig("base-generic")
	cfg.SSHAuthorizedKeys = nil
	cfg.ExtraPackages = nil

	text, err := renderUserData(cfg)
	require.NoError(t, err)

	var raw map[string]any
	require.NoError(t, yaml.Unmarshal([]byte(text), &raw))
	assert.NotContains(t, raw, "packages")

	users, ok := raw["users"].([]any)
	require.True(t, ok)
	require.Len(t, users, 1)
	user0, ok := users[0].(map[string]any)
	require.True(t, ok)
	assert.NotContains(t, user0, "ssh_authorized_keys")

	// Whitespace-only keys are dropped too.
	cfg.SSHAuthorizedKeys = []string{"   ", "\t"}
	text2, err := renderUserData(cfg)
	require.NoError(t, err)
	var raw2 map[string]any
	require.NoError(t, yaml.Unmarshal([]byte(text2), &raw2))
	users2, ok := raw2["users"].([]any)
	require.True(t, ok)
	require.Len(t, users2, 1)
	user02, ok := users2[0].(map[string]any)
	require.True(t, ok)
	assert.NotContains(t, user02, "ssh_authorized_keys")
}

func TestRenderUserDataPlatformOutputs(t *testing.T) {
	type platformExpectation struct {
		mounts     [][]string
		writeFiles []userDataFile
	}
	expected := map[string]platformExpectation{
		"proxmox": {nil, nil},
		"unraid": {
			mounts: [][]string{{"share", "/mnt/share", "virtiofs", "rw,sync", "0", "0"}},
		},
		"truenas": {
			mounts: [][]string{{"nfs_share", "/mnt/truenas", "nfs", "rw,hard,intr,noatime", "0", "0"}},
			writeFiles: []userDataFile{{
				Path:    "/etc/udev/rules.d/99-truenas-virtio.rules",
				Content: "ACTION==\"add|change\", SUBSYSTEM==\"block\", KERNEL==\"sd[a-z]|vd[a-z]\", ATTR{queue/discard_max_bytes}!=\"0\", ATTR{queue/discard_granularity}!=\"0\"\n",
			}},
		},
		"macos": {
			mounts: [][]string{{"workspace", "/mnt/workspace", "virtiofs", "rw,sync", "0", "0"}},
		},
		"utm": {
			mounts: [][]string{{"workspace", "/mnt/workspace", "virtiofs", "rw,sync", "0", "0"}},
		},
		"windows": {
			writeFiles: []userDataFile{{
				Path:    "/etc/modules-load.d/hyperv.conf",
				Content: "hv_vmbus\nhv_storvsc\nhv_netvsc\nhv_utils\n",
			}},
		},
		"hyperv": {
			writeFiles: []userDataFile{{
				Path:    "/etc/modules-load.d/hyperv.conf",
				Content: "hv_vmbus\nhv_storvsc\nhv_netvsc\nhv_utils\n",
			}},
		},
	}
	for platform, want := range expected {
		t.Run(platform, func(t *testing.T) {
			cfg := DefaultConfig("base-generic")
			cfg.Platform = platform
			text, err := renderUserData(cfg)
			require.NoError(t, err)

			var parsed struct {
				Mounts     [][]string     `yaml:"mounts"`
				WriteFiles []userDataFile `yaml:"write_files"`
			}
			require.NoError(t, yaml.Unmarshal([]byte(text), &parsed))
			assert.Equal(t, want.mounts, parsed.Mounts)
			assert.Equal(t, want.writeFiles, parsed.WriteFiles)
		})
	}
}

// cloud-init reads user-data with PyYAML (YAML 1.1); a plain scalar like yes or 08 would come back
// as a bool or number there, so the encoder must quote every such string.
func TestRenderUserDataQuotesYAML11Ambiguous(t *testing.T) {
	cfg := DefaultConfig("base-generic")
	cfg.Hostname = "yes"
	cfg.Timezone = "1_000"
	cfg.ExtraPackages = []string{"off", "08", "0.1e3"}
	text, err := renderUserData(cfg)
	require.NoError(t, err)
	for _, line := range []string{`hostname: "yes"`, `timezone: "1_000"`, `  - "off"`, `  - "08"`, `  - "0.1e3"`} {
		assert.Contains(t, text, line+"\n")
	}
}
