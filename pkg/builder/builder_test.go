// Copyright 2026 Lusoris
package builder_test

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/golusoris/golusoris/core/clock"

	"github.com/cordanaLLM/imago/pkg/builder"
)

func TestDispatchDryRun(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	req := builder.Request{
		Backend: builder.BackendLocal,
		Flavor:  "base-generic",
		DryRun:  true,
		Clock:   clock.NewFake(),
	}

	res, err := builder.Dispatch(ctx, req)
	require.NoError(t, err)
	assert.True(t, res.Success)
	assert.Contains(t, res.Message, "dry-run")
}

func TestDispatchInvalidFlavor(t *testing.T) {
	ctx := context.Background()
	req := builder.Request{
		Backend: builder.BackendLocal,
		Flavor:  "invalid-flavor-name",
		Clock:   clock.NewFake(),
	}

	_, err := builder.Dispatch(ctx, req)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid flavor")
}

func TestDispatchRequiresClock(t *testing.T) {
	_, err := builder.Dispatch(context.Background(), builder.Request{
		Backend: builder.BackendLocal,
		Flavor:  "base-generic",
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "clock is required")
}

func TestDispatchBackends(t *testing.T) {
	ctx := context.Background()
	backends := []builder.Backend{
		builder.BackendLocal,
		builder.BackendGitea,
		builder.BackendProxmox,
		builder.BackendGitLab,
		builder.BackendWoodpecker,
		builder.BackendHarbor,
		builder.BackendMinIO,
		builder.BackendJenkins,
		builder.BackendGitHub,
	}

	for _, b := range backends {
		req := builder.Request{
			Backend: b,
			Flavor:  "base-generic",
			Clock:   clock.NewFake(),
		}
		res, err := builder.Dispatch(ctx, req)
		require.NoError(t, err, "backend %s should succeed", b)
		assert.True(t, res.Success)
		assert.NotEmpty(t, res.Message)
	}
}
