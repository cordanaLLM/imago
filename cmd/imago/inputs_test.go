// Copyright 2026 Lusoris
package main

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Negative and boundary cases for the commands that take user input and print text another
// tool reads: cloud-init, boot, apply, standards, manifest, epics and milestones.

func TestCloudInitGenerateRefusesPlantedFlags(t *testing.T) {
	cases := []struct {
		args []string
		want string
	}{
		{[]string{"--hostname=x\nruncmd: [planted]"}, "hostname"},
		{[]string{"--hostname=" + strings.Repeat("a", 64)}, "hostname"},
		{[]string{"--user=root"}, "user"},
		{[]string{"--user=ops\n    sudo: ALL"}, "user"},
		{[]string{"--platform=esxi"}, "platform"},
		{[]string{"--flavor=no-such-flavor"}, "not found"},
	}
	for _, tc := range cases {
		out, err := executeCommand(append([]string{"cloud-init", "generate"}, tc.args...)...)
		require.Error(t, err, tc.args)
		assert.Contains(t, err.Error(), tc.want, tc.args)
		assert.NotContains(t, out, "#cloud-config", tc.args)
	}
}

func TestCloudInitGenerateBoundaryFlags(t *testing.T) {
	out, err := executeCommand("cloud-init", "generate", "--hostname="+strings.Repeat("a", 63),
		"--user=u"+strings.Repeat("x", 31), "--platform=HyperV")
	require.NoError(t, err)
	assert.Contains(t, out, `hostname: "`+strings.Repeat("a", 63)+`"`)
	assert.Contains(t, out, "hv_vmbus")
}

func TestCloudInitMetadataRefusesPlantedHostname(t *testing.T) {
	out, err := executeCommand("cloud-init", "metadata", "--hostname=x\ninstance-id: planted")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "hostname")
	assert.NotContains(t, out, "local-hostname")
}

func TestBootCommandQuotesEveryPath(t *testing.T) {
	out, err := executeCommand("boot", "--kernel=/boot/vmlinuz 7", "--root=/dev/$(id)")
	require.NoError(t, err)
	assert.Contains(t, out, "-kernel '/boot/vmlinuz 7'")
	assert.Contains(t, out, "-append 'root=/dev/$(id) ro ")
}

func TestBootCommandRefusesPlantedFlags(t *testing.T) {
	cases := [][]string{
		{"--kernel=vmlinuz"},
		{"--initrd=/i\ntouch planted"},
		{"--root=/dev/vda1 init=/bin/sh"},
		{"--flavor=no-such-flavor"},
	}
	for _, args := range cases {
		out, err := executeCommand(append([]string{"boot"}, args...)...)
		require.Error(t, err, args)
		assert.NotContains(t, out, "qemu-system-x86_64", args)
	}
}

func TestApplyRefusesUnknownFlavor(t *testing.T) {
	out, err := executeCommand("apply", "--flavor=no-such-flavor", "--dry-run")
	require.Error(t, err)
	assert.NotContains(t, out, "#!/usr/bin/env bash")
}

func TestStandardsGetRefusesUnknownFlavor(t *testing.T) {
	_, err := executeCommand("standards", "get", "no-such-flavor")
	require.Error(t, err)
	_, err = executeCommand("standards", "get")
	require.Error(t, err, "standards get takes exactly one flavor")
}

func TestListCommandsRefuseMissingFiles(t *testing.T) {
	absent := filepath.Join(t.TempDir(), "absent.json")
	for _, args := range [][]string{
		{"manifest", "validate", "--path", absent},
		{"epics", "list", "--path", absent},
		{"milestones", "list", "--path", absent},
	} {
		out, err := executeCommand(args...)
		require.Error(t, err, args)
		assert.NotContains(t, out, "✓", args)
	}
}

// The tables are read by people and by grep; a separator of NUL bytes breaks both.
func TestTableSeparatorsArePrintable(t *testing.T) {
	epics, err := filepath.Abs("../../.github/epics.json")
	require.NoError(t, err)
	milestones, err := filepath.Abs("../../.github/milestones.json")
	require.NoError(t, err)
	for _, args := range [][]string{
		{"standards", "list"},
		{"epics", "list", "--path", epics},
		{"milestones", "list", "--path", milestones},
	} {
		out, err := executeCommand(args...)
		require.NoError(t, err, args)
		assert.NotContains(t, out, "\x00", args)
		assert.Contains(t, out, strings.Repeat("-", 85), args)
	}
}
