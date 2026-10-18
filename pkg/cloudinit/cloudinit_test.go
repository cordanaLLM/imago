// Copyright 2026 Lusoris
package cloudinit_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.yaml.in/yaml/v3"

	"github.com/cordanaLLM/imago/pkg/cloudinit"
)

func TestGenerateUserDataDefault(t *testing.T) {
	cfg := cloudinit.DefaultConfig("base-generic")
	cfg.SSHAuthorizedKeys = []string{"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGenericKeyForTestingOnly"}

	userData, err := cloudinit.GenerateUserData(cfg)
	require.NoError(t, err)

	assert.Contains(t, userData, "#cloud-config")

	var parsed struct {
		Hostname    string `yaml:"hostname"`
		DisableRoot bool   `yaml:"disable_root"`
		SSHPwauth   bool   `yaml:"ssh_pwauth"`
		Users       []struct {
			SSHAuthorizedKeys []string `yaml:"ssh_authorized_keys"`
		} `yaml:"users"`
	}
	require.NoError(t, yaml.Unmarshal([]byte(userData), &parsed))
	assert.Equal(t, "lusoris-node", parsed.Hostname)
	assert.True(t, parsed.DisableRoot)
	assert.False(t, parsed.SSHPwauth)
	require.Len(t, parsed.Users, 1)
	assert.Contains(t, parsed.Users[0].SSHAuthorizedKeys, "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGenericKeyForTestingOnly")
}

func TestGenerateUserDataPlatforms(t *testing.T) {
	cfgUnraid := cloudinit.DefaultConfig("docker-generic")
	cfgUnraid.Platform = "unraid"
	udUnraid, err := cloudinit.GenerateUserData(cfgUnraid)
	require.NoError(t, err)
	assert.Contains(t, udUnraid, "virtiofs")

	cfgTrueNAS := cloudinit.DefaultConfig("docker-generic")
	cfgTrueNAS.Platform = "truenas"
	udTrueNAS, err := cloudinit.GenerateUserData(cfgTrueNAS)
	require.NoError(t, err)
	assert.Contains(t, udTrueNAS, "nfs_share")
	assert.Contains(t, udTrueNAS, "99-truenas-virtio.rules")

	cfgMacOS := cloudinit.DefaultConfig("base-generic")
	cfgMacOS.Platform = "macos"
	udMacOS, err := cloudinit.GenerateUserData(cfgMacOS)
	require.NoError(t, err)
	assert.Contains(t, udMacOS, "workspace")

	cfgWin := cloudinit.DefaultConfig("base-generic")
	cfgWin.Platform = "windows"
	udWin, err := cloudinit.GenerateUserData(cfgWin)
	require.NoError(t, err)
	assert.Contains(t, udWin, "hv_vmbus")
}

func TestGenerateMetaData(t *testing.T) {
	cfg := cloudinit.DefaultConfig("base-generic")
	cfg.Hostname = "custom-host"
	metaData, err := cloudinit.GenerateMetaData(cfg)
	require.NoError(t, err)

	var meta map[string]string
	require.NoError(t, yaml.Unmarshal([]byte(metaData), &meta))
	assert.Equal(t, "custom-host-01", meta["instance-id"])
	assert.Equal(t, "custom-host", meta["local-hostname"])
}
