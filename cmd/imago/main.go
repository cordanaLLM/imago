// Copyright 2026 Lusoris
// imago is the unified CLI and Model Context Protocol (MCP) server for the
// cordanaLLM/imago image forge. It is composed from golusoris core: clikit
// builds the command tree, core/log provides the logger, core/clock supplies
// time, and core/mcp owns the MCP transport lifecycle.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"
	"go.uber.org/fx"

	"github.com/golusoris/golusoris/core/clikit"
	"github.com/golusoris/golusoris/core/clock"
	"github.com/golusoris/golusoris/core/config"
	"github.com/golusoris/golusoris/core/log"
	coremcp "github.com/golusoris/golusoris/core/mcp"

	"github.com/cordanaLLM/imago/pkg/builder"
	"github.com/cordanaLLM/imago/pkg/cloudinit"
	"github.com/cordanaLLM/imago/pkg/flavors"
	"github.com/cordanaLLM/imago/pkg/imageless"
	"github.com/cordanaLLM/imago/pkg/manifest"
	"github.com/cordanaLLM/imago/pkg/mcp"
	"github.com/cordanaLLM/imago/pkg/planning"
	"github.com/cordanaLLM/imago/pkg/standards"
	"github.com/cordanaLLM/imago/pkg/tracker"
)

// version is advertised to MCP clients; release-please owns the VERSION file.
const version = "0.1.0"

// envPrefix scopes runtime configuration (IMAGO_LOG_LEVEL, IMAGO_MCP_TRANSPORT, ...).
const envPrefix = "IMAGO_"

// newRuntimeConfig builds the koanf-backed configuration golusoris modules read.
// File watching is off: the CLI is short-lived and the MCP server is restarted by its client.
func newRuntimeConfig() (*config.Config, error) {
	cfg, err := config.New(config.Options{EnvPrefix: envPrefix, Watch: false})
	if err != nil {
		return nil, fmt.Errorf("imago: config: %w", err)
	}
	return cfg, nil
}

// newRootCmd assembles the command tree on a golusoris clikit root.
func newRootCmd() *cobra.Command {
	root := clikit.New("imago", "Imago — Unified CLI & AI MCP Server for cloud images")
	root.AddCommand(
		newFlavorsCmd(),
		newManifestCmd(),
		newCloudInitCmd(),
		newBuildCmd(),
		newApplyCmd(),
		newBootCmd(),
		newStandardsCmd(),
		newEpicsCmd(),
		newMilestonesCmd(),
		newPlanCmd(),
		newLintCmd(),
		newAuditCmd(),
		newMCPCmd(),
	)
	return root.Cobra()
}

func main() {
	slog.SetDefault(log.New(log.Options{Level: slog.LevelInfo}))

	if err := newRootCmd().Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func newFlavorsCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "flavors",
		Short: "Inspect and query the 44-flavor catalog",
	}

	var tier string
	var jsonOutput bool

	listCmd := &cobra.Command{
		Use:   "list",
		Short: "List all production flavors",
		RunE: func(cmd *cobra.Command, args []string) error {
			var list []flavors.Flavor
			if tier != "" {
				list = flavors.FilterByTier(tier)
			} else {
				list = flavors.All()
			}
			if jsonOutput {
				enc := json.NewEncoder(cmd.OutOrStdout())
				enc.SetIndent("", "  ")
				return enc.Encode(list)
			}
			fmt.Fprintf(cmd.OutOrStdout(), "%-28s %-12s %-24s %s\n", "FLAVOR ID", "TIER", "HARDWARE", "DESCRIPTION")
			fmt.Fprintln(cmd.OutOrStdout(), string(make([]byte, 100)))
			for _, f := range list {
				fmt.Fprintf(cmd.OutOrStdout(), "%-28s %-12s %-24s %s\n", f.ID, f.TierID, f.HardwareStack, f.Description)
			}
			return nil
		},
	}
	listCmd.Flags().StringVarP(&tier, "tier", "t", "", "Filter by workload tier")
	listCmd.Flags().BoolVar(&jsonOutput, "json", false, "Output JSON")

	getCmd := &cobra.Command{
		Use:   "get [flavor-id]",
		Short: "Get full details of a specific flavor",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			fl, err := flavors.Get(args[0])
			if err != nil {
				return err
			}
			enc := json.NewEncoder(cmd.OutOrStdout())
			enc.SetIndent("", "  ")
			return enc.Encode(fl)
		},
	}

	cmd.AddCommand(listCmd, getCmd)
	return cmd
}

func newManifestCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "manifest",
		Short: "Inspect and validate versions.json",
	}

	var path string
	valCmd := &cobra.Command{
		Use:   "validate",
		Short: "Validate versions.json Single Source of Truth",
		RunE: func(cmd *cobra.Command, args []string) error {
			p := path
			if p == "" {
				p = "versions.json"
			}
			m, err := manifest.Load(p)
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "✓ Manifest %s is valid.\n", p)
			fmt.Fprintf(cmd.OutOrStdout(), "  Distro: %s (%s %s)\n", m.Distro.Name, m.Distro.Release, m.Distro.Version)
			fmt.Fprintf(cmd.OutOrStdout(), "  Kubernetes: %s (K3s: %s)\n", m.Kubernetes.Version, m.K3s.Version)
			fmt.Fprintf(cmd.OutOrStdout(), "  Runtimes: Containerd %s, Docker CE %s\n", m.Runtimes.Containerd, m.Runtimes.DockerCE)
			fmt.Fprintf(cmd.OutOrStdout(), "  Time: Anycast %s (Stratum-1 endpoints: %d)\n", m.Time.AnycastNTS, len(m.Time.Stratum1NTS))
			return nil
		},
	}
	valCmd.Flags().StringVarP(&path, "file", "f", "versions.json", "Path to versions.json")
	valCmd.Flags().StringVar(&path, "path", "versions.json", "Path to versions.json (alias)")

	cmd.AddCommand(valCmd)
	return cmd
}

func newCloudInitCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "cloud-init",
		Short: "Generate hardened cloud-init configuration",
	}

	var flavor, hostname, user, platform string

	genCmd := &cobra.Command{
		Use:   "generate",
		Short: "Generate user-data YAML",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg := cloudinit.DefaultConfig(flavor)
			if hostname != "" {
				cfg.Hostname = hostname
			}
			if user != "" {
				cfg.User = user
			}
			if platform != "" {
				cfg.Platform = platform
			}
			ud, err := cloudinit.GenerateUserData(cfg)
			if err != nil {
				return err
			}
			fmt.Fprint(cmd.OutOrStdout(), ud)
			return nil
		},
	}
	genCmd.Flags().StringVarP(&flavor, "flavor", "f", "base-generic", "Target flavor")
	genCmd.Flags().StringVar(&hostname, "hostname", "lusoris-node", "Virtual machine hostname")
	genCmd.Flags().StringVar(&user, "user", "ubuntu", "Default non-root operator user")
	genCmd.Flags().StringVarP(&platform, "platform", "p", "proxmox", "Platform target (proxmox, unraid, macos, windows)")

	metaCmd := &cobra.Command{
		Use:   "metadata",
		Short: "Generate meta-data YAML",
		RunE: func(cmd *cobra.Command, args []string) error {
			md, err := cloudinit.GenerateMetaData(cloudinit.Config{Hostname: hostname})
			if err != nil {
				return err
			}
			fmt.Fprint(cmd.OutOrStdout(), md)
			return nil
		},
	}
	metaCmd.Flags().StringVar(&hostname, "hostname", "lusoris-node", "Virtual machine hostname")

	cmd.AddCommand(genCmd, metaCmd)
	return cmd
}

