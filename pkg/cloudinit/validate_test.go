// Copyright 2026 Lusoris
package cloudinit_test

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.yaml.in/yaml/v3"

	"github.com/cordanaLLM/imago/pkg/cloudinit"
)

// Every value the caller passes ends up in YAML that cloud-init executes as root. The tests
// parse the output with a real YAML reader: an accepted value must come back unchanged and
// add no key, and a value that could break out of its scalar must be refused.

const testKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGenericKeyForTestingOnly"

type userData struct {
	Hostname string `yaml:"hostname"`
	FQDN     string `yaml:"fqdn"`
	Timezone string `yaml:"timezone"`
	Users    []struct {
		Name string   `yaml:"name"`
		Keys []string `yaml:"ssh_authorized_keys"`
	} `yaml:"users"`
	Packages []string `yaml:"packages"`
}

// topLevelKeys are the keys the generator writes; a planted value must not add one.
var topLevelKeys = map[string]bool{
	"hostname": true, "fqdn": true, "manage_etc_hosts": true, "users": true, "ssh_pwauth": true,
	"disable_root": true, "timezone": true, "growpart": true, "packages": true, "final_message": true,
	"mounts": true, "write_files": true,
}

func parse(t *testing.T, text string) userData {
	t.Helper()
	var keys map[string]any
	require.NoError(t, yaml.Unmarshal([]byte(text), &keys))
	for key := range keys {
		assert.True(t, topLevelKeys[key], "unexpected top-level key %q", key)
	}
	var data userData
	require.NoError(t, yaml.Unmarshal([]byte(text), &data))
	return data
}

func TestUserDataRoundTripsEveryValue(t *testing.T) {
	cfg := cloudinit.DefaultConfig("base-generic")
	cfg.Hostname = "node-07"
	cfg.User = "ops"
	cfg.Timezone = "Europe/Berlin"
	cfg.SSHAuthorizedKeys = []string{testKey + " ops@node: #1"}
	cfg.ExtraPackages = []string{"g++", "libc6-dev", "python3.13"}
	text, err := cloudinit.GenerateUserData(cfg)
	require.NoError(t, err)

	data := parse(t, text)
	assert.Equal(t, "node-07", data.Hostname)
	assert.Equal(t, "node-07.local", data.FQDN)
	assert.Equal(t, "Europe/Berlin", data.Timezone)
	require.Len(t, data.Users, 1)
	assert.Equal(t, "ops", data.Users[0].Name)
	assert.Equal(t, cfg.SSHAuthorizedKeys, data.Users[0].Keys)
	assert.Equal(t, cfg.ExtraPackages, data.Packages)
}

func TestUserDataAcceptsBoundaryValues(t *testing.T) {
	cases := map[string]func(*cloudinit.Config){
		"hostname-63":      func(c *cloudinit.Config) { c.Hostname = strings.Repeat("a", 63) },
		"hostname-1":       func(c *cloudinit.Config) { c.Hostname = "a" },
		"hostname-digits":  func(c *cloudinit.Config) { c.Hostname = "0node9" },
		"user-32":          func(c *cloudinit.Config) { c.User = "u" + strings.Repeat("x", 31) },
		"user-underscore":  func(c *cloudinit.Config) { c.User = "svc_ops-1" },
		"platform-case":    func(c *cloudinit.Config) { c.Platform = "UnRaid" },
		"platform-empty":   func(c *cloudinit.Config) { c.Platform = "" },
		"timezone-deep":    func(c *cloudinit.Config) { c.Timezone = "America/Argentina/Buenos_Aires" },
		"timezone-offset":  func(c *cloudinit.Config) { c.Timezone = "Etc/GMT+5" },
		"package-plus":     func(c *cloudinit.Config) { c.ExtraPackages = []string{"g++"} },
		"key-sk":           func(c *cloudinit.Config) { c.SSHAuthorizedKeys = []string{"sk-ssh-ed25519@openssh.com AAAA"} },
		"key-ecdsa":        func(c *cloudinit.Config) { c.SSHAuthorizedKeys = []string{"ecdsa-sha2-nistp384 AAAA= ops"} },
		"key-blank-ignore": func(c *cloudinit.Config) { c.SSHAuthorizedKeys = []string{"  ", testKey} },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			cfg := cloudinit.DefaultConfig("base-generic")
			mutate(&cfg)
			require.NoError(t, cloudinit.Validate(cfg))
			text, err := cloudinit.GenerateUserData(cfg)
			require.NoError(t, err)
			parse(t, text)
		})
	}
}

