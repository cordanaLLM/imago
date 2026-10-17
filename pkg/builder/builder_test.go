// Copyright 2026 Lusoris
package builder_test

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/builder"
)

// knownBackends lists every backend Validate accepts; none has an executor.
var knownBackends = []builder.Backend{
	builder.BackendLocal, builder.BackendGitea, builder.BackendProxmox,
	builder.BackendGitLab, builder.BackendWoodpecker, builder.BackendHarbor,
	builder.BackendMinIO, builder.BackendJenkins, builder.BackendGitHub,
}

// assertNoExecutionEvidence refuses a result that carries anything a caller
// could read as proof of a build: success, a timestamp, a job id or an artifact.
func assertNoExecutionEvidence(t *testing.T, res builder.Result) {
	t.Helper()
	assert.False(t, res.Success)
	out, err := json.Marshal(res)
	require.NoError(t, err)
	var fields map[string]any
	require.NoError(t, json.Unmarshal(out, &fields))
	for _, key := range []string{"triggered_at", "pipeline_id", "artifact_url"} {
		assert.NotContains(t, fields, key)
	}
}

// Every known backend once reported success without invoking anything. Each
// one is its own planted false-success case: a non-dry-run request must fail
// with the typed unavailable error and carry no execution evidence.
func TestDispatchRefusesEveryBackendWithoutExecutor(t *testing.T) {
	for _, b := range knownBackends {
		t.Run(string(b), func(t *testing.T) {
			res, err := builder.Dispatch(context.Background(), builder.Request{Backend: b, Flavor: "base-generic"})
			require.ErrorIs(t, err, builder.ErrBackendUnavailable)
			var unavailable *builder.BackendUnavailableError
			require.True(t, errors.As(err, &unavailable))
			assert.Equal(t, b, unavailable.Backend)
			assert.Equal(t, builder.StatusUnavailable, res.Status)
			assert.False(t, res.DryRun)
			assertNoExecutionEvidence(t, res)
		})
	}
}

// A dry run of every known backend reports a plan, never a success.
func TestDispatchDryRunReportsPlanOnly(t *testing.T) {
	for _, b := range knownBackends {
		t.Run(string(b), func(t *testing.T) {
			res, err := builder.Dispatch(context.Background(), builder.Request{Backend: b, Flavor: "base-generic", DryRun: true})
			require.NoError(t, err)
			assert.Equal(t, builder.StatusPlanned, res.Status)
			assert.True(t, res.DryRun)
			assert.Contains(t, res.Message, "no build was executed")
			assertNoExecutionEvidence(t, res)
		})
	}
}

// A dry run validates like a real dispatch: an unknown backend or flavor is
// refused, not reported as a plan.
func TestDispatchRefusesUnknownInput(t *testing.T) {
	cases := map[string]builder.Request{
		"unknown-backend": {Backend: "bogus", Flavor: "base-generic"},
		"empty-backend":   {Backend: "", Flavor: "base-generic"},
		"backend-case":    {Backend: "LOCAL", Flavor: "base-generic"},
		"unknown-flavor":  {Backend: builder.BackendLocal, Flavor: "invalid-flavor-name"},
	}
	for name, req := range cases {
		for _, dryRun := range []bool{true, false} {
			t.Run(name, func(t *testing.T) {
				req.DryRun = dryRun
				res, err := builder.Dispatch(context.Background(), req)
				require.Error(t, err)
				assert.NotErrorIs(t, err, builder.ErrBackendUnavailable)
				assert.Empty(t, res.Status)
				assertNoExecutionEvidence(t, res)
			})
		}
	}
	require.NoError(t, builder.Validate(builder.BackendGitHub, "appliance-game-server"))
}

// A cancelled context ends the request before validation reports anything.
func TestDispatchRefusesCancelledContext(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	res, err := builder.Dispatch(ctx, builder.Request{Backend: builder.BackendLocal, Flavor: "base-generic", DryRun: true})
	require.ErrorIs(t, err, context.Canceled)
	assert.Empty(t, res.Status)
	assertNoExecutionEvidence(t, res)
}
