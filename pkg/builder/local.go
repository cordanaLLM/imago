// Copyright 2026 Lusoris
package builder

import (
	"bytes"
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// Local execution failures support errors.Is, including wrapped process errors.
var (
	ErrPackerVersionMismatch  = errors.New("Packer version mismatch")
	ErrPluginChecksumMismatch = errors.New("QEMU plugin checksum mismatch")
	ErrPluginMissing          = errors.New("QEMU plugin missing")
	ErrPackerFailed           = errors.New("Packer failed")
	ErrBuildTimeout           = errors.New("build timed out")
	ErrArtifactMissing        = errors.New("build artifact missing")
)

// Runner executes one command in dir and sends both output streams to log.
type Runner interface {
	Run(ctx context.Context, dir string, log io.Writer, name string, args ...string) error
}

type execRunner struct{ pluginDir string }

func (r execRunner) Run(ctx context.Context, dir string, log io.Writer, name string, args ...string) error {
	// #nosec G204 -- name is the packer binary LookPath resolved, args are fixed flags plus a flavor execute checked with Validate; no shell runs.
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir, cmd.Stdout, cmd.Stderr = dir, log, log
	cmd.Env = append(os.Environ(), "PACKER_PLUGIN_PATH="+r.pluginDir)
	cmd.Cancel = func() error { return cmd.Process.Kill() }
	cmd.WaitDelay = 5 * time.Second
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("run %s: %w", name, err)
	}
	return nil
}

// LocalExecutor runs the installed Packer and verifies the resulting QCOW2 file.
// It never installs tools or plugins. Zero Timeout on a request means two hours.
type LocalExecutor struct {
	Runner    Runner
	Pins      Pins
	PackerDir string
	OutputDir string
	LogDir    string
	PluginDir string
	LookPath  func(string) (string, error)
}

const localImageName = "lusoris-cloud"

// Execute accepts local requests only, including when called outside DispatchWith.
func (e LocalExecutor) Execute(ctx context.Context, req Request) (res Result, err error) {
	res = Result{Backend: req.Backend, Flavor: req.Flavor, DryRun: req.DryRun}
	if req.Backend != BackendLocal || req.DryRun {
		return Dispatch(ctx, req)
	}
	timeout := req.Timeout
	if timeout == 0 {
		timeout = 2 * time.Hour
	}
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	defer func() {
		err = localContextError(ctx, err)
		if err != nil {
			res.Success, res.Status = false, ""
		}
	}()
	return e.execute(ctx, req)
}

func localContextError(ctx context.Context, err error) error {
	if ctx.Err() == nil {
		return err
	}
	err = errors.Join(err, fmt.Errorf("builder: local context: %w", ctx.Err()))
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return errors.Join(ErrBuildTimeout, err)
	}
	return err
}

func (e LocalExecutor) execute(ctx context.Context, req Request) (res Result, err error) {
	res = Result{Backend: req.Backend, Flavor: req.Flavor}
	if err = ctx.Err(); err != nil {
		return res, err
	}
	if err = Validate(req.Backend, req.Flavor); err != nil {
		return res, err
	}
	if err = e.Pins.validate(); err != nil {
		return res, fmt.Errorf("builder: local pins: %w", err)
	}
	if err = e.defaults(); err != nil {
		return res, err
	}
	packer, err := e.LookPath("packer")
	if err != nil {
		return res, fmt.Errorf("%w: find packer: %w", ErrPackerVersionMismatch, err)
	}
	if err = e.checkVersion(ctx, packer); err != nil {
		return res, err
	}
	if err = e.checkPlugin(ctx); err != nil {
		return res, err
	}
	started := time.Now()
	res.RunLog, err = e.build(ctx, req.Flavor, packer)
	if err != nil {
		return res, err
	}
	res.Artifact = filepath.Join(e.OutputDir, req.Flavor, localImageName+"-"+req.Flavor+".qcow2")
	res.ArtifactSHA256, err = freshFileSHA256(ctx, res.Artifact, started)
	if err != nil {
		return res, fmt.Errorf("%w: %q: %w", ErrArtifactMissing, res.Artifact, err)
	}
	res.Success, res.Status = true, StatusSucceeded
	res.Message = "local Packer build completed and artifact verified"
	return res, nil
}

func (e *LocalExecutor) defaults() error {
	if e.PackerDir == "" {
		e.PackerDir = "./packer"
	}
	if e.OutputDir == "" {
		e.OutputDir = "./output-images"
	}
	if e.LogDir == "" {
		e.LogDir = filepath.Join(e.OutputDir, "logs")
	}
	if e.PluginDir == "" {
		var err error
		e.PluginDir, err = defaultPluginDir()
		if err != nil {
			return fmt.Errorf("%w: %w", ErrPluginMissing, err)
		}
	}
	if err := e.absolutePaths(); err != nil {
		return err
	}
	if e.Runner == nil {
		e.Runner = execRunner{pluginDir: e.PluginDir}
	}
	if e.LookPath == nil {
		e.LookPath = exec.LookPath
	}
	return nil
}

func (e *LocalExecutor) absolutePaths() error {
	for _, path := range []*string{&e.PackerDir, &e.OutputDir, &e.LogDir, &e.PluginDir} {
		absolute, err := filepath.Abs(*path)
		if err != nil {
			return fmt.Errorf("builder: resolve %q: %w", *path, err)
		}
		*path = absolute
	}
	return nil
}

