// Copyright 2026 Lusoris
package mcp_test

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// backendNames lists every backend trigger_build accepts; none has an executor.
var backendNames = []string{"local", "gitea", "proxmox", "gitlab", "woodpecker", "harbor", "minio", "jenkins", "github"}

// assertBuildUnavailable refuses a tool result that reads as an executed build.
func assertBuildUnavailable(t *testing.T, text string, refused bool) {
	t.Helper()
	assert.True(t, refused, text)
	assert.Contains(t, text, "not implemented")
	for _, evidence := range []string{"executed", `"success": true`, "pipeline_id", "artifact_url", "triggered_at"} {
		assert.NotContains(t, text, evidence)
	}
}

// Each backend is a planted false-success case on both MCP paths: the direct
// confirmed call and the staged call confirmed through confirm_action.
func TestMCPBuildReportsUnavailableForEveryBackend(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	for _, backend := range backendNames {
		t.Run(backend+"/confirmed", func(t *testing.T) {
			text, refused := call(t, session, "trigger_build", map[string]any{"flavor": "base-generic", "backend": backend, "confirmed": true})
			assertBuildUnavailable(t, text, refused)
		})
		t.Run(backend+"/staged", func(t *testing.T) {
			text, refused := call(t, session, "trigger_build", map[string]any{"flavor": "base-generic", "backend": backend})
			require.False(t, refused, text)
			m := actionIDPattern.FindStringSubmatch(text)
			require.Len(t, m, 2, text)
			text, refused = call(t, session, "confirm_action", map[string]any{"action_id": m[1]})
			assertBuildUnavailable(t, text, refused)
		})
	}
}

// A dry run of every backend reports a plan and no execution evidence.
func TestMCPBuildDryRunReportsPlanOnly(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	for _, backend := range backendNames {
		t.Run(backend, func(t *testing.T) {
			text, refused := call(t, session, "trigger_build", map[string]any{"flavor": "base-generic", "backend": backend, "dry_run": true})
			require.False(t, refused, text)
			var payload map[string]any
			require.NoError(t, json.Unmarshal([]byte(text), &payload))
			assert.Equal(t, "planned", payload["status"])
			assert.Equal(t, true, payload["dry_run"])
			assert.Equal(t, false, payload["success"])
			for _, key := range []string{"pipeline_id", "artifact_url", "triggered_at"} {
				assert.NotContains(t, payload, key)
			}
		})
	}
}

// An unknown backend is refused on the dry-run and the confirmed path alike,
// with the validation error rather than the unavailable-executor error.
func TestMCPBuildRefusesUnknownBackend(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	for _, mode := range []string{"dry_run", "confirmed"} {
		text, refused := call(t, session, "trigger_build", map[string]any{"flavor": "base-generic", "backend": "unknown", mode: true})
		assert.True(t, refused, text)
		assert.Contains(t, text, "unsupported backend")
		assert.NotContains(t, text, "not implemented")
	}
}
