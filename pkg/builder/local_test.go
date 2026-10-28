// Copyright 2026 Lusoris
package builder_test

import (
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/cordanaLLM/imago/pkg/builder"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type fakeRunner struct {
	run func(context.Context, string, io.Writer, string, ...string) error
}

func (r fakeRunner) Run(ctx context.Context, dir string, log io.Writer, name string, args ...string) error {
	return r.run(ctx, dir, log, name, args...)
}

func localFixture(t *testing.T) (builder.LocalExecutor, string) {
	t.Helper()
	root := t.TempDir()
	pins, err := builder.LoadPins(filepath.Join("testdata", "pins.json"))
	require.NoError(t, err)
	e := builder.LocalExecutor{Pins: pins, PackerDir: filepath.Join(root, "packer"),
		OutputDir: filepath.Join(root, "output"), LogDir: filepath.Join(root, "logs"), PluginDir: filepath.Join(root, "plugins"),
		LookPath: func(name string) (string, error) { return "/fake/" + name, nil }}
	plugin := filepath.Join(e.PluginDir, "github.com", "hashicorp", "qemu",
		fmt.Sprintf("packer-plugin-qemu_v%s_x5.0_%s_%s", pins.QemuPluginVersion, runtime.GOOS, runtime.GOARCH))
	data, err := os.ReadFile(filepath.Join("testdata", "qemu-plugin"))
	require.NoError(t, err)
	require.NoError(t, os.MkdirAll(filepath.Dir(plugin), 0o755))
	require.NoError(t, os.WriteFile(plugin, data, 0o755))
	return e, plugin
}

func localRequest() builder.Request {
	return builder.Request{Backend: builder.BackendLocal, Flavor: "docker-generic"}
}

