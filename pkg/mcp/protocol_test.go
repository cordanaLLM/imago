// Copyright 2026 Lusoris
package mcp_test

import (
	"context"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"testing"

	sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestSession(t *testing.T) (*sdkmcp.ClientSession, func()) {
	t.Helper()

	wd, err := os.Getwd()
	require.NoError(t, err)
	repoRoot := filepath.Join(wd, "..", "..")
	err = os.Chdir(repoRoot)
	require.NoError(t, err)

	logger := slog.New(slog.DiscardHandler)
	server := newTestServer(t, logger)

	serverTransport, clientTransport := sdkmcp.NewInMemoryTransports()
	ctx := context.Background()

	serverSession, err := server.Connect(ctx, serverTransport, nil)
	require.NoError(t, err)

	client := sdkmcp.NewClient(
		&sdkmcp.Implementation{Name: "test-client", Version: "1.0.0"},
		nil,
	)
	clientSession, err := client.Connect(ctx, clientTransport, nil)
	require.NoError(t, err)

	cleanup := func() {
		_ = clientSession.Close()
		_ = serverSession.Close()
		_ = os.Chdir(wd)
	}

	return clientSession, cleanup
}

func TestMCPProtocolHandshakeAndToolListing(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	ctx := context.Background()
	res, err := session.ListTools(ctx, nil)
	require.NoError(t, err)
	require.NotNil(t, res)

	expectedTools := []string{
		"list_flavors",
		"get_flavor",
		"validate_manifest",
		"generate_cloudinit",
		"get_standards",
		"list_epics",
		"get_milestones",
		"inspect_compliance",
		"trigger_build",
		"apply_flavor",
		"list_staged_actions",
		"confirm_action",
		"discard_staged_action",
		"route_plan",
	}

	assert.Equal(t, len(expectedTools), len(res.Tools))
	toolNames := make(map[string]bool)
	for _, tool := range res.Tools {
		toolNames[tool.Name] = true
		assert.NotEmpty(t, tool.Description)
		assert.NotEmpty(t, tool.InputSchema)
	}

	for _, name := range expectedTools {
		assert.True(t, toolNames[name], "Missing registered tool %s", name)
	}
}

// toolCase is one tool call over the protocol: the result must carry isError
// as given, and its text must hold every want and none of the absent strings.
type toolCase struct {
	name    string
	tool    string
	args    map[string]any
	isError bool
	want    []string
	absent  []string
}

var toolCases = []toolCase{
	{name: "list_flavors_unfiltered", tool: "list_flavors", want: []string{"base-generic", "k8s-node-cilium"}},
	{name: "list_flavors_filtered", tool: "list_flavors", args: map[string]any{"tier": "kubernetes"}, want: []string{"k8s-node-cilium"}, absent: []string{"base-generic"}},
	{name: "get_flavor_valid", tool: "get_flavor", args: map[string]any{"flavor_id": "base-generic"}, want: []string{"base-generic", "00-base-strip.sh"}},
	{name: "get_flavor_invalid", tool: "get_flavor", args: map[string]any{"flavor_id": "unknown-flavor-xyz"}, isError: true, want: []string{"not found across"}},
	{name: "validate_manifest_default", tool: "validate_manifest", want: []string{"Validation SUCCESS"}},
	{name: "validate_manifest_invalid_path", tool: "validate_manifest", args: map[string]any{"path": "non-existent-manifest.json"}, isError: true},
	{name: "generate_cloudinit_valid", tool: "generate_cloudinit", args: map[string]any{
		"flavor": "base-generic", "hostname": "test-host", "platform": "proxmox", "user": "ops",
	}, want: []string{"#cloud-config", "test-host", "ops"}},
	{name: "generate_cloudinit_invalid_flavor", tool: "generate_cloudinit", args: map[string]any{"flavor": "invalid-flavor"}, isError: true},
	{name: "get_standards_valid", tool: "get_standards", args: map[string]any{"flavor_id": "base-generic"}, want: []string{"base-generic", "CIS Ubuntu Linux"}},
	{name: "get_standards_invalid", tool: "get_standards", args: map[string]any{"flavor_id": "invalid-flavor"}, isError: true},
	{name: "list_epics", tool: "list_epics", want: []string{"EPIC-01"}},
	{name: "get_milestones", tool: "get_milestones", want: []string{"0.1.0 — First release"}},
	{name: "inspect_compliance_default", tool: "inspect_compliance", want: []string{"kernel-param", "net.ipv4.tcp_syncookies"}},
	{name: "inspect_compliance_invalid", tool: "inspect_compliance", args: map[string]any{"path": "non-existent-goss.yaml"}, isError: true},
	{name: "apply_flavor_dry_run", tool: "apply_flavor", args: map[string]any{"flavor_id": "base-generic", "dry_run": true}, want: []string{"#!/usr/bin/env bash", "DRY-RUN:"}},
	{name: "apply_flavor_invalid", tool: "apply_flavor", args: map[string]any{"flavor_id": "invalid-flavor", "dry_run": true}, isError: true},
	{name: "trigger_build_dry_run", tool: "trigger_build", args: map[string]any{
		"flavor": "base-generic", "backend": "local", "dry_run": true,
	}, want: []string{"base-generic", "local", `"status":"planned"`, `"success":false`}},
	{name: "trigger_build_invalid_flavor", tool: "trigger_build", args: map[string]any{
		"flavor": "invalid-flavor-xyz", "backend": "local", "dry_run": true,
	}, isError: true},
}

// callTool calls one tool and returns the result with the text of its first
// content block.
func callTool(t *testing.T, session *sdkmcp.ClientSession, tool string, args map[string]any) (*sdkmcp.CallToolResult, string) {
	t.Helper()
	params := &sdkmcp.CallToolParams{Name: tool}
	if args != nil {
		params.Arguments = args
	}
	res, err := session.CallTool(context.Background(), params)
	require.NoError(t, err)
	require.NotEmpty(t, res.Content)
	return res, res.Content[0].(*sdkmcp.TextContent).Text
}

func TestMCPProtocolToolExecution(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	for _, tc := range toolCases {
		t.Run(tc.name, func(t *testing.T) {
			res, text := callTool(t, session, tc.tool, tc.args)
			assert.Equal(t, tc.isError, res.IsError)
			for _, want := range tc.want {
				assert.Contains(t, text, want)
			}
			for _, absent := range tc.absent {
				assert.NotContains(t, text, absent)
			}
		})
	}
}

func TestMCPProtocolCloudInitBounds(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	t.Run("generate_cloudinit_planted_values", func(t *testing.T) {
		for _, args := range []map[string]any{
			{"flavor": "base-generic", "hostname": "x\nruncmd: [planted]"},
			{"flavor": "base-generic", "user": "root"},
			{"flavor": "base-generic", "platform": "esxi"},
		} {
			res, text := callTool(t, session, "generate_cloudinit", args)
			assert.True(t, res.IsError, args)
			assert.NotContains(t, text, "#cloud-config", args)
		}
	})

	t.Run("generate_cloudinit_boundary", func(t *testing.T) {
		host := strings.Repeat("h", 63)
		res, text := callTool(t, session, "generate_cloudinit", map[string]any{"flavor": "base-generic", "hostname": host, "platform": "UTM"})
		assert.False(t, res.IsError)
		assert.Contains(t, text, "hostname: "+host)
	})
}

func TestMCPProtocolStagingLifecycle(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	// trigger_build without confirmed or dry_run stages the build.
	res, text := callTool(t, session, "trigger_build", map[string]any{"flavor": "base-generic", "backend": "local"})
	assert.False(t, res.IsError)
	assert.Contains(t, text, "ACTION STAGED")
	assert.Contains(t, text, "Action ID: act-")

	res, text = callTool(t, session, "list_staged_actions", map[string]any{})
	assert.False(t, res.IsError)
	assert.Contains(t, text, "trigger_build")

	for _, tool := range []string{"confirm_action", "discard_staged_action"} {
		res, _ = callTool(t, session, tool, map[string]any{"action_id": "nonexistent-action-id"})
		assert.True(t, res.IsError, tool)
	}
}

func TestMCPProtocolRoutePlan(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	ctx := context.Background()

	t.Run("ready_set_from_tracked_graph", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "route_plan",
			Arguments: map[string]any{"ready_only": true},
		})
		require.NoError(t, err)
		require.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, `"state":"ready"`)
		assert.NotContains(t, text, `"state":"blocked"`)
	})

	t.Run("rejects_path_escape", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "route_plan",
			Arguments: map[string]any{"plan_path": "../outside/plan.json"},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
		assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, "relative to the repository")
	})

	t.Run("missing_overlay_is_an_error", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "route_plan",
			Arguments: map[string]any{"routing_path": "planning/absent.json"},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})
}
