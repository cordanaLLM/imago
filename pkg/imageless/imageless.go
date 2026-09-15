// Copyright 2026 Lusoris
// Package imageless provides an in-place host provisioning generator
// and direct kernel/initramfs microVM boot configuration engine.
package imageless

import (
	"fmt"
	"strings"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

// ApplyOptions configures the in-place host provisioning script.
type ApplyOptions struct {
	FlavorID    string
	TargetHost  string
	DryRun      bool
	SkipCleanup bool
}

// GenerateApplyScript produces an idempotent, standalone bash script to provision
// a running host or container into the exact target flavor.
func GenerateApplyScript(opts ApplyOptions) (string, error) {
	fl, err := flavors.Get(opts.FlavorID)
	if err != nil {
		return "", fmt.Errorf("imageless: %w", err)
	}

	var sb strings.Builder
	sb.WriteString("#!/usr/bin/env bash\n")
	sb.WriteString("# Lusoris Imageless Provisioning Script\n")
	fmt.Fprintf(&sb, "# Target Flavor: %s (%s)\n", fl.ID, fl.Name)
	sb.WriteString("# Generated automatically by imago\n")
	sb.WriteString("set -euo pipefail\n\n")

	sb.WriteString("echo \"==> Initiating Lusoris imageless flavor application...\"\n")
	fmt.Fprintf(&sb, "echo \"==> Flavor: %s | Hardware Stack: %s\"\n\n", fl.ID, fl.HardwareStack)

	if opts.DryRun {
		sb.WriteString("echo \"==> DRY-RUN: Simulating provisioner execution for:\"\n")
		for _, p := range fl.Provisioners {
			fmt.Fprintf(&sb, "echo \"    [SIMULATED] %s\"\n", p)
		}
		sb.WriteString("echo \"==> DRY-RUN completed successfully.\"\n")
		return sb.String(), nil
	}

	sb.WriteString("# Environment configuration\n")
	fmt.Fprintf(&sb, "export FLAVOR=\"%s\"\n", fl.ID)
	fmt.Fprintf(&sb, "export KERNEL_PROFILE=\"%s\"\n", fl.KernelProfile)
	if fl.PreheatProfile != "" {
		fmt.Fprintf(&sb, "export PREHEAT_PROFILE=\"%s\"\n", fl.PreheatProfile)
	}
	sb.WriteString("\n")

	sb.WriteString("# Execution pipeline\n")
	for _, p := range fl.Provisioners {
		if opts.SkipCleanup && p == "99-cleanup.sh" {
			continue
		}
		fmt.Fprintf(&sb, "echo \"==> Executing provisioner: %s\"\n", p)
		fmt.Fprintf(&sb, "if [ -f \"packer/provisioners/%s\" ]; then\n", p)
		fmt.Fprintf(&sb, "  bash \"packer/provisioners/%s\"\n", p)
		sb.WriteString("else\n")
		fmt.Fprintf(&sb, "  echo \"    Warning: provisioner %s not found in local workspace\"\n", p)
		sb.WriteString("fi\n\n")
	}

	sb.WriteString("echo \"==> Imageless flavor application complete.\"\n")
	return sb.String(), nil
}

// MicroVMBootConfig defines direct kernel boot parameters for QEMU / Cloud-Hypervisor / Firecracker.
type MicroVMBootConfig struct {
	FlavorID     string
	KernelPath   string
	InitrdPath   string
	RootDevice   string
	ExtraCmdline string
}

// GenerateBootCommand formats a direct kernel boot command line.
func GenerateBootCommand(cfg MicroVMBootConfig) (string, error) {
	fl, err := flavors.Get(cfg.FlavorID)
	if err != nil {
		return "", fmt.Errorf("imageless: %w", err)
	}

	if cfg.KernelPath == "" {
		cfg.KernelPath = "/boot/vmlinuz"
	}
	if cfg.InitrdPath == "" {
		cfg.InitrdPath = "/boot/initrd.img"
	}
	if cfg.RootDevice == "" {
		cfg.RootDevice = "/dev/vda1"
	}

	cmdline := []string{
		fmt.Sprintf("root=%s", cfg.RootDevice),
		"ro",
		"console=ttyS0,115200n8",
		"quiet",
		"loglevel=3",
		"systemd.unified_cgroup_hierarchy=1",
	}

	if fl.KernelProfile == "ai-infer" {
		cmdline = append(cmdline, "transparent_hugepage=madvise", "numa=on")
	}

	if cfg.ExtraCmdline != "" {
		cmdline = append(cmdline, cfg.ExtraCmdline)
	}

	cmdlineStr := strings.Join(cmdline, " ")

	return fmt.Sprintf("qemu-system-x86_64 -enable-kvm -m 4096 -smp 4 -kernel %s -initrd %s -append %q -nographic",
		cfg.KernelPath, cfg.InitrdPath, cmdlineStr), nil
}
