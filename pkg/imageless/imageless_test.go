// Copyright 2026 Lusoris
package imageless_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/imageless"
)

func TestGenerateApplyScript(t *testing.T) {
	opts := imageless.ApplyOptions{
		FlavorID: "docker-generic",
		DryRun:   false,
	}

	script, err := imageless.GenerateApplyScript(opts)
	require.NoError(t, err)

	assert.Contains(t, script, "#!/usr/bin/env bash")
	assert.Contains(t, script, "export FLAVOR=\"docker-generic\"")
	assert.Contains(t, script, "40-docker-runtime.sh")
}

func TestGenerateApplyScriptDryRun(t *testing.T) {
	opts := imageless.ApplyOptions{
		FlavorID: "base-generic",
		DryRun:   true,
	}

	script, err := imageless.GenerateApplyScript(opts)
	require.NoError(t, err)

	assert.Contains(t, script, "DRY-RUN")
	assert.Contains(t, script, "[SIMULATED] 00-base-strip.sh")
}

func TestGenerateBootCommand(t *testing.T) {
	cfg := imageless.MicroVMBootConfig{
		FlavorID:   "ai-infer-generic",
		KernelPath: "/custom/vmlinuz",
		InitrdPath: "/custom/initrd.img",
	}

	cmd, err := imageless.GenerateBootCommand(cfg)
	require.NoError(t, err)

	assert.Contains(t, cmd, "qemu-system-x86_64")
	assert.Contains(t, cmd, "-kernel /custom/vmlinuz")
	assert.Contains(t, cmd, "-initrd /custom/initrd.img")
	assert.Contains(t, cmd, "transparent_hugepage=madvise")
}