func newBuildCmd() *cobra.Command {
	var flavor, backend string
	var dryRun bool
	var clk clock.Clock
	var cmd *cobra.Command

	// One-shot fx run: clock.Module provides the golusoris wall clock, the app
	// starts, dispatch runs, and the app stops without blocking on a signal.
	cmd = clikit.Command("build", "Dispatch an image build locally or to self-hosted CI backends",
		clikit.WithFxRun(func(ctx context.Context) error {
			res, err := builder.Dispatch(ctx, builder.Request{
				Backend: builder.Backend(backend),
				Flavor:  flavor,
				DryRun:  dryRun,
				Clock:   clk,
			})
			if err != nil {
				return err
			}
			return printBuildResult(cmd.OutOrStdout(), res)
		}, clock.Module, fx.Populate(&clk)),
	)
	cmd.Flags().StringVarP(&flavor, "flavor", "f", "base-generic", "Flavor to build")
	cmd.Flags().StringVarP(&backend, "backend", "b", "local", "Build backend (local, gitea, proxmox, gitlab, woodpecker, harbor, minio, jenkins, github)")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Simulate build dispatch without execution")
	return cmd
}

func printBuildResult(w io.Writer, res builder.Result) error {
	if _, err := fmt.Fprintf(w, "==> Build Dispatch: %s\n", res.Message); err != nil {
		return err
	}
	if res.PipelineID != "" {
		fmt.Fprintf(w, "    Pipeline ID: %s\n", res.PipelineID)
	}
	if res.ArtifactURL != "" {
		fmt.Fprintf(w, "    Artifact: %s\n", res.ArtifactURL)
	}
	return nil
}

func newApplyCmd() *cobra.Command {
	var flavor string
	var dryRun, skipCleanup bool

	cmd := &cobra.Command{
		Use:   "apply",
		Short: "In-place live host / SSH provisioning (imageless execution)",
		RunE: func(cmd *cobra.Command, args []string) error {
			script, err := imageless.GenerateApplyScript(imageless.ApplyOptions{
				FlavorID:    flavor,
				DryRun:      dryRun,
				SkipCleanup: skipCleanup,
			})
			if err != nil {
				return err
			}
			fmt.Fprint(cmd.OutOrStdout(), script)
			return nil
		},
	}
	cmd.Flags().StringVarP(&flavor, "flavor", "f", "base-generic", "Target flavor to apply")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Generate simulated execution script")
	cmd.Flags().BoolVar(&skipCleanup, "skip-cleanup", false, "Skip 99-cleanup.sh provisioner step")
	return cmd
}

func newBootCmd() *cobra.Command {
	var flavor, kernel, initrd, rootDev string

	cmd := &cobra.Command{
		Use:   "boot",
		Short: "Generate microVM direct kernel boot command",
		RunE: func(cmd *cobra.Command, args []string) error {
			bootCmd, err := imageless.GenerateBootCommand(imageless.MicroVMBootConfig{
				FlavorID:   flavor,
				KernelPath: kernel,
				InitrdPath: initrd,
				RootDevice: rootDev,
			})
			if err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), bootCmd)
			return nil
		},
	}
	cmd.Flags().StringVarP(&flavor, "flavor", "f", "base-generic", "Target flavor")
	cmd.Flags().StringVarP(&kernel, "kernel", "k", "/boot/vmlinuz", "Kernel binary path")
	cmd.Flags().StringVarP(&initrd, "initrd", "i", "/boot/initrd.img", "Initramfs path")
	cmd.Flags().StringVarP(&rootDev, "root", "r", "/dev/vda1", "Root block device")
	return cmd
}

func newStandardsCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "standards",
		Short: "Inspect machine-verifiable CIS and BSI hardening standards",
	}

	listCmd := &cobra.Command{
		Use:   "list",
		Short: "List standards across all 44 flavors",
		RunE: func(cmd *cobra.Command, args []string) error {
			stds := standards.All()
			fmt.Fprintf(cmd.OutOrStdout(), "%-28s %-12s %-40s %s\n", "FLAVOR ID", "TIER", "SECURITY BASELINE", "CDI")
			fmt.Fprintln(cmd.OutOrStdout(), string(make([]byte, 100)))
			for _, s := range stds {
				cdiStr := "no"
				if s.CDISpecRequired {
					cdiStr = "yes"
				}
				fmt.Fprintf(cmd.OutOrStdout(), "%-28s %-12s %-40s %s\n", s.FlavorID, s.Tier, s.SecurityBaseline, cdiStr)
			}
			return nil
		},
	}

	getCmd := &cobra.Command{
		Use:   "get [flavor-id]",
		Short: "Get exact hardening requirements for a flavor",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			std, err := standards.Get(args[0])
			if err != nil {
				return err
			}
			enc := json.NewEncoder(cmd.OutOrStdout())
			enc.SetIndent("", "  ")
			return enc.Encode(std)
		},
	}

	cmd.AddCommand(listCmd, getCmd)
	return cmd
}

func newEpicsCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "epics",
		Short: "Inspect tracked architectural and operational recurring epics",
	}

	var file string
	listCmd := &cobra.Command{
		Use:   "list",
		Short: "List all active epics",
		RunE: func(cmd *cobra.Command, args []string) error {
			p := file
			if p == "" {
				p = filepath.Join(".github", "epics.json")
			}
			epics, err := tracker.LoadEpics(p)
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "%-10s %-12s %-50s %s\n", "ID", "CADENCE", "TITLE", "STATUS")
			fmt.Fprintln(cmd.OutOrStdout(), string(make([]byte, 85)))
			for _, e := range epics {
				fmt.Fprintf(cmd.OutOrStdout(), "%-10s %-12s %-50s %s\n", e.ID, e.Cadence, e.Title, e.Status)
			}
			return nil
		},
	}
	listCmd.Flags().StringVarP(&file, "file", "f", "", "Path to epics.json")
	listCmd.Flags().StringVar(&file, "path", "", "Path to epics.json (alias)")

	cmd.AddCommand(listCmd)
	return cmd
}

func newMilestonesCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "milestones",
		Short: "Inspect release milestones",
	}

	var file string
	listCmd := &cobra.Command{
		Use:   "list",
		Short: "List all open milestones",
		RunE: func(cmd *cobra.Command, args []string) error {
			p := file
			if p == "" {
				p = filepath.Join(".github", "milestones.json")
			}
			ms, err := tracker.LoadMilestones(p)
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "%-14s %-8s %-22s %s\n", "TITLE", "STATE", "DUE ON", "DESCRIPTION")
			fmt.Fprintln(cmd.OutOrStdout(), string(make([]byte, 85)))
			for _, m := range ms {
				fmt.Fprintf(cmd.OutOrStdout(), "%-14s %-8s %-22s %s\n", m.Title, m.State, m.DueOn, m.Description)
			}
			return nil
		},
	}
	listCmd.Flags().StringVarP(&file, "file", "f", "", "Path to milestones.json")
	listCmd.Flags().StringVar(&file, "path", "", "Path to milestones.json (alias)")

	cmd.AddCommand(listCmd)
	return cmd
}

func newLintCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "lint",
		Short: "Run specialized static analyzers and linters",
		RunE: func(cmd *cobra.Command, args []string) error {
			fmt.Println("==> Running imago static analyzers...")
			// 1. Manifest
			if _, err := manifest.Load("versions.json"); err != nil {
				return fmt.Errorf("manifest lint failed: %w", err)
			}
			fmt.Println("  ✓ versions.json schema valid")

			// 2. Epics & Milestones
			if _, err := tracker.LoadEpics(".github/epics.json"); err != nil {
				return fmt.Errorf("epics lint failed: %w", err)
			}
			fmt.Println("  ✓ .github/epics.json valid")
			if _, err := tracker.LoadMilestones(".github/milestones.json"); err != nil {
				return fmt.Errorf("milestones lint failed: %w", err)
			}
			fmt.Println("  ✓ .github/milestones.json valid")

			fmt.Println("==> All internal linter checks passed.")
			return nil
		},
	}
}

func newAuditCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "audit",
		Short: "Execute repository health audit script",
		RunE: func(cmd *cobra.Command, args []string) error {
			scriptPath := filepath.Join("scripts", "audit-repository-health.sh")
			if _, err := os.Stat(scriptPath); err != nil {
				return fmt.Errorf("audit script %s not found: %w", scriptPath, err)
			}
			// Literal script path: the audit runner is a fixed repository asset, not user input.
			c := exec.Command("bash", "scripts/audit-repository-health.sh")
			c.Stdout = os.Stdout
			c.Stderr = os.Stderr
			return c.Run()
		},
	}
}

