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

	"github.com/golusoris/golusoris/core/clock"
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

// Deps carries the injected collaborators the mutating tools need. Both are
// provided through fx in production (clock.Module, NewStager) and faked in tests.
type Deps struct {
	Stager *Stager
	Clock  clock.Clock
}

// RegisterTools registers every imago tool on the given server. The server is
// provided by golusoris core/mcp.Module, which also owns the transport lifecycle
// and stdout-purity guard for stdio mode.
func RegisterTools(s *Server, deps Deps) error {
	if s == nil || deps.Stager == nil || deps.Clock == nil {
		return errors.New("mcp: server, stager and clock are required")
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

// tool builds a tool descriptor from its name, description and JSON schema.
func tool(name, description, schema string) *coremcp.Tool {
	return &coremcp.Tool{Name: name, Description: description, InputSchema: json.RawMessage(schema)}
}

// decodeArgs decodes the call arguments into `into`; absent arguments decode as
// the zero value, malformed arguments are reported instead of ignored.
func decodeArgs(req *coremcp.CallToolRequest, into any) error {
	if len(req.Params.Arguments) == 0 {
		return nil
	}
	if err := json.Unmarshal(req.Params.Arguments, into); err != nil {
		return fmt.Errorf("mcp: decode arguments: %w", err)
	}
	return nil
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
	s.AddTool(tool("list_flavors",
		"List all 44 available image flavors categorized by workload tier",
		`{"type":"object","properties":{"tier":{"type":"string","description":"Optional filter by tier ID (base, containers, kubernetes, k3s, cloudnative, ai-infer, homelab)"}}}`,
	), listFlavorsHandler)
	s.AddTool(tool("get_flavor",
		"Get detailed hardware specifications, kernel profiles, and provisioners for a specific flavor",
		`{"type":"object","required":["flavor_id"],"properties":{"flavor_id":{"type":"string"}}}`,
	), getFlavorHandler)
}

func listFlavorsHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		Tier string `json:"tier"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	if args.Tier != "" {
		return jsonResult(flavors.FilterByTier(args.Tier))
	}
	return jsonResult(flavors.All())
}

func getFlavorHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		FlavorID string `json:"flavor_id"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	fl, err := flavors.Get(args.FlavorID)
	if err != nil {
		return errorResult(err), nil
	}
	return jsonResult(fl)
}

func registerManifestTools(s *coremcp.Server) {
	s.AddTool(tool("validate_manifest",
		"Validate versions.json Single Source of Truth against semantic schema",
		`{"type":"object","properties":{"path":{"type":"string","description":"Path to versions.json"}}}`,
	), validateManifestHandler)
}

func validateManifestHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		Path string `json:"path"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	p := args.Path
	if p == "" {
		p = "versions.json"
	}
	m, err := manifest.Load(p)
	if err != nil {
		return errorResult(err), nil
	}
	msg := fmt.Sprintf("Validation SUCCESS: Distribution %s (%s %s), K8s %s, Containerd %s, Docker CE %s",
		m.Distro.Name, m.Distro.Release, m.Distro.Version, m.Kubernetes.Version, m.Runtimes.Containerd, m.Runtimes.DockerCE)
	return textResult(msg), nil
}

func registerCloudInitTools(s *coremcp.Server) {
	s.AddTool(tool("generate_cloudinit",
		"Generate hardened cloud-init user-data for Proxmox, Unraid, VMware, macOS, or Windows",
		`{"type":"object","required":["flavor"],"properties":{"flavor":{"type":"string"},"hostname":{"type":"string"},"user":{"type":"string"},"platform":{"type":"string"}}}`,
	), generateCloudInitHandler)
}

func generateCloudInitHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		Flavor   string `json:"flavor"`
		Hostname string `json:"hostname"`
		User     string `json:"user"`
		Platform string `json:"platform"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	if _, err := flavors.Get(args.Flavor); err != nil {
		return errorResult(err), nil
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
		return errorResult(err), nil
	}
	return textResult(ud), nil
}

