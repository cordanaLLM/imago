// Copyright 2026 Lusoris
package mcp_test

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestMCPToolErrorResult(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	res, text := callTool(t, session, "get_flavor", map[string]any{"flavor_id": "unknown-flavor-xyz"})
	assert.True(t, res.IsError)
	assert.Equal(t, `flavor "unknown-flavor-xyz" not found across 44 targets`, text)
	assert.Nil(t, res.StructuredContent)
}

func TestMCPListFlavorsStructuredResult(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	res, text := callTool(t, session, "list_flavors", nil)
	require.False(t, res.IsError)
	require.NotNil(t, res.StructuredContent)
	structured, err := json.Marshal(res.StructuredContent)
	require.NoError(t, err)
	assert.JSONEq(t, string(structured), text)
	var list []map[string]any
	require.NoError(t, json.Unmarshal([]byte(text), &list))
	assert.Len(t, list, 44)
}