func successfulRunner(t *testing.T, e builder.LocalExecutor) fakeRunner {
	t.Helper()
	return fakeRunner{run: func(ctx context.Context, dir string, log io.Writer, name string, args ...string) error {
		deadline, ok := ctx.Deadline()
		require.True(t, ok)
		assert.InDelta(t, (2 * time.Hour).Seconds(), time.Until(deadline).Seconds(), 2)
		assert.Equal(t, e.PackerDir, dir)
		assert.Equal(t, "/fake/packer", name)
		if args[0] == "version" {
			_, err := fmt.Fprintln(log, "Packer v"+e.Pins.PackerVersion+"\nextra version notice")
			return err
		}
		assert.Equal(t, []string{"build", "-only=docker-generic.qemu.image", "-var", "output_dir=" + e.OutputDir,
			"-var", "flavor=docker-generic", "-var", "image_name=imago-cloud", "."}, args)
		artifact := filepath.Join(e.OutputDir, "docker-generic", "imago-cloud-docker-generic.qcow2")
		if err := os.MkdirAll(filepath.Dir(artifact), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(artifact, []byte("built qcow2 bytes"), 0o644); err != nil {
			return err
		}
		_, err := fmt.Fprintln(log, "fake Packer build complete")
		return err
	}}
}

func TestLocalExecutorSuccess(t *testing.T) {
	e, _ := localFixture(t)
	e.Runner = successfulRunner(t, e)
	res, err := builder.DispatchWith(context.Background(), localRequest(), map[builder.Backend]builder.Executor{builder.BackendLocal: e})
	require.NoError(t, err)
	assert.True(t, res.Success)
	assert.Equal(t, builder.StatusSucceeded, res.Status)
	assert.Equal(t, fmt.Sprintf("%x", sha256.Sum256([]byte("built qcow2 bytes"))), res.ArtifactSHA256)
	assert.Equal(t, filepath.Join(e.OutputDir, "docker-generic", "imago-cloud-docker-generic.qcow2"), res.Artifact)
	assert.Regexp(t, `docker-generic-\d{8}T\d{6}Z\.log$`, res.RunLog)
	log, err := os.ReadFile(res.RunLog)
	require.NoError(t, err)
	assert.Contains(t, string(log), "fake Packer build complete")
}

func TestLocalExecutorPreflightRefusals(t *testing.T) {
	for _, tc := range []struct {
		name string
		want error
	}{
		{"version mismatch", builder.ErrPackerVersionMismatch},
		{"plugin checksum", builder.ErrPluginChecksumMismatch},
		{"plugin missing", builder.ErrPluginMissing},
	} {
		t.Run(tc.name, func(t *testing.T) {
			e, plugin := localFixture(t)
			version := "Packer v" + e.Pins.PackerVersion
			switch tc.name {
			case "version mismatch":
				version = "Packer v0.0.0"
			case "plugin checksum":
				require.NoError(t, os.WriteFile(plugin, []byte("tampered"), 0o755))
			case "plugin missing":
				require.NoError(t, os.Remove(plugin))
			}
			e.Runner = fakeRunner{run: func(_ context.Context, _ string, log io.Writer, _ string, args ...string) error {
				require.Equal(t, []string{"version"}, args)
				_, err := fmt.Fprintln(log, version)
				return err
			}}
			res, err := e.Execute(context.Background(), localRequest())
			require.ErrorIs(t, err, tc.want)
			if tc.name == "version mismatch" {
				assert.Contains(t, err.Error(), "want")
				assert.Contains(t, err.Error(), "got")
			}
			assert.False(t, res.Success)
			assert.Empty(t, res.ArtifactSHA256)
		})
	}
}

// writeStaleArtifact leaves a qcow2 dated before the build, as an earlier run would.
func writeStaleArtifact(e builder.LocalExecutor) error {
	artifact := filepath.Join(e.OutputDir, "docker-generic", "imago-cloud-docker-generic.qcow2")
	if err := os.MkdirAll(filepath.Dir(artifact), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(artifact, []byte("earlier qcow2"), 0o644); err != nil {
		return err
	}
	old := time.Now().Add(-time.Hour)
	return os.Chtimes(artifact, old, old)
}

func TestLocalExecutorBuildFailures(t *testing.T) {
	exitErr := errors.New("exit status 42")
	for _, tc := range []struct {
		name string
		want error
	}{
		{"nonzero exit", builder.ErrPackerFailed},
		{"artifact missing", builder.ErrArtifactMissing},
		{"artifact stale", builder.ErrArtifactMissing},
		{"timeout", builder.ErrBuildTimeout},
	} {
		t.Run(tc.name, func(t *testing.T) {
			e, _ := localFixture(t)
			e.Runner = fakeRunner{run: func(ctx context.Context, _ string, log io.Writer, _ string, args ...string) error {
				if args[0] == "version" {
					_, err := fmt.Fprintln(log, "Packer v"+e.Pins.PackerVersion)
					return err
				}
				if tc.name == "timeout" {
					<-ctx.Done()
					return ctx.Err()
				}
				if tc.name == "nonzero exit" {
					return exitErr
				}
				if tc.name == "artifact stale" {
					return writeStaleArtifact(e)
				}
				return nil
			}}
			req := localRequest()
			if tc.name == "timeout" {
				req.Timeout = 25 * time.Millisecond
			}
			res, err := e.Execute(context.Background(), req)
			require.ErrorIs(t, err, tc.want)
			assert.False(t, res.Success)
			assert.NotEmpty(t, res.RunLog)
			if tc.name == "timeout" {
				require.ErrorIs(t, err, context.DeadlineExceeded)
			}
			if tc.name == "nonzero exit" {
				require.ErrorIs(t, err, exitErr)
				assert.Contains(t, err.Error(), res.RunLog)
			}
		})
	}
}

func TestLocalExecutorBoundaries(t *testing.T) {
	e, _ := localFixture(t)
	e.Runner = fakeRunner{run: func(context.Context, string, io.Writer, string, ...string) error {
		t.Fatal("runner called for a refused request")
		return nil
	}}
	for _, tc := range []struct {
		name string
		req  builder.Request
		want error
	}{
		{"other backend", builder.Request{Backend: builder.BackendGitea, Flavor: "base-generic"}, builder.ErrBackendUnavailable},
		{"expired timeout", builder.Request{Backend: builder.BackendLocal, Flavor: "base-generic", Timeout: -time.Second}, builder.ErrBuildTimeout},
	} {
		t.Run(tc.name, func(t *testing.T) {
			res, err := e.Execute(context.Background(), tc.req)
			require.ErrorIs(t, err, tc.want)
			assert.False(t, res.Success)
		})
	}
	req := localRequest()
	req.DryRun = true
	res, err := builder.DispatchWith(context.Background(), req, map[builder.Backend]builder.Executor{builder.BackendLocal: e})
	require.NoError(t, err)
	assert.Equal(t, builder.StatusPlanned, res.Status)
	req.DryRun = false
	req.Backend = builder.BackendGitHub
	_, err = builder.DispatchWith(context.Background(), req, map[builder.Backend]builder.Executor{builder.BackendLocal: e})
	require.ErrorIs(t, err, builder.ErrBackendUnavailable)
}

func TestLocalExecutorPluginEnvironmentDefault(t *testing.T) {
	e, _ := localFixture(t)
	t.Setenv("PACKER_PLUGIN_PATH", e.PluginDir)
	e.PluginDir = ""
	e.Runner = successfulRunner(t, e)
	res, err := e.Execute(context.Background(), localRequest())
	require.NoError(t, err)
	assert.True(t, res.Success)
}

func TestLocalExecutorRelativeOutputPaths(t *testing.T) {
	e, _ := localFixture(t)
	cwd, err := os.Getwd()
	require.NoError(t, err)
	relative, err := filepath.Rel(cwd, e.OutputDir)
	require.NoError(t, err)
	absolute := e.OutputDir
	e.OutputDir = relative
	e.Runner = fakeRunner{run: func(_ context.Context, _ string, log io.Writer, _ string, args ...string) error {
		if args[0] == "version" {
			_, err := fmt.Fprintln(log, "Packer v"+e.Pins.PackerVersion)
			return err
		}
		assert.Contains(t, strings.Join(args, "|"), "output_dir="+absolute)
		return errors.New("stop after path check")
	}}
	_, err = e.Execute(context.Background(), localRequest())
	require.ErrorIs(t, err, builder.ErrPackerFailed)
}
