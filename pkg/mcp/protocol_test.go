// Copyright 2026 Lusoris
package mcp_test

import (
	"context"
	"log/slog"
	"os"
	"path/filepath"
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

func TestMCPProtocolToolExecution(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	ctx := context.Background()

	t.Run("list_flavors_unfiltered", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "list_flavors",
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		require.NotEmpty(t, res.Content)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "base-generic")
		assert.Contains(t, text, "k8s-node-cilium")
	})

	t.Run("list_flavors_filtered", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "list_flavors",
			Arguments: map[string]any{"tier": "kubernetes"},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "k8s-node-cilium")
		assert.NotContains(t, text, "base-generic")
	})

	t.Run("get_flavor_valid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "get_flavor",
			Arguments: map[string]any{"flavor_id": "base-generic"},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "base-generic")
		assert.Contains(t, text, "00-base-strip.sh")
	})

	t.Run("get_flavor_invalid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "get_flavor",
			Arguments: map[string]any{"flavor_id": "unknown-flavor-xyz"},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "not found across")
	})

	t.Run("validate_manifest_default", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "validate_manifest",
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "Validation SUCCESS")
	})

	t.Run("validate_manifest_invalid_path", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "validate_manifest",
			Arguments: map[string]any{"path": "non-existent-manifest.json"},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})

	t.Run("generate_cloudinit_valid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "generate_cloudinit",
			Arguments: map[string]any{
				"flavor":   "base-generic",
				"hostname": "test-host",
				"platform": "proxmox",
				"user":     "ops",
			},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "#cloud-config")
		assert.Contains(t, text, "test-host")
		assert.Contains(t, text, "ops")
	})

	t.Run("generate_cloudinit_invalid_flavor", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "generate_cloudinit",
			Arguments: map[string]any{
				"flavor": "invalid-flavor",
			},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})

	t.Run("get_standards_valid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "get_standards",
			Arguments: map[string]any{"flavor_id": "base-generic"},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "base-generic")
		assert.Contains(t, text, "CIS Ubuntu Linux")
	})

	t.Run("get_standards_invalid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "get_standards",
			Arguments: map[string]any{"flavor_id": "invalid-flavor"},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})

	t.Run("list_epics", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "list_epics",
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "EPIC-01")
	})

	t.Run("get_milestones", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "get_milestones",
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "v2026")
	})

	t.Run("inspect_compliance_default", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "inspect_compliance",
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "kernel-param")
		assert.Contains(t, text, "net.ipv4.tcp_syncookies")
	})

	t.Run("inspect_compliance_invalid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "inspect_compliance",
			Arguments: map[string]any{"path": "non-existent-goss.yaml"},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})

	t.Run("apply_flavor_dry_run", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "apply_flavor",
			Arguments: map[string]any{
				"flavor_id": "base-generic",
				"dry_run":   true,
			},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "#!/usr/bin/env bash")
		assert.Contains(t, text, "DRY-RUN:")
	})

	t.Run("apply_flavor_invalid", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "apply_flavor",
			Arguments: map[string]any{
				"flavor_id": "invalid-flavor",
				"dry_run":   true,
			},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})

	t.Run("trigger_build_dry_run", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "trigger_build",
			Arguments: map[string]any{
				"flavor":  "base-generic",
				"backend": "local",
				"dry_run": true,
			},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "base-generic")
		assert.Contains(t, text, "local")
	})

	t.Run("trigger_build_invalid_flavor", func(t *testing.T) {
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "trigger_build",
			Arguments: map[string]any{
				"flavor":  "invalid-flavor-xyz",
				"backend": "local",
				"dry_run": true,
			},
		})
		require.NoError(t, err)
		assert.True(t, res.IsError)
	})

	t.Run("staging_lifecycle_via_protocol", func(t *testing.T) {
		// 1. Calling trigger_build without confirmed or dry_run should stage
		res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "trigger_build",
			Arguments: map[string]any{
				"flavor":  "base-generic",
				"backend": "local",
			},
		})
		require.NoError(t, err)
		assert.False(t, res.IsError)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, "ACTION STAGED")
		assert.Contains(t, text, "Action ID: act-")

		// 2. List staged actions
		resList, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "list_staged_actions",
			Arguments: map[string]any{},
		})
		require.NoError(t, err)
		assert.False(t, resList.IsError)
		listText := resList.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, listText, "trigger_build")

		// 3. Confirm with invalid action_id
		resConfirmErr, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "confirm_action",
			Arguments: map[string]any{
				"action_id": "nonexistent-action-id",
			},
		})
		require.NoError(t, err)
		assert.True(t, resConfirmErr.IsError)

		// 4. Discard with invalid action_id
		resDiscardErr, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
			Name: "discard_staged_action",
			Arguments: map[string]any{
				"action_id": "nonexistent-action-id",
			},
		})
		require.NoError(t, err)
		assert.True(t, resDiscardErr.IsError)
	})
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
		assert.Contains(t, text, `"state": "ready"`)
		assert.NotContains(t, text, `"state": "blocked"`)
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
