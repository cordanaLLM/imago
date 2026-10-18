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

// RoutePlanArgs holds the input arguments for the route_plan tool.
type RoutePlanArgs struct {
	PlanPath    string `json:"plan_path,omitempty" jsonschema:"Repository-relative plan.json (default planning/plan.json)"`
	RoutingPath string `json:"routing_path,omitempty" jsonschema:"Repository-relative routing overlay (default planning/routing.json)"`
	ReadyOnly   bool   `json:"ready_only,omitempty" jsonschema:"Set to true to receive only the ready set"`
}

func registerPlanningTools(s *coremcp.Server) {
	coremcp.AddTool(s, &coremcp.Tool{
		Name:        "route_plan",
		Description: "Validate the tracked planning graph (praetor schema v1) and return its steps ranked for execution: ready local work first, scored by (1 + transitive unblocks) / cost. Set ready_only=true to receive only the ready set.",
	}, routePlanHandler)
}

func routePlanHandler(_ context.Context, _ *coremcp.CallToolRequest, args RoutePlanArgs) (*coremcp.CallToolResult, any, error) {
	routed, err := routePlanFiles(args.PlanPath, args.RoutingPath)
	if err != nil {
		return &coremcp.CallToolResult{IsError: true, Content: []coremcp.Content{&coremcp.TextContent{Text: err.Error()}}}, nil, nil
	}
	if args.ReadyOnly {
		routed = planning.Ready(routed)
	}
	out, err := json.MarshalIndent(routed, "", "  ")
	if err != nil {
		return nil, nil, fmt.Errorf("mcp: encode result: %w", err)
	}
	return &coremcp.CallToolResult{Content: []coremcp.Content{&coremcp.TextContent{Text: string(out)}}}, nil, nil
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