func defaultPluginDir() (string, error) {
	// Packer 1.16.x: PACKER_PLUGIN_PATH takes precedence over config/plugins.
	// https://developer.hashicorp.com/packer/docs/configure#packer_plugin_path
	if dir := os.Getenv("PACKER_PLUGIN_PATH"); dir != "" {
		return dir, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("builder: plugin home: %w", err)
	}
	return filepath.Join(home, ".config", "packer", "plugins"), nil
}

func (e LocalExecutor) checkVersion(ctx context.Context, packer string) error {
	var output bytes.Buffer
	if err := e.Runner.Run(ctx, e.PackerDir, &output, packer, "version"); err != nil {
		return fmt.Errorf("%w: packer version: %w", ErrPackerVersionMismatch, err)
	}
	first, _, _ := strings.Cut(output.String(), "\n")
	got := strings.TrimSuffix(first, "\r")
	want := "Packer v" + e.Pins.PackerVersion
	if got != want {
		return fmt.Errorf("%w: want %q, got %q", ErrPackerVersionMismatch, want, got)
	}
	return nil
}

func (e LocalExecutor) checkPlugin(ctx context.Context) error {
	binary := fmt.Sprintf("packer-plugin-qemu_v%s_x5.0_%s_%s", e.Pins.QemuPluginVersion, runtime.GOOS, runtime.GOARCH)
	path := filepath.Join(e.PluginDir, "github.com", "hashicorp", "qemu", binary)
	got, err := fileSHA256(ctx, path)
	if errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("%w: %q: %w", ErrPluginMissing, path, err)
	}
	if err != nil {
		return fmt.Errorf("%w: %q: %w", ErrPluginChecksumMismatch, path, err)
	}
	if !strings.EqualFold(got, e.Pins.QemuPluginSHA256) {
		return fmt.Errorf("%w: %q: want %s, got %s", ErrPluginChecksumMismatch, path, e.Pins.QemuPluginSHA256, got)
	}
	return nil
}

func (e LocalExecutor) build(ctx context.Context, flavor, packer string) (path string, err error) {
	if err := os.MkdirAll(e.LogDir, 0o750); err != nil {
		return "", fmt.Errorf("%w: create log directory: %w", ErrPackerFailed, err)
	}
	path = filepath.Join(e.LogDir, flavor+"-"+time.Now().UTC().Format("20060102T150405Z")+".log")
	log, err := os.OpenFile(filepath.Clean(path), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return path, fmt.Errorf("%w: open log %q: %w", ErrPackerFailed, path, err)
	}
	defer func() {
		if closeErr := log.Close(); closeErr != nil {
			err = errors.Join(err, fmt.Errorf("%w: close log %q: %w", ErrPackerFailed, path, closeErr))
		}
	}()
	args := []string{"build", "-only=" + flavor + ".qemu.image", "-var", "output_dir=" + e.OutputDir,
		"-var", "flavor=" + flavor, "-var", "image_name=" + localImageName, "."}
	if err := e.Runner.Run(ctx, e.PackerDir, log, packer, args...); err != nil {
		return path, fmt.Errorf("%w: flavor %q; run log %q: %w", ErrPackerFailed, flavor, path, err)
	}
	return path, nil
}

// freshFileSHA256 refuses an artifact last written before the build started, so a
// leftover file from an earlier run never stands in as evidence for this one.
func freshFileSHA256(ctx context.Context, path string, started time.Time) (string, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return "", fmt.Errorf("stat file: %w", err)
	}
	if info.ModTime().Before(started.Truncate(time.Second)) {
		return "", fmt.Errorf("stale file: modified %s, build started %s",
			info.ModTime().UTC().Format(time.RFC3339), started.UTC().Format(time.RFC3339))
	}
	return fileSHA256(ctx, path)
}

// fileSHA256 accepts regular files only and reads at most their measured size.
func fileSHA256(ctx context.Context, path string) (digest string, err error) {
	info, err := os.Lstat(path)
	if err != nil {
		return "", fmt.Errorf("stat file: %w", err)
	}
	if !info.Mode().IsRegular() {
		return "", fmt.Errorf("not a regular file: %q", path)
	}
	file, err := os.Open(filepath.Clean(path))
	if err != nil {
		return "", fmt.Errorf("open file: %w", err)
	}
	defer func() {
		if closeErr := file.Close(); closeErr != nil {
			err = errors.Join(err, fmt.Errorf("close file: %w", closeErr))
		}
	}()
	hash := sha256.New()
	n, err := io.Copy(hash, io.LimitReader(contextReader{ctx, file}, info.Size()))
	if err != nil {
		return "", fmt.Errorf("hash file: %w", err)
	}
	if n != info.Size() {
		return "", fmt.Errorf("file size changed: want %d bytes, read %d", info.Size(), n)
	}
	return fmt.Sprintf("%x", hash.Sum(nil)), nil
}

type contextReader struct {
	ctx    context.Context
	reader io.Reader
}

func (r contextReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, fmt.Errorf("read context: %w", err)
	}
	return r.reader.Read(p)
}