func newMCPCmd() *cobra.Command {
	var transport, addr string

	// Long-running fx app: core/mcp.Module owns the transport lifecycle (stdio
	// with stdout-purity guard, or streamable-HTTP) and ends the app when the
	// client disconnects. Tools are registered through fx.Invoke before start.
	cmd := clikit.Command("mcp", "Start the Model Context Protocol (MCP) server (stdio or streamable-HTTP)",
		clikit.WithFx(
			fx.Provide(newRuntimeConfig),
			log.Module,
			clock.Module,
			coremcp.Module,
			fx.Provide(mcp.NewStager),
			fx.Decorate(func(o coremcp.Options) coremcp.Options {
				return withServerIdentity(o, transport, addr)
			}),
			fx.Invoke(func(s *coremcp.Server, st *mcp.Stager, c clock.Clock) error {
				return mcp.RegisterTools(s, mcp.Deps{Stager: st, Clock: c})
			}),
		),
	)
	cmd.Flags().StringVar(&transport, "transport", string(coremcp.TransportStdio), "MCP transport (stdio, http)")
	cmd.Flags().StringVar(&addr, "addr", ":8899", "Listen address for the http transport")
	return cmd
}

// withServerIdentity pins the advertised implementation and lets the CLI flags
// override the IMAGO_MCP_* configuration keys core/mcp reads.
func withServerIdentity(o coremcp.Options, transport, addr string) coremcp.Options {
	o.Name = mcp.ServerName
	o.Version = version
	o.Transport = coremcp.Transport(transport)
	if addr != "" {
		o.HTTP.Addr = addr
	}
	return o
}

func newPlanCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "plan",
		Short: "Validate and route the tracked planning graph (planning/plan.json)",
	}

	var planPath, routingPath string
	var jsonOutput, readyOnly bool

	validateCmd := &cobra.Command{
		Use:   "validate",
		Short: "Validate the planning graph and its routing overlay",
		RunE: func(cmd *cobra.Command, args []string) error {
			plan, err := planning.Load(planPath)
			if err != nil {
				return err
			}
			if _, err := planning.LoadOverlay(routingPath, plan); err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "✓ Plan %s (%d steps, %d milestones) and routing overlay are valid.\n", plan.ID, len(plan.Steps), len(plan.Milestones))
			return nil
		},
	}

	routeCmd := &cobra.Command{
		Use:   "route",
		Short: "Rank steps: ready local work first, by (1 + transitive unblocks) / cost",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runPlanRoute(cmd.OutOrStdout(), planPath, routingPath, jsonOutput, readyOnly)
		},
	}
	routeCmd.Flags().BoolVar(&jsonOutput, "json", false, "Output JSON")
	routeCmd.Flags().BoolVar(&readyOnly, "ready", false, "Show only the ready set")

	cmd.PersistentFlags().StringVar(&planPath, "plan", mcp.DefaultPlanPath, "Path to plan.json")
	cmd.PersistentFlags().StringVar(&routingPath, "routing", mcp.DefaultRoutingPath, "Path to routing.json")
	cmd.AddCommand(validateCmd, routeCmd)
	return cmd
}

func runPlanRoute(w io.Writer, planPath, routingPath string, jsonOutput, readyOnly bool) error {
	plan, err := planning.Load(planPath)
	if err != nil {
		return err
	}
	overlay, err := planning.LoadOverlay(routingPath, plan)
	if err != nil {
		return err
	}
	routed, err := planning.Route(plan, overlay)
	if err != nil {
		return err
	}
	if readyOnly {
		routed = planning.Ready(routed)
	}
	if jsonOutput {
		enc := json.NewEncoder(w)
		enc.SetIndent("", "  ")
		return enc.Encode(routed)
	}
	fmt.Fprintf(w, "%-4s %-8s %-7s %-6s %-9s %-36s %s\n", "RANK", "STATE", "COST", "SCORE", "UNBLOCKS", "STEP", "BLOCKED BY")
	for _, r := range routed {
		fmt.Fprintf(w, "%-4d %-8s %-7s %-6.2f %-9d %-36s %s\n", r.Rank, r.State, r.Cost, r.Score, r.TransitiveUnblocks, r.ID, strings.Join(r.BlockedBy, ","))
	}
	return nil
}
