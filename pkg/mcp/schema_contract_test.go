// Copyright 2026 Lusoris
package mcp_test

import (
	"context"
	"encoding/json"
	"sort"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// toolContract is the input contract of one tool as clients see it in tools/list.
type toolContract struct {
	Required   []string
	Properties []string
}

// wantContracts pins the inferred input schemas. A field gains or loses
// `omitempty` only together with a change here: the required set is the
// contract, and before the typed AddTool it was written by hand.
var wantContracts = map[string]toolContract{
	"list_flavors":          {nil, []string{"tier"}},
	"get_flavor":            {[]string{"flavor_id"}, []string{"flavor_id"}},
	"validate_manifest":     {nil, []string{"path"}},
	"generate_cloudinit":    {[]string{"flavor"}, []string{"flavor", "hostname", "platform", "user"}},
	"get_standards":         {[]string{"flavor_id"}, []string{"flavor_id"}},
	"list_epics":            {nil, nil},
	"get_milestones":        {nil, nil},
	"inspect_compliance":    {nil, []string{"path"}},
	"trigger_build":         {[]string{"backend", "flavor"}, []string{"backend", "confirmed", "dry_run", "flavor"}},
	"apply_flavor":          {[]string{"flavor_id"}, []string{"dry_run", "flavor_id"}},
	"list_staged_actions":   {nil, nil},
	"confirm_action":        {[]string{"action_id"}, []string{"action_id"}},
	"discard_staged_action": {[]string{"action_id"}, []string{"action_id"}},
	"route_plan":            {nil, []string{"plan_path", "ready_only", "routing_path"}},
}

type listedSchema struct {
	Required             []string                   `json:"required"`
	Properties           map[string]json.RawMessage `json:"properties"`
	AdditionalProperties *json.RawMessage           `json:"additionalProperties"`
}

func contractOf(t *testing.T, schema any) (toolContract, string) {
	t.Helper()
	raw, err := json.Marshal(schema)
	require.NoError(t, err)
	var s listedSchema
	require.NoError(t, json.Unmarshal(raw, &s))
	var props []string
	for name := range s.Properties {
		props = append(props, name)
	}
	sort.Strings(props)
	sort.Strings(s.Required)
	if len(s.Required) == 0 {
		s.Required = nil // an absent and an empty list state the same contract
	}
	extra := "absent"
	if s.AdditionalProperties != nil {
		extra = string(*s.AdditionalProperties)
	}
	return toolContract{s.Required, props}, extra
}

func TestMCPToolInputContracts(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	res, err := session.ListTools(context.Background(), nil)
	require.NoError(t, err)
	seen := map[string]bool{}
	for _, tl := range res.Tools {
		want, ok := wantContracts[tl.Name]
		if !assert.True(t, ok, "tool %q has no pinned contract", tl.Name) {
			continue
		}
		seen[tl.Name] = true
		got, extra := contractOf(t, tl.InputSchema)
		assert.Equal(t, want, got, "tool %q input contract", tl.Name)
		assert.Equal(t, "false", extra, "tool %q must refuse unknown arguments", tl.Name)
	}
	assert.Len(t, seen, len(wantContracts), "pinned tools missing from tools/list")
}