func registerStandardsTools(s *coremcp.Server) {
	s.AddTool(tool("get_standards",
		"Get machine-verifiable CIS and BSI hardening requirements for a flavor",
		`{"type":"object","required":["flavor_id"],"properties":{"flavor_id":{"type":"string"}}}`,
	), getStandardsHandler)
}

func getStandardsHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		FlavorID string `json:"flavor_id"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	std, err := standards.Get(args.FlavorID)
	if err != nil {
		return errorResult(err), nil
	}
	return jsonResult(std)
}

func registerTrackerTools(s *coremcp.Server) {
	s.AddTool(tool("list_epics",
		"List tracked architectural and operational recurring epics",
		`{"type":"object"}`,
	), func(_ context.Context, _ *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
		epics, err := tracker.LoadEpics(filepath.Join(".github", "epics.json"))
		if err != nil {
			return errorResult(err), nil
		}
		return jsonResult(epics)
	})
	s.AddTool(tool("get_milestones",
		"List open release milestones and due dates",
		`{"type":"object"}`,
	), func(_ context.Context, _ *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
		ms, err := tracker.LoadMilestones(filepath.Join(".github", "milestones.json"))
		if err != nil {
			return errorResult(err), nil
		}
		return jsonResult(ms)
	})
}

func registerComplianceTools(s *coremcp.Server) {
	s.AddTool(tool("inspect_compliance",
		"Inspect the declarative Goss compliance-as-code specification (CIS Level 2, DISA STIG, NIST SP 800-53)",
		`{"type":"object","properties":{"path":{"type":"string","description":"Optional path to goss.yaml"}}}`,
	), inspectComplianceHandler)
}

func inspectComplianceHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		Path string `json:"path"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	p := args.Path
	if p == "" {
		p = filepath.Join("tests", "compliance", "goss.yaml")
	}
	data, err := os.ReadFile(p)
	if err != nil {
		return errorResult(err), nil
	}
	return textResult(string(data)), nil
}

func registerExecutionTools(s *coremcp.Server, deps Deps) {
	s.AddTool(tool("trigger_build",
		"Dispatch an image build to local Packer or remote CI backends (Gitea, Proxmox, GitLab, GitHub). Mutating operations stage a confirmation card unless confirmed=true or dry_run=true.",
		`{"type":"object","required":["flavor","backend"],"properties":{"flavor":{"type":"string"},"backend":{"type":"string"},"dry_run":{"type":"boolean"},"confirmed":{"type":"boolean"}}}`,
	), triggerBuildHandler(deps))
	s.AddTool(tool("apply_flavor",
		"Generate an in-place live host or remote SSH flavor provisioning script (imageless execution)",
		`{"type":"object","required":["flavor_id"],"properties":{"flavor_id":{"type":"string"},"dry_run":{"type":"boolean"}}}`,
	), applyFlavorHandler)
}

// triggerBuildHandler applies the two-phase staging guardrail: a build that is
// neither a dry run nor explicitly confirmed is staged for confirmation.
func triggerBuildHandler(deps Deps) coremcp.ToolHandler {
	return func(ctx context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
		var args struct {
			Flavor    string `json:"flavor"`
			Backend   string `json:"backend"`
			DryRun    bool   `json:"dry_run"`
			Confirmed bool   `json:"confirmed"`
		}
		if err := decodeArgs(req, &args); err != nil {
			return nil, err
		}
		if !args.DryRun && !args.Confirmed {
			preview := fmt.Sprintf("Trigger image build for flavor %q via backend %q", args.Flavor, args.Backend)
			staged := deps.Stager.Stage("trigger_build", args.Flavor, map[string]any{
				"flavor":  args.Flavor,
				"backend": args.Backend,
				"dry_run": args.DryRun,
			}, preview)
			return textResult(stagedMessage(staged, args.Flavor, args.Backend)), nil
		}
		return dispatchBuild(ctx, deps, args.Backend, args.Flavor, args.DryRun, "")
	}
}

