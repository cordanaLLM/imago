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

// A dry run validates like a real dispatch: an unknown backend or flavor is
// refused, not reported as a successful plan.
func TestDispatchDryRunRefusesUnknownInput(t *testing.T) {
	cases := map[string]builder.Request{
		"unknown-backend": {Backend: "bogus", Flavor: "base-generic"},
		"empty-backend":   {Backend: "", Flavor: "base-generic"},
		"backend-case":    {Backend: "LOCAL", Flavor: "base-generic"},
		"unknown-flavor":  {Backend: builder.BackendLocal, Flavor: "invalid-flavor-name"},
	}
	for name, req := range cases {
		t.Run(name, func(t *testing.T) {
			req.DryRun = true
			req.Clock = clock.NewFake()
			res, err := builder.Dispatch(context.Background(), req)
			require.Error(t, err)
			assert.False(t, res.Success)
		})
	}
	require.NoError(t, builder.Validate(builder.BackendGitHub, "appliance-game-server"))
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
	// Each backend must reach its own dispatcher: the message names it.
	backends := map[builder.Backend]string{
		builder.BackendLocal:      "local build command formulated",
		builder.BackendGitea:      "GITEA Actions workflow dispatch",
		builder.BackendProxmox:    "Proxmox VE template clone task",
		builder.BackendGitLab:     "GitLab CI pipeline trigger",
		builder.BackendWoodpecker: "Woodpecker CI build triggered",
		builder.BackendHarbor:     "Harbor OCI artifact verification",
		builder.BackendMinIO:      "MinIO/S3 artifact storage target",
		builder.BackendJenkins:    "Jenkins remote job trigger",
		builder.BackendGitHub:     "GITHUB Actions workflow dispatch",
	}

	for b, want := range backends {
		req := builder.Request{
			Backend: b,
			Flavor:  "base-generic",
			Clock:   clock.NewFake(),
		}
		res, err := builder.Dispatch(ctx, req)
		require.NoError(t, err, "backend %s should succeed", b)
		assert.True(t, res.Success)
		assert.Contains(t, res.Message, want, "backend %s", b)
	}
}
