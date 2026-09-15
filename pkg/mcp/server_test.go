// Copyright 2026 Lusoris
package mcp_test

import (
	"log/slog"
	"testing"

	sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/golusoris/golusoris/core/clock"

	"github.com/cordanaLLM/imago/pkg/mcp"
)

// newTestServer builds a tool-less SDK server exactly as golusoris core/mcp.Module
// does in production, then registers the imago tools on it. Tests own the raw SDK
// import; production code only imports core/mcp.
func newTestServer(t *testing.T, logger *slog.Logger) *mcp.Server {
	t.Helper()
	s := sdkmcp.NewServer(
		&sdkmcp.Implementation{Name: mcp.ServerName, Version: "test"},
		&sdkmcp.ServerOptions{Logger: logger},
	)
	fc := clock.NewFake()
	require.NoError(t, mcp.RegisterTools(s, mcp.Deps{Stager: mcp.NewStager(fc), Clock: fc}))
	return s
}

func TestRegisterTools(t *testing.T) {
	srv := newTestServer(t, slog.New(slog.DiscardHandler))
	require.NotNil(t, srv)
}

func TestRegisterToolsRejectsMissingDeps(t *testing.T) {
	s := sdkmcp.NewServer(&sdkmcp.Implementation{Name: mcp.ServerName, Version: "test"}, nil)
	err := mcp.RegisterTools(s, mcp.Deps{})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "required")

	err = mcp.RegisterTools(nil, mcp.Deps{Stager: mcp.NewStager(clock.NewFake()), Clock: clock.NewFake()})
	assert.Error(t, err)
}
