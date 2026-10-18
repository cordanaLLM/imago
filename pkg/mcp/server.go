// Copyright 2026 Lusoris
// Package mcp registers the imago tool surface on a golusoris core/mcp server
// so AI agents and IDEs can drive the image forge over the Model Context Protocol.
package mcp

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	coremcp "github.com/golusoris/golusoris/core/mcp"

	"github.com/cordanaLLM/imago/pkg/builder"
	"github.com/cordanaLLM/imago/pkg/cloudinit"
	"github.com/cordanaLLM/imago/pkg/flavors"
	"github.com/cordanaLLM/imago/pkg/imageless"
	"github.com/cordanaLLM/imago/pkg/manifest"
	"github.com/cordanaLLM/imago/pkg/standards"
	"github.com/cordanaLLM/imago/pkg/tracker"
)

// Server re-exports the golusoris core/mcp server type (itself the official SDK server).
type Server = coremcp.Server

// ServerName is the MCP implementation name advertised to clients.
const ServerName = "imago"

// Deps carries the injected collaborator the mutating tools need. It is
// provided through fx in production (NewStager) and faked in tests.
type Deps struct {
	Stager *Stager
}

// RegisterTools registers every imago tool on the given server. The server is
// provided by golusoris core/mcp.Module, which also owns the transport lifecycle
// and stdout-purity guard for stdio mode.
func RegisterTools(s *Server, deps Deps) error {
	if s == nil || deps.Stager == nil {
		return errors.New("mcp: server and stager are required")
	}
	registerFlavorTools(s)
	registerManifestTools(s)
	registerCloudInitTools(s)
	registerStandardsTools(s)
	registerTrackerTools(s)
	registerComplianceTools(s)
	registerExecutionTools(s, deps)
	registerStagingTools(s, deps)
	registerPlanningTools(s)
	return nil
}

// ListFlavorsArgs holds the input arguments for the list_flavors tool.
type ListFlavorsArgs struct {
	Tier string `json:"tier,omitempty" jsonschema:"Optional filter by tier ID (base, containers, kubernetes, k3s, cloudnative, ai-infer, homelab)"`
}

// GetFlavorArgs holds the input arguments for the get_flavor tool.
type GetFlavorArgs struct {
	FlavorID string `json:"flavor_id" jsonschema:"Flavor identifier"`
}

// ValidateManifestArgs holds the input arguments for the validate_manifest tool.
type ValidateManifestArgs struct {
	Path string `json:"path,omitempty" jsonschema:"Path to versions.json"`
}

// GenerateCloudInitArgs holds the input arguments for the generate_cloudinit tool.
type GenerateCloudInitArgs struct {
	Flavor   string `json:"flavor" jsonschema:"Target flavor ID"`
	Hostname string `json:"hostname,omitempty" jsonschema:"Optional host name"`
	User     string `json:"user,omitempty" jsonschema:"Optional default user"`
	Platform string `json:"platform,omitempty" jsonschema:"Optional target hypervisor or platform"`
}

// GetStandardsArgs holds the input arguments for the get_standards tool.
type GetStandardsArgs struct {
	FlavorID string `json:"flavor_id" jsonschema:"Flavor identifier"`
}

// ListEpicsArgs holds the input arguments for the list_epics tool.
type ListEpicsArgs struct{}

// GetMilestonesArgs holds the input arguments for the get_milestones tool.
type GetMilestonesArgs struct{}

// InspectComplianceArgs holds the input arguments for the inspect_compliance tool.
type InspectComplianceArgs struct {
	Path string `json:"path,omitempty" jsonschema:"Optional path to goss.yaml"`
}

// TriggerBuildArgs holds the input arguments for the trigger_build tool.
type TriggerBuildArgs struct {
	Flavor    string `json:"flavor" jsonschema:"Image flavor ID to build"`
	Backend   string `json:"backend" jsonschema:"Build backend (local, pve, qemu, github)"`
	DryRun    bool   `json:"dry_run,omitempty" jsonschema:"Validate build plan without execution"`
	Confirmed bool   `json:"confirmed,omitempty" jsonschema:"Confirm staged action"`
}

// ApplyFlavorArgs holds the input arguments for the apply_flavor tool.
type ApplyFlavorArgs struct {
	FlavorID string `json:"flavor_id" jsonschema:"Flavor identifier to provision"`
	DryRun   bool   `json:"dry_run,omitempty" jsonschema:"Generate script without applying"`
}