func TestUserDataRefusesPlantedValues(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(*cloudinit.Config)
		want   string
	}{
		{"hostname-newline", func(c *cloudinit.Config) { c.Hostname = "x\nruncmd: [planted]" }, "hostname"},
		{"hostname-leading-hyphen", func(c *cloudinit.Config) { c.Hostname = "-node" }, "hostname"},
		{"hostname-trailing-hyphen", func(c *cloudinit.Config) { c.Hostname = "node-" }, "hostname"},
		{"hostname-64", func(c *cloudinit.Config) { c.Hostname = strings.Repeat("a", 64) }, "hostname"},
		{"hostname-dotted", func(c *cloudinit.Config) { c.Hostname = "node.example" }, "hostname"},
		{"hostname-flow", func(c *cloudinit.Config) { c.Hostname = "{a: b}" }, "hostname"},
		{"user-root", func(c *cloudinit.Config) { c.User = "root" }, "user"},
		{"user-upper", func(c *cloudinit.Config) { c.User = "Ops" }, "user"},
		{"user-33", func(c *cloudinit.Config) { c.User = "u" + strings.Repeat("x", 32) }, "user"},
		{"user-newline", func(c *cloudinit.Config) { c.User = "ops\n    sudo: ALL" }, "user"},
		{"user-leading-digit", func(c *cloudinit.Config) { c.User = "1ops" }, "user"},
		{"platform-unknown", func(c *cloudinit.Config) { c.Platform = "esxi" }, "platform"},
		{"flavor-unknown", func(c *cloudinit.Config) { c.Flavor = "no-such-flavor" }, "cloudinit:"},
		{"timezone-newline", func(c *cloudinit.Config) { c.Timezone = "UTC\nruncmd: [planted]" }, "timezone"},
		{"timezone-traversal", func(c *cloudinit.Config) { c.Timezone = "../etc/shadow" }, "timezone"},
		{"key-newline", func(c *cloudinit.Config) { c.SSHAuthorizedKeys = []string{testKey + "\nruncmd: [planted]"} }, "ssh key 0"},
		{"key-not-a-key", func(c *cloudinit.Config) { c.SSHAuthorizedKeys = []string{"hello world"} }, "ssh key 0"},
		{"key-second", func(c *cloudinit.Config) { c.SSHAuthorizedKeys = []string{testKey, "ssh-dss AAAA"} }, "ssh key 1"},
		{"package-shell", func(c *cloudinit.Config) { c.ExtraPackages = []string{"x; rm"} }, "package"},
		{"package-one-char", func(c *cloudinit.Config) { c.ExtraPackages = []string{"a"} }, "package"},
		{"package-upper", func(c *cloudinit.Config) { c.ExtraPackages = []string{"Vim"} }, "package"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cfg := cloudinit.DefaultConfig("base-generic")
			cfg.SSHAuthorizedKeys = []string{testKey}
			tc.mutate(&cfg)
			text, err := cloudinit.GenerateUserData(cfg)
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.want)
			assert.Empty(t, text)
		})
	}
}

func TestMetaDataRefusesPlantedHostname(t *testing.T) {
	for _, host := range []string{"x\ninstance-id: planted", "-node", strings.Repeat("a", 64)} {
		text, err := cloudinit.GenerateMetaData(cloudinit.Config{Hostname: host})
		require.Error(t, err, host)
		assert.Empty(t, text)
	}
}

func TestMetaDataRoundTrips(t *testing.T) {
	for host, want := range map[string]string{"": "lusoris-node", "n": "n", strings.Repeat("b", 63): strings.Repeat("b", 63)} {
		text, err := cloudinit.GenerateMetaData(cloudinit.Config{Hostname: host})
		require.NoError(t, err)
		var meta map[string]string
		require.NoError(t, yaml.Unmarshal([]byte(text), &meta))
		assert.Equal(t, map[string]string{"instance-id": want + "-01", "local-hostname": want}, meta)
	}
}
