// Copyright 2026 Lusoris
package imageless_test

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/imageless"
)

// The boot command is printed for an operator to paste into a shell. The tests run it through
// a real POSIX shell with qemu replaced by a script on PATH that prints its arguments, so they
// see the argument vector the shell builds, and check that no planted command ran. A shell
// function cannot stand in for qemu: dash refuses a function name with a hyphen.

const shellTimeout = 10 * time.Second

// shellArgs runs command in sh inside an empty directory and returns the qemu arguments and
// whether any file appeared in the directory.
func shellArgs(t *testing.T, command string) ([]string, bool) {
	t.Helper()
	sh, err := exec.LookPath("sh")
	if err != nil {
		t.Skip("no POSIX sh on PATH; the quoting check needs one")
	}
	bin := t.TempDir()
	shim := "#!" + sh + "\nprintf '%s\\0' \"$@\"\n"
	require.NoError(t, os.WriteFile(filepath.Join(bin, "qemu-system-x86_64"), []byte(shim), 0o700))
	dir := t.TempDir()
	ctx, cancel := context.WithTimeout(context.Background(), shellTimeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, sh, "-c", command)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "PATH="+bin+string(os.PathListSeparator)+os.Getenv("PATH"))
	out, err := cmd.Output()
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		t.Logf("stderr: %s", exitErr.Stderr)
	}
	require.NoError(t, err, command)
	entries, err := os.ReadDir(dir)
	require.NoError(t, err)
	return strings.Split(strings.TrimSuffix(string(out), "\x00"), "\x00"), len(entries) > 0
}

func argAfter(t *testing.T, args []string, flag string) string {
	t.Helper()
	for i := 0; i+1 < len(args); i++ {
		if args[i] == flag {
			return args[i+1]
		}
	}
	require.Failf(t, "flag missing", "%s not in %q", flag, args)
	return ""
}

func TestBootCommandSurvivesTheShell(t *testing.T) {
	cases := []imageless.MicroVMBootConfig{
		{FlavorID: "base-generic"},
		{FlavorID: "ai-infer-generic", KernelPath: "/boot/vmlinuz-7.2 rt", InitrdPath: "/boot/initrd.img"},
		{FlavorID: "base-generic", KernelPath: "/k'; touch planted; '", InitrdPath: "/i$(touch planted)"},
		{FlavorID: "base-generic", RootDevice: "/dev/$(touch${IFS}planted)", ExtraCmdline: "a='b' `touch planted` $HOME"},
	}
	for _, cfg := range cases {
		command, err := imageless.GenerateBootCommand(cfg)
		require.NoError(t, err)
		args, ranSomething := shellArgs(t, command)
		assert.False(t, ranSomething, "a planted command ran: %s", command)

		want := cfg
		if want.KernelPath == "" {
			want.KernelPath = "/boot/vmlinuz"
		}
		if want.InitrdPath == "" {
			want.InitrdPath = "/boot/initrd.img"
		}
		if want.RootDevice == "" {
			want.RootDevice = "/dev/vda1"
		}
		assert.Equal(t, want.KernelPath, argAfter(t, args, "-kernel"))
		assert.Equal(t, want.InitrdPath, argAfter(t, args, "-initrd"))
		appendArg := argAfter(t, args, "-append")
		assert.True(t, strings.HasPrefix(appendArg, "root="+want.RootDevice+" ro "), appendArg)
		assert.True(t, strings.HasSuffix(appendArg, want.ExtraCmdline), appendArg)
		assert.Equal(t, "-nographic", args[len(args)-1])
	}
}

func TestBootCommandRefusesPlantedPaths(t *testing.T) {
	cases := []struct {
		name string
		cfg  imageless.MicroVMBootConfig
		want string
	}{
		{"relative-kernel", imageless.MicroVMBootConfig{KernelPath: "vmlinuz"}, "kernel path"},
		{"newline-kernel", imageless.MicroVMBootConfig{KernelPath: "/k\ntouch planted"}, "kernel path"},
		{"relative-initrd", imageless.MicroVMBootConfig{InitrdPath: "./initrd"}, "initrd path"},
		{"tab-initrd", imageless.MicroVMBootConfig{InitrdPath: "/i\tx"}, "initrd path"},
		{"root-space", imageless.MicroVMBootConfig{RootDevice: "/dev/vda1 init=/bin/sh"}, "root device"},
		{"root-quote", imageless.MicroVMBootConfig{RootDevice: `/dev/vda1"`}, "root device"},
		{"root-newline", imageless.MicroVMBootConfig{RootDevice: "/dev/vda1\n"}, "root device"},
		{"cmdline-escape", imageless.MicroVMBootConfig{ExtraCmdline: "quiet\x1b[2J"}, "extra kernel command line"},
		{"unknown-flavor", imageless.MicroVMBootConfig{FlavorID: "no-such-flavor"}, "imageless:"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.cfg.FlavorID == "" {
				tc.cfg.FlavorID = "base-generic"
			}
			command, err := imageless.GenerateBootCommand(tc.cfg)
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.want)
			assert.Empty(t, command)
		})
	}
}
