// Copyright 2026 Lusoris
package mcp_test

import (
	"context"
	"os"
	"regexp"
	"testing"

	sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// The tests below complete the positive, negative and boundary cases of every
// registered tool that protocol_test.go leaves open, through the MCP protocol.

var actionIDPattern = regexp.MustCompile(`Action ID: (act-[0-9a-f]+)`)

// call runs one tool and returns its text and whether the server refused the
// call, either as a tool error or as a protocol error.
func call(t *testing.T, session *sdkmcp.ClientSession, name string, args map[string]any) (string, bool) {
	t.Helper()
	res, err := session.CallTool(context.Background(), &sdkmcp.CallToolParams{Name: name, Arguments: args})
	if err != nil {
		return err.Error(), true
	}
	require.NotEmpty(t, res.Content)
	return res.Content[0].(*sdkmcp.TextContent).Text, res.IsError
}

// stage stages a local build through trigger_build and returns its action ID.
func stage(t *testing.T, session *sdkmcp.ClientSession) string {
	t.Helper()
	text, refused := call(t, session, "trigger_build", map[string]any{"flavor": "base-generic", "backend": "local"})
	require.False(t, refused, text)
	m := actionIDPattern.FindStringSubmatch(text)
	require.Len(t, m, 2, text)
	return m[1]
}

func TestMCPToolsRefuseOutOfRangeInput(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	cases := []struct {
		name string
		tool string
		args map[string]any
		want string
	}{
		{"list_flavors_unknown_tier", "list_flavors", map[string]any{"tier": "gpu"}, "known tiers: base, containers"},
		{"list_flavors_wrong_type", "list_flavors", map[string]any{"tier": 7}, ""},
		{"get_flavor_empty_id", "get_flavor", map[string]any{"flavor_id": ""}, ""},
		{"get_standards_empty_id", "get_standards", map[string]any{"flavor_id": ""}, ""},
		{"apply_flavor_empty_id", "apply_flavor", map[string]any{"flavor_id": "", "dry_run": true}, ""},
		{"validate_manifest_absolute", "validate_manifest", map[string]any{"path": "/etc/hostname"}, "relative to the repository"},
		{"validate_manifest_escape", "validate_manifest", map[string]any{"path": "pkg/../../versions.json"}, "relative to the repository"},
		{"validate_manifest_not_a_manifest", "validate_manifest", map[string]any{"path": "go.mod"}, ""},
		{"inspect_compliance_absolute", "inspect_compliance", map[string]any{"path": "/etc/passwd"}, "relative to the repository"},
		{"inspect_compliance_escape", "inspect_compliance", map[string]any{"path": "../../../../../../etc/passwd"}, "relative to the repository"},
		{"trigger_build_dry_run_unknown_backend", "trigger_build", map[string]any{"flavor": "base-generic", "backend": "bogus", "dry_run": true}, "unsupported backend"},
		{"trigger_build_dry_run_empty_backend", "trigger_build", map[string]any{"flavor": "base-generic", "backend": "", "dry_run": true}, "unsupported backend"},
		{"trigger_build_backend_case", "trigger_build", map[string]any{"flavor": "base-generic", "backend": "LOCAL", "dry_run": true}, "unsupported backend"},
		{"trigger_build_stage_invalid_flavor", "trigger_build", map[string]any{"flavor": "invalid-flavor-xyz", "backend": "local"}, "invalid flavor"},
		{"trigger_build_stage_unknown_backend", "trigger_build", map[string]any{"flavor": "base-generic", "backend": "bogus"}, "unsupported backend"},
		{"confirm_action_empty_id", "confirm_action", map[string]any{"action_id": ""}, "not found"},
		{"discard_action_empty_id", "discard_staged_action", map[string]any{"action_id": ""}, "not found"},
		{"route_plan_absolute", "route_plan", map[string]any{"plan_path": "/etc/hostname"}, "relative to the repository"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			text, refused := call(t, session, tc.tool, tc.args)
			assert.True(t, refused, text)
			assert.Contains(t, text, tc.want)
			assert.NotContains(t, text, "root:")
		})
	}

	// A refused build must not have been staged.
	text, refused := call(t, session, "list_staged_actions", nil)
	require.False(t, refused, text)
	assert.JSONEq(t, "[]", text)
}

