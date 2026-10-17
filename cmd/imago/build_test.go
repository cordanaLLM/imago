// Copyright 2026 Lusoris
package main

import (
	"context"
	"errors"
	"path/filepath"
	"testing"

	"github.com/cordanaLLM/imago/pkg/builder"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type cliBuildExecutor struct {
	result builder.Result
	err    error
}

func (e cliBuildExecutor) Execute(_ context.Context, req builder.Request) (builder.Result, error) {
	e.result.Backend, e.result.Flavor = req.Backend, req.Flavor
	return e.result, e.err
}

func TestBuildCommandLocalExecutor(t *testing.T) {
	previous := newLocalBuildExecutor
	t.Cleanup(func() { newLocalBuildExecutor = previous })
	newLocalBuildExecutor = func(packerDir, outputDir, versions string) (builder.Executor, error) {
		assert.Equal(t, "templates", packerDir)
		assert.Equal(t, "artifacts", outputDir)
		assert.Equal(t, "pins.json", versions)
		return cliBuildExecutor{result: builder.Result{Success: true, Status: builder.StatusSucceeded,
			RunLog: "run.log", Artifact: "image.qcow2", ArtifactSHA256: "digest"}}, nil
	}
	out, err := executeCommand("build", "--backend=local", "--flavor=docker-generic", "--packer-dir=templates", "--output-dir=artifacts", "--versions=pins.json")
	require.NoError(t, err)
	assert.Contains(t, out, "==> Build succeeded: docker-generic\nRun log: run.log\nArtifact: image.qcow2\nSHA256: digest\n")
}

func TestBuildCommandLocalFailure(t *testing.T) {
	previous := newLocalBuildExecutor
	t.Cleanup(func() { newLocalBuildExecutor = previous })
	newLocalBuildExecutor = func(_, _, _ string) (builder.Executor, error) {
		return cliBuildExecutor{err: builder.ErrPackerFailed}, nil
	}
	out, err := executeCommand("build", "--backend=local")
	require.ErrorIs(t, err, builder.ErrPackerFailed)
	assert.NotContains(t, out, "==> Build succeeded")
}

func TestBuildCommandSkipsExecutorConstruction(t *testing.T) {
	previous := newLocalBuildExecutor
	t.Cleanup(func() { newLocalBuildExecutor = previous })
	newLocalBuildExecutor = func(_, _, _ string) (builder.Executor, error) {
		t.Fatal("executor constructed for a dry run or invalid input")
		return nil, errors.New("unexpected constructor")
	}
	_, err := executeCommand("build", "--backend=local", "--dry-run", "--versions=missing.json")
	require.NoError(t, err)
	_, err = executeCommand("build", "--backend=local", "--flavor=unknown")
	require.ErrorContains(t, err, "invalid flavor")
}

func TestLoadLocalBuildExecutor(t *testing.T) {
	executor, err := loadLocalBuildExecutor("templates", "artifacts", filepath.Join("..", "..", "pkg", "builder", "testdata", "pins.json"))
	require.NoError(t, err)
	local, ok := executor.(builder.LocalExecutor)
	require.True(t, ok)
	assert.Equal(t, "templates", local.PackerDir)
	assert.Equal(t, "artifacts", local.OutputDir)
	assert.Equal(t, filepath.Join("artifacts", "logs"), local.LogDir)
	_, err = loadLocalBuildExecutor("templates", "artifacts", "missing-pins.json")
	require.ErrorContains(t, err, "local build pins")
}