// ListStagedActionsArgs holds the input arguments for the list_staged_actions tool.
type ListStagedActionsArgs struct{}

// ConfirmActionArgs holds the input arguments for the confirm_action tool.
type ConfirmActionArgs struct {
	ActionID string `json:"action_id" jsonschema:"ID of the staged action to confirm"`
}

// DiscardStagedActionArgs holds the input arguments for the discard_staged_action tool.
type DiscardStagedActionArgs struct {
	ActionID string `json:"action_id" jsonschema:"ID of the staged action to discard"`
}

func textResult(text string) *coremcp.CallToolResult {
	return &coremcp.CallToolResult{Content: []coremcp.Content{&coremcp.TextContent{Text: text}}}
}

func errorResult(err error) *coremcp.CallToolResult {
	return &coremcp.CallToolResult{IsError: true, Content: []coremcp.Content{&coremcp.TextContent{Text: err.Error()}}}
}

// jsonResult renders v as indented JSON; an encoding failure is a tool error.
func jsonResult(v any) (*coremcp.CallToolResult, error) {
	out, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("mcp: encode result: %w", err)
	}
	return textResult(string(out)), nil
}

func registerFlavorTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "list_flavors",
		Description: "List all 44 available image flavors categorized by workload tier",
	}, listFlavorsHandler)
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "get_flavor",
		Description: "Get detailed hardware specifications, kernel profiles, and provisioners for a specific flavor",
	}, getFlavorHandler)
}

func listFlavorsHandler(_ context.Context, _ *coremcp.CallToolRequest, args ListFlavorsArgs) (*coremcp.CallToolResult, any, error) {
	if args.Tier == "" {
		res, err := jsonResult(flavors.All())
		return res, nil, err
	}
	list := flavors.FilterByTier(args.Tier)
	if len(list) == 0 {
		return errorResult(fmt.Errorf("mcp: unknown tier %q; known tiers: %s", args.Tier, tierIDs())), nil, nil
	}
	res, err := jsonResult(list)
	return res, nil, err
}

func tierIDs() string {
	tiers := flavors.Tiers()
	ids := make([]string, 0, len(tiers))
	for _, t := range tiers {
		ids = append(ids, t.ID)
	}
	return strings.Join(ids, ", ")
}

func getFlavorHandler(_ context.Context, _ *coremcp.CallToolRequest, args GetFlavorArgs) (*coremcp.CallToolResult, any, error) {
	fl, err := flavors.Get(args.FlavorID)
	if err != nil {
		return errorResult(err), nil, nil
	}
	res, err := jsonResult(fl)
	return res, nil, err
}

func registerManifestTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "validate_manifest",
		Description: "Validate versions.json Single Source of Truth against semantic schema",
	}, validateManifestHandler)
}

func validateManifestHandler(_ context.Context, _ *coremcp.CallToolRequest, args ValidateManifestArgs) (*coremcp.CallToolResult, any, error) {
	p, err := repoRelativePath(args.Path, "versions.json")
	if err != nil {
		return errorResult(err), nil, nil
	}
	m, err := manifest.Load(p)
	if err != nil {
		return errorResult(err), nil, nil
	}
	msg := fmt.Sprintf("Validation SUCCESS: Distribution %s (%s %s), K8s %s, Containerd %s, Docker CE %s",
		m.Distro.Name, m.Distro.Release, m.Distro.Version, m.Kubernetes.Version, m.Runtimes.Containerd, m.Runtimes.DockerCE)
	return textResult(msg), nil, nil
}

func registerCloudInitTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "generate_cloudinit",
		Description: "Generate hardened cloud-init user-data for Proxmox, Unraid, VMware, macOS, or Windows",
	}, generateCloudInitHandler)
}

func generateCloudInitHandler(_ context.Context, _ *coremcp.CallToolRequest, args GenerateCloudInitArgs) (*coremcp.CallToolResult, any, error) {
	if _, err := flavors.Get(args.Flavor); err != nil {
		return errorResult(err), nil, nil
	}
	cfg := cloudinit.DefaultConfig(args.Flavor)
	if args.Hostname != "" {
		cfg.Hostname = args.Hostname
	}
	if args.User != "" {
		cfg.User = args.User
	}
	if args.Platform != "" {
		cfg.Platform = args.Platform
	}
	ud, err := cloudinit.GenerateUserData(cfg)
	if err != nil {
		return errorResult(err), nil, nil
	}
	return textResult(ud), nil, nil
}

func registerStandardsTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "get_standards",
		Description: "Get machine-verifiable CIS and BSI hardening requirements for a flavor",
	}, getStandardsHandler)
}

func getStandardsHandler(_ context.Context, _ *coremcp.CallToolRequest, args GetStandardsArgs) (*coremcp.CallToolResult, any, error) {
	std, err := standards.Get(args.FlavorID)
	if err != nil {
		return errorResult(err), nil, nil
	}
	res, err := jsonResult(std)
	return res, nil, err
}

func registerTrackerTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "list_epics",
		Description: "List tracked architectural and operational recurring epics",
	}, listEpicsHandler)
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "get_milestones",
		Description: "List release milestones with state and due date",
	}, getMilestonesHandler)
}

func listEpicsHandler(_ context.Context, _ *coremcp.CallToolRequest, _ ListEpicsArgs) (*coremcp.CallToolResult, any, error) {
	epics, err := tracker.LoadEpics(filepath.Join(".github", "epics.json"))
	if err != nil {
		return errorResult(err), nil, nil
	}
	res, err := jsonResult(epics)
	return res, nil, err
}

func getMilestonesHandler(_ context.Context, _ *coremcp.CallToolRequest, _ GetMilestonesArgs) (*coremcp.CallToolResult, any, error) {
	ms, err := tracker.LoadMilestones(filepath.Join(".github", "milestones.json"))
	if err != nil {
		return errorResult(err), nil, nil
	}
	res, err := jsonResult(ms)
	return res, nil, err
}

func registerComplianceTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "inspect_compliance",
		Description: "Inspect the declarative Goss compliance-as-code specification (CIS Level 2, DISA STIG, NIST SP 800-53)",
	}, inspectComplianceHandler)
}

func inspectComplianceHandler(_ context.Context, _ *coremcp.CallToolRequest, args InspectComplianceArgs) (*coremcp.CallToolResult, any, error) {
	p, err := repoRelativePath(args.Path, filepath.Join("tests", "compliance", "goss.yaml"))
	if err != nil {
		return errorResult(err), nil, nil
	}
	data, err := os.ReadFile(filepath.Clean(p))
	if err != nil {
		return errorResult(err), nil, nil
	}
	return textResult(string(data)), nil, nil
}

func registerExecutionTools(s *coremcp.Server, deps Deps) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "trigger_build",
		Description: "Validate an image build plan with dry_run=true. MCP has no execution backends: a confirmed request returns an error. For local execution use the CLI: imago build --backend local. Requests stage a confirmation card unless confirmed=true or dry_run=true; confirmation does not imply execution.",
	}, triggerBuildHandler(deps))
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "apply_flavor",
		Description: "Generate an in-place live host or remote SSH flavor provisioning script (imageless execution)",
	}, applyFlavorHandler)
}

// triggerBuildHandler applies the two-phase staging guardrail: a build that is
// neither a dry run nor explicitly confirmed is staged for confirmation.
func triggerBuildHandler(deps Deps) func(context.Context, *coremcp.CallToolRequest, TriggerBuildArgs) (*coremcp.CallToolResult, any, error) {
	return func(ctx context.Context, _ *coremcp.CallToolRequest, args TriggerBuildArgs) (*coremcp.CallToolResult, any, error) {
		if err := builder.Validate(builder.Backend(args.Backend), args.Flavor); err != nil {
			return errorResult(err), nil, nil
		}
		if !args.DryRun && !args.Confirmed {
			preview := fmt.Sprintf("Trigger image build for flavor %q via backend %q", args.Flavor, args.Backend)
			staged := deps.Stager.Stage("trigger_build", args.Flavor, map[string]any{
				"flavor":  args.Flavor,
				"backend": args.Backend,
				"dry_run": args.DryRun,
			}, preview)
			return textResult(stagedMessage(staged, args.Flavor, args.Backend)), nil, nil
		}
		res, err := dispatchBuild(ctx, args.Backend, args.Flavor, args.DryRun, "")
		return res, nil, err
	}
}

