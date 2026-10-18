// Copyright 2026 Lusoris
package mcp_test

import (
	"context"
	"sync/atomic"
	"testing"

	sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	coremcp "github.com/golusoris/golusoris/core/mcp"

	"github.com/cordanaLLM/imago/pkg/mcp"
)

func TestMCPUnknownToolReturnsSDKError(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()

	ctx := context.Background()
	params := &sdkmcp.CallToolParams{Name: "definitely_unknown_tool"}
	res, err := session.CallTool(ctx, params)
	require.Error(t, err)
	assert.Nil(t, res)
	assert.Contains(t, err.Error(), `unknown tool "definitely_unknown_tool"`)
}

type testToolArgs struct {
	RequiredField string `json:"required_field" jsonschema:"Mandatory test field"`
	OptionalField string `json:"optional_field,omitempty" jsonschema:"Optional test field"`
}

func setupTestToolSession(t *testing.T, counter *atomic.Int32) (*sdkmcp.ClientSession, func()) {
	t.Helper()
	server := sdkmcp.NewServer(
		&sdkmcp.Implementation{Name: mcp.ServerName, Version: "test"},
		nil,
	)
	coremcp.AddTool(server, &coremcp.Tool{
		Name:        "test_typed_tool",
		Description: "A test tool to verify schema enforcement before handler execution",
	}, func(_ context.Context, _ *coremcp.CallToolRequest, args testToolArgs) (*coremcp.CallToolResult, any, error) {
		counter.Add(1)
		return &coremcp.CallToolResult{
			Content: []coremcp.Content{&coremcp.TextContent{Text: "ok: " + args.RequiredField}},
		}, nil, nil
	})

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
	}
	return clientSession, cleanup
}

func TestMCPValidationRefusesBeforeHandlerRuns(t *testing.T) {
	var handlerCounter atomic.Int32
	clientSession, cleanup := setupTestToolSession(t, &handlerCounter)
	defer cleanup()
	ctx := context.Background()

	t.Run("missing_required_field_refused_before_handler", func(t *testing.T) {
		res, err := clientSession.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "test_typed_tool",
			Arguments: map[string]any{},
		})
		require.NoError(t, err)
		require.NotNil(t, res)
		assert.True(t, res.IsError)
		require.NotEmpty(t, res.Content)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, `validating "arguments"`)
		assert.Contains(t, text, `missing properties: ["required_field"]`)
		assert.Equal(t, int32(0), handlerCounter.Load(), "handler must not be reached on missing required field")
	})

	t.Run("wrong_typed_field_refused_before_handler", func(t *testing.T) {
		res, err := clientSession.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "test_typed_tool",
			Arguments: map[string]any{"required_field": 12345},
		})
		require.NoError(t, err)
		require.NotNil(t, res)
		assert.True(t, res.IsError)
		require.NotEmpty(t, res.Content)
		text := res.Content[0].(*sdkmcp.TextContent).Text
		assert.Contains(t, text, `validating "arguments"`)
		assert.Contains(t, text, `type: 12345 has type "integer", want "string"`)
		assert.Equal(t, int32(0), handlerCounter.Load(), "handler must not be reached on wrong-typed field")
	})

	t.Run("valid_required_field_executes_handler", func(t *testing.T) {
		res, err := clientSession.CallTool(ctx, &sdkmcp.CallToolParams{
			Name:      "test_typed_tool",
			Arguments: map[string]any{"required_field": "hello"},
		})
		require.NoError(t, err)
		require.NotNil(t, res)
		assert.False(t, res.IsError)
		assert.Equal(t, int32(1), handlerCounter.Load(), "handler must be reached when arguments are valid")
	})
}

func TestMCPRegisteredToolsRefuseInvalidSchemaInput(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	ctx := context.Background()

	// Missing required field "flavor_id" on get_flavor
	res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
		Name:      "get_flavor",
		Arguments: map[string]any{},
	})
	require.NoError(t, err)
	assert.True(t, res.IsError)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, `validating "arguments"`)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, `missing properties: ["flavor_id"]`)

	// Wrong-typed field on get_flavor: flavor_id = 999
	res, err = session.CallTool(ctx, &sdkmcp.CallToolParams{
		Name:      "get_flavor",
		Arguments: map[string]any{"flavor_id": 999},
	})
	require.NoError(t, err)
	assert.True(t, res.IsError)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, `validating "arguments"`)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, `type: 999 has type "integer", want "string"`)
}

func TestMCPBoundaryRequiredFieldsOnlySucceeds(t *testing.T) {
	session, cleanup := setupTestSession(t)
	defer cleanup()
	ctx := context.Background()

	// 1. trigger_build: required [flavor, backend], optional [dry_run, confirmed]
	res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
		Name:      "trigger_build",
		Arguments: map[string]any{"flavor": "base-generic", "backend": "local"},
	})
	require.NoError(t, err)
	assert.False(t, res.IsError)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, "ACTION STAGED")

	// 2. generate_cloudinit: required [flavor], optional [hostname, user, platform]
	res, err = session.CallTool(ctx, &sdkmcp.CallToolParams{
		Name:      "generate_cloudinit",
		Arguments: map[string]any{"flavor": "base-generic"},
	})
	require.NoError(t, err)
	assert.False(t, res.IsError)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, "#cloud-config")

	// 3. apply_flavor: required [flavor_id], optional [dry_run]
	res, err = session.CallTool(ctx, &sdkmcp.CallToolParams{
		Name:      "apply_flavor",
		Arguments: map[string]any{"flavor_id": "base-generic"},
	})
	require.NoError(t, err)
	assert.False(t, res.IsError)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, "#!/usr/bin/env bash")
}