func TestMCPToolsAcceptBoundaryInput(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	cases := []struct {
		name string
		tool string
		args map[string]any
		want string
	}{
		{"list_flavors_upper_case_tier", "list_flavors", map[string]any{"tier": "KUBERNETES"}, "k8s-node-cilium"},
		{"list_flavors_empty_tier_is_unfiltered", "list_flavors", map[string]any{"tier": ""}, "appliance-game-server"},
		{"get_flavor_last_of_matrix", "get_flavor", map[string]any{"flavor_id": "appliance-game-server"}, "appliance-game-server"},
		{"get_standards_last_of_matrix", "get_standards", map[string]any{"flavor_id": "appliance-game-server"}, "appliance-game-server"},
		{"validate_manifest_dot_prefix", "validate_manifest", map[string]any{"path": "./versions.json"}, "Validation SUCCESS"},
		{"inspect_compliance_explicit_default", "inspect_compliance", map[string]any{"path": "tests/compliance/goss.yaml"}, "kernel-param"},
		{"list_epics_ignores_unknown_argument", "list_epics", map[string]any{"unused": true}, "EPIC-01"},
		{"get_milestones_ignores_unknown_argument", "get_milestones", map[string]any{"unused": true}, "1.0"},
		{"apply_flavor_live_script", "apply_flavor", map[string]any{"flavor_id": "base-generic", "dry_run": false}, "#!/usr/bin/env bash"},
		{"trigger_build_dry_run_last_backend", "trigger_build", map[string]any{"flavor": "appliance-game-server", "backend": "github", "dry_run": true}, "dry-run"},
		{"list_staged_actions_empty", "list_staged_actions", nil, "[]"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			text, refused := call(t, session, tc.tool, tc.args)
			assert.False(t, refused, text)
			assert.Contains(t, text, tc.want)
		})
	}

	text, _ := call(t, session, "apply_flavor", map[string]any{"flavor_id": "base-generic", "dry_run": false})
	assert.NotContains(t, text, "DRY-RUN:")
}

func TestMCPTrackerToolsFailWithoutTrackedFiles(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	wd, err := os.Getwd()
	require.NoError(t, err)
	require.NoError(t, os.Chdir(t.TempDir()))
	defer func() { require.NoError(t, os.Chdir(wd)) }()

	for _, name := range []string{"list_epics", "get_milestones", "validate_manifest", "inspect_compliance"} {
		text, refused := call(t, session, name, nil)
		assert.True(t, refused, "%s: %s", name, text)
	}
}

func TestMCPConfirmActionExecutesOnce(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	id := stage(t, session)

	text, refused := call(t, session, "list_staged_actions", nil)
	require.False(t, refused, text)
	assert.Contains(t, text, id)

	text, refused = call(t, session, "confirm_action", map[string]any{"action_id": id})
	require.False(t, refused, text)
	assert.Contains(t, text, "confirmed and executed")
	assert.Contains(t, text, "local build command formulated")

	text, refused = call(t, session, "confirm_action", map[string]any{"action_id": id})
	assert.True(t, refused, text)
	assert.Contains(t, text, "cannot be confirmed")
}

func TestMCPDiscardActionRemovesIt(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	kept := stage(t, session)
	dropped := stage(t, session)
	require.NotEqual(t, kept, dropped)

	text, refused := call(t, session, "discard_staged_action", map[string]any{"action_id": dropped})
	require.False(t, refused, text)
	assert.Contains(t, text, "discarded successfully")

	text, refused = call(t, session, "list_staged_actions", nil)
	require.False(t, refused, text)
	assert.Contains(t, text, kept)
	assert.NotContains(t, text, dropped)

	for _, name := range []string{"discard_staged_action", "confirm_action"} {
		text, refused = call(t, session, name, map[string]any{"action_id": dropped})
		assert.True(t, refused, "%s: %s", name, text)
	}
}
