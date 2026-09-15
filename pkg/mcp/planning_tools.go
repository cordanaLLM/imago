// Copyright 2026 Lusoris
package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"path/filepath"
	"strings"

	coremcp "github.com/golusoris/golusoris/core/mcp"

	"github.com/cordanaLLM/imago/pkg/planning"
)

// Default locations of the tracked planning graph and its routing overlay.
const (
	DefaultPlanPath    = "planning/plan.json"
	DefaultRoutingPath = "planning/routing.json"
)

// repoRelativePath accepts only a clean, relative path inside the repository so
// an agent cannot route an arbitrary file through the planner.
func repoRelativePath(raw, fallback string) (string, error) {
	if raw == "" {
		return fallback, nil
	}
	clean := filepath.ToSlash(filepath.Clean(raw))
	if filepath.IsAbs(raw) || strings.HasPrefix(clean, "../") || clean == ".." {
		return "", fmt.Errorf("mcp: path %q must be relative to the repository", raw)
	}
	return filepath.FromSlash(clean), nil
}

func registerPlanningTools(s *coremcp.Server) {
	s.AddTool(
		&coremcp.Tool{
			Name:        "route_plan",
			Description: "Validate the tracked planning graph (praetor schema v1) and return its steps ranked for execution: ready local work first, scored by (1 + transitive unblocks) / cost. Set ready_only=true to receive only the ready set.",
			InputSchema: json.RawMessage(`{"type":"object","properties":{"plan_path":{"type":"string","description":"Repository-relative plan.json (default planning/plan.json)"},"routing_path":{"type":"string","description":"Repository-relative routing overlay (default planning/routing.json)"},"ready_only":{"type":"boolean"}}}`),
		},
		func(ctx context.Context, req *coremcp.CallToolRequest) (*coremcp.CallToolResult, error) {
			var args struct {
				PlanPath    string `json:"plan_path"`
				RoutingPath string `json:"routing_path"`
				ReadyOnly   bool   `json:"ready_only"`
			}
			if err := json.Unmarshal(req.Params.Arguments, &args); err != nil {
				return nil, err
			}
			routed, err := routePlanFiles(args.PlanPath, args.RoutingPath)
			if err != nil {
				return &coremcp.CallToolResult{IsError: true, Content: []coremcp.Content{&coremcp.TextContent{Text: err.Error()}}}, nil
			}
			if args.ReadyOnly {
				routed = planning.Ready(routed)
			}
			out, _ := json.MarshalIndent(routed, "", "  ")
			return &coremcp.CallToolResult{Content: []coremcp.Content{&coremcp.TextContent{Text: string(out)}}}, nil
		},
	)
}

// routePlanFiles loads both planning files from repository-relative paths and routes them.
func routePlanFiles(planRaw, routingRaw string) ([]planning.RoutedStep, error) {
	planPath, err := repoRelativePath(planRaw, DefaultPlanPath)
	if err != nil {
		return nil, err
	}
	routingPath, err := repoRelativePath(routingRaw, DefaultRoutingPath)
	if err != nil {
		return nil, err
	}
	plan, err := planning.Load(planPath)
	if err != nil {
		return nil, err
	}
	overlay, err := planning.LoadOverlay(routingPath, plan)
	if err != nil {
		return nil, err
	}
	return planning.Route(plan, overlay)
}