func stagedMessage(staged *StagedAction, flavor, backend string) string {
	return fmt.Sprintf("⚠️ ACTION STAGED (Two-Phase Verification Guardrail)\nAction ID: %s\nTool: trigger_build\nTarget Flavor: %s\nBackend: %s\n\nTo attempt this build, invoke `confirm_action` with `{\"action_id\": %q}` or re-run `trigger_build` with `\"confirmed\": true`.",
		staged.ID, flavor, backend, staged.ID)
}

// dispatchBuild runs the build dispatcher and renders the result, prefixed by
// an optional confirmation banner. A refused dispatch is an error result.
func dispatchBuild(ctx context.Context, backend, flavor string, dryRun bool, prefix string) (*coremcp.CallToolResult, error) {
	res, err := builder.Dispatch(ctx, builder.Request{
		Backend: builder.Backend(backend),
		Flavor:  flavor,
		DryRun:  dryRun,
	})
	if err != nil {
		if backend == string(builder.BackendLocal) && errors.Is(err, builder.ErrBackendUnavailable) {
			err = fmt.Errorf("%w; local executor available from the CLI: imago build --backend local", err)
		}
		return errorResult(err), nil
	}
	out, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("mcp: encode result: %w", err)
	}
	return textResult(prefix + string(out)), nil
}

func applyFlavorHandler(_ context.Context, _ *coremcp.CallToolRequest, args ApplyFlavorArgs) (*coremcp.CallToolResult, any, error) {
	script, err := imageless.GenerateApplyScript(imageless.ApplyOptions{
		FlavorID: args.FlavorID,
		DryRun:   args.DryRun,
	})
	if err != nil {
		return errorResult(err), nil, nil
	}
	return textResult(script), nil, nil
}

func registerStagingTools(s *coremcp.Server, deps Deps) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "list_staged_actions",
		Description: "List all pending two-phase staged actions waiting for confirmation",
	}, listStagedActionsHandler(deps))
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "confirm_action",
		Description: "Confirm a pending staged action by its action_id and attempt it; a build backend without an executor returns an error",
	}, confirmActionHandler(deps))
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "discard_staged_action",
		Description: "Discard or cancel a pending staged action",
	}, discardActionHandler(deps))
}

func listStagedActionsHandler(deps Deps) func(context.Context, *coremcp.CallToolRequest, ListStagedActionsArgs) (*coremcp.CallToolResult, any, error) {
	return func(_ context.Context, _ *coremcp.CallToolRequest, _ ListStagedActionsArgs) (*coremcp.CallToolResult, any, error) {
		res, err := jsonResult(deps.Stager.List())
		return res, nil, err
	}
}

func confirmActionHandler(deps Deps) func(context.Context, *coremcp.CallToolRequest, ConfirmActionArgs) (*coremcp.CallToolResult, any, error) {
	return func(ctx context.Context, _ *coremcp.CallToolRequest, args ConfirmActionArgs) (*coremcp.CallToolResult, any, error) {
		act, err := deps.Stager.Confirm(args.ActionID)
		if err != nil {
			return errorResult(err), nil, nil
		}
		if act.Tool != "trigger_build" {
			return textResult(fmt.Sprintf("✅ Action %s confirmed (tool: %s)", act.ID, act.Tool)), nil, nil
		}
		flavor, _ := act.Payload["flavor"].(string)
		backend, _ := act.Payload["backend"].(string)
		dryRun, _ := act.Payload["dry_run"].(bool)
		prefix := fmt.Sprintf("Action %s confirmed; dispatch result:\n", act.ID)
		res, err := dispatchBuild(ctx, backend, flavor, dryRun, prefix)
		return res, nil, err
	}
}

func discardActionHandler(deps Deps) func(context.Context, *coremcp.CallToolRequest, DiscardStagedActionArgs) (*coremcp.CallToolResult, any, error) {
	return func(_ context.Context, _ *coremcp.CallToolRequest, args DiscardStagedActionArgs) (*coremcp.CallToolResult, any, error) {
		if err := deps.Stager.Discard(args.ActionID); err != nil {
			return errorResult(err), nil, nil
		}
		return textResult(fmt.Sprintf("Action %q discarded successfully", args.ActionID)), nil, nil
	}
}