func stagedMessage(staged *StagedAction, flavor, backend string) string {
	return fmt.Sprintf("⚠️ ACTION STAGED (Two-Phase Verification Guardrail)\nAction ID: %s\nTool: trigger_build\nTarget Flavor: %s\nBackend: %s\n\nTo execute this build, invoke `confirm_action` with `{\"action_id\": %q}` or re-run `trigger_build` with `\"confirmed\": true`.",
		staged.ID, flavor, backend, staged.ID)
}

// dispatchBuild runs the build dispatcher with the injected clock and renders
// the result, prefixed by an optional confirmation banner.
func dispatchBuild(ctx context.Context, deps Deps, backend, flavor string, dryRun bool, prefix string) (*coremcp.CallToolResult, error) {
	res, err := builder.Dispatch(ctx, builder.Request{
		Backend: builder.Backend(backend),
		Flavor:  flavor,
		DryRun:  dryRun,
		Clock:   deps.Clock,
	})
	if err != nil {
		return errorResult(err), nil
	}
	out, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("mcp: encode result: %w", err)
	}
	return textResult(prefix + string(out)), nil
}

func applyFlavorHandler(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
	var args struct {
		FlavorID string `json:"flavor_id"`
		DryRun   bool   `json:"dry_run"`
	}
	if err := decodeArgs(req, &args); err != nil {
		return nil, err
	}
	script, err := imageless.GenerateApplyScript(imageless.ApplyOptions{
		FlavorID: args.FlavorID,
		DryRun:   args.DryRun,
	})
	if err != nil {
		return errorResult(err), nil
	}
	return textResult(script), nil
}

func registerStagingTools(s *coremcp.Server, deps Deps) {
	s.AddTool(tool("list_staged_actions",
		"List all pending two-phase staged actions waiting for confirmation",
		`{"type":"object"}`,
	), func(_ context.Context, _ *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
		return jsonResult(deps.Stager.List())
	})
	s.AddTool(tool("confirm_action",
		"Confirm and execute a pending staged action by its action_id",
		`{"type":"object","required":["action_id"],"properties":{"action_id":{"type":"string"}}}`,
	), confirmActionHandler(deps))
	s.AddTool(tool("discard_staged_action",
		"Discard or cancel a pending staged action",
		`{"type":"object","required":["action_id"],"properties":{"action_id":{"type":"string"}}}`,
	), discardActionHandler(deps))
}

func confirmActionHandler(deps Deps) coremcp.ToolHandler {
	return func(ctx context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
		var args struct {
			ActionID string `json:"action_id"`
		}
		if err := decodeArgs(req, &args); err != nil {
			return nil, err
		}
		act, err := deps.Stager.Confirm(args.ActionID)
		if err != nil {
			return errorResult(err), nil
		}
		if act.Tool != "trigger_build" {
			return textResult(fmt.Sprintf("✅ Action %s confirmed (tool: %s)", act.ID, act.Tool)), nil
		}
		flavor, _ := act.Payload["flavor"].(string)
		backend, _ := act.Payload["backend"].(string)
		dryRun, _ := act.Payload["dry_run"].(bool)
		prefix := fmt.Sprintf("✅ Action %s confirmed and executed:\n", act.ID)
		return dispatchBuild(ctx, deps, backend, flavor, dryRun, prefix)
	}
}

func discardActionHandler(deps Deps) coremcp.ToolHandler {
	return func(_ context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
		var args struct {
			ActionID string `json:"action_id"`
		}
		if err := decodeArgs(req, &args); err != nil {
			return nil, err
		}
		if err := deps.Stager.Discard(args.ActionID); err != nil {
			return errorResult(err), nil
		}
		return textResult(fmt.Sprintf("Action %q discarded successfully", args.ActionID)), nil
	}
}
