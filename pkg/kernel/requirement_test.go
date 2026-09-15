// Copyright 2026 Lusoris
package kernel_test

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/kernel"
)

// requirementDoc is a mutable copy of a valid Aegis-shaped requirement.
func requirementDoc() map[string]any {
	return map[string]any{
		"schema":         kernel.RequirementSchema,
		"correlation-id": "test-kernel-requirement-0001",
		"architectures":  []any{"x86-64"},
		"abi":            map[string]any{"minimum-release": "6.12", "target-release": "7.3"},
		"features": []any{
			map[string]any{"symbol": "CONFIG_KVM", "state": "module", "probe": "kernel-config", "required-by": "REQ-BOOT-01"},
			map[string]any{"symbol": "CONFIG_BPF_LSM", "state": "built-in", "probe": "lsm-list", "required-by": "REQ-P06-05"},
		},
	}
}

func parseDoc(t *testing.T, doc map[string]any) (*kernel.Requirement, error) {
	t.Helper()
	raw, err := json.Marshal(doc)
	require.NoError(t, err)
	return kernel.ParseRequirement(bytes.NewReader(raw))
}

func features(n int) []any {
	out := make([]any, 0, n)
	for i := 0; i < n; i++ {
		out = append(out, map[string]any{
			"symbol": fmt.Sprintf("CONFIG_F_%d", i), "state": "built-in", "probe": "kernel-config", "required-by": "REQ-X",
		})
	}
	return out
}

func TestLoadRequirementAegisFixtures(t *testing.T) {
	q, err := kernel.LoadRequirement(filepath.Join("testdata", "aegis-kernel-requirement.json"))
	require.NoError(t, err)
	assert.Equal(t, "aegis-m18-kernel-requirement-0001", q.CorrelationID)
	assert.Equal(t, []string{"x86-64"}, q.Architectures)
	assert.Equal(t, "6.12", q.ABI.MinimumRelease)
	assert.Equal(t, "7.3", q.ABI.TargetRelease)
	assert.Len(t, q.Features, 13)
	assert.Equal(t, "CONFIG_PREEMPT_RT", q.Features[0].Symbol)

	ref, err := kernel.LoadRequirement(filepath.Join("testdata", "aegis-kernel-requirement.reference.json"))
	require.NoError(t, err)
	assert.Equal(t, "7.2.4-1-cachyos", ref.ABI.ModuleABI)
	assert.Empty(t, ref.ABI.TargetRelease)
	assert.Len(t, ref.Features, 13)
}

func TestLoadRequirementMissingFile(t *testing.T) {
	_, err := kernel.LoadRequirement(filepath.Join("testdata", "does-not-exist.json"))
	require.Error(t, err)
	assert.Contains(t, err.Error(), "kernel requirement: open")
}

func TestParseRequirementRejectsEmptyFeatureList(t *testing.T) {
	doc := requirementDoc()
	doc["features"] = []any{}
	_, err := parseDoc(t, doc)
	require.Error(t, err)
	assert.True(t, errors.Is(err, kernel.ErrEmptyRequirement), "expected ErrEmptyRequirement, got %v", err)
	assert.Equal(t, "kernel requirement test-kernel-requirement-0001: features: feature list is empty", err.Error())

	delete(doc, "features")
	_, err = parseDoc(t, doc)
	assert.True(t, errors.Is(err, kernel.ErrEmptyRequirement), "absent features must be rejected too, got %v", err)
}

func TestParseRequirementNegative(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(doc map[string]any)
		want   string
	}{
		{"unknown field", func(d map[string]any) { d["extra"] = 1 }, `unknown field "extra"`},
		{"wrong schema", func(d map[string]any) { d["schema"] = "aegis.p01-nucleus.kernel-requirement.v2" }, "schema: must be"},
		{"missing correlation id", func(d map[string]any) { delete(d, "correlation-id") }, "kernel requirement: correlation-id:"},
		{"correlation id characters", func(d map[string]any) { d["correlation-id"] = "bad id" }, "correlation-id: must be"},
		{"no architectures", func(d map[string]any) { d["architectures"] = []any{} }, "architectures: must list 1..8"},
		{"uppercase architecture", func(d map[string]any) { d["architectures"] = []any{"X86-64"} }, "architectures[0]: must be a lowercase token"},
		{"duplicate architecture", func(d map[string]any) { d["architectures"] = []any{"x86-64", "x86-64"} }, "duplicate architecture x86-64"},
		{"minimum release not dotted", func(d map[string]any) { d["abi"] = map[string]any{"minimum-release": "6"} }, "abi.minimum-release: must be a dotted"},
		{"minimum release missing", func(d map[string]any) { d["abi"] = map[string]any{"target-release": "7.3"} }, "abi.minimum-release"},
		{"target release token", func(d map[string]any) {
			d["abi"] = map[string]any{"minimum-release": "6.12", "target-release": "7.3 rc"}
		}, "abi.target-release"},
		{"module abi token", func(d map[string]any) { d["abi"] = map[string]any{"minimum-release": "6.12", "module-abi": "-bad"} }, "abi.module-abi"},
		{"symbol prefix", func(d map[string]any) {
			d["features"] = []any{map[string]any{"symbol": "KVM", "state": "module", "probe": "kernel-config", "required-by": "R"}}
		}, "features[0].symbol: must match CONFIG_"},
		{"symbol lowercase", func(d map[string]any) {
			d["features"] = []any{map[string]any{"symbol": "CONFIG_kvm", "state": "module", "probe": "kernel-config", "required-by": "R"}}
		}, "features[0].symbol"},
		{"state", func(d map[string]any) {
			d["features"] = []any{map[string]any{"symbol": "CONFIG_KVM", "state": "y", "probe": "kernel-config", "required-by": "R"}}
		}, "features[0].state: must be built-in or module"},
		{"unknown probe", func(d map[string]any) {
			d["features"] = []any{map[string]any{"symbol": "CONFIG_KVM", "state": "module", "probe": "dmesg", "required-by": "R"}}
		}, `features[0].probe: unknown probe "dmesg"`},
		{"required-by empty", func(d map[string]any) {
			d["features"] = []any{map[string]any{"symbol": "CONFIG_KVM", "state": "module", "probe": "kernel-config", "required-by": ""}}
		}, "features[0].required-by"},
		{"duplicate symbol", func(d map[string]any) {
			f := d["features"].([]any)
			d["features"] = append(f, f[0])
		}, "features[2].symbol: duplicate symbol CONFIG_KVM"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			doc := requirementDoc()
			tc.mutate(doc)
			_, err := parseDoc(t, doc)
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.want)
		})
	}
}

func TestParseRequirementStrictDecoding(t *testing.T) {
	raw, err := json.Marshal(requirementDoc())
	require.NoError(t, err)

	_, err = kernel.ParseRequirement(bytes.NewReader(append(raw, []byte(" {}")...)))
	require.Error(t, err)
	assert.Contains(t, err.Error(), "trailing data")

	_, err = kernel.ParseRequirement(strings.NewReader("{"))
	require.Error(t, err)
	assert.Contains(t, err.Error(), "decode:")

	doc := requirementDoc()
	doc["correlation-id"] = strings.Repeat("a", int(kernel.MaxRequirementBytes))
	big, err := json.Marshal(doc)
	require.NoError(t, err)
	_, err = kernel.ParseRequirement(bytes.NewReader(big))
	require.Error(t, err)
	assert.True(t, errors.Is(err, kernel.ErrTooLarge), "expected ErrTooLarge, got %v", err)
}

func TestParseRequirementBoundaries(t *testing.T) {
	doc := requirementDoc()
	doc["features"] = features(kernel.MaxFeatures)
	q, err := parseDoc(t, doc)
	require.NoError(t, err)
	assert.Len(t, q.Features, kernel.MaxFeatures)

	doc["features"] = features(kernel.MaxFeatures + 1)
	_, err = parseDoc(t, doc)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "features: more than 512 entries")

	archs := make([]any, 0, kernel.MaxArchitectures+1)
	for i := 0; i <= kernel.MaxArchitectures; i++ {
		archs = append(archs, fmt.Sprintf("arch%d", i))
	}
	doc = requirementDoc()
	doc["architectures"] = archs[:kernel.MaxArchitectures]
	_, err = parseDoc(t, doc)
	require.NoError(t, err)
	doc["architectures"] = archs
	_, err = parseDoc(t, doc)
	require.Error(t, err)

	doc = requirementDoc()
	doc["correlation-id"] = strings.Repeat("c", kernel.MaxCorrelationIDLen)
	_, err = parseDoc(t, doc)
	require.NoError(t, err)
	doc["correlation-id"] = strings.Repeat("c", kernel.MaxCorrelationIDLen+1)
	_, err = parseDoc(t, doc)
	require.Error(t, err)
}

func TestKnownProbesAllowListIsExtensible(t *testing.T) {
	saved := kernel.KnownProbes
	t.Cleanup(func() { kernel.KnownProbes = saved })

	doc := requirementDoc()
	doc["features"] = []any{map[string]any{"symbol": "CONFIG_X", "state": "module", "probe": "sysfs-node", "required-by": "R"}}
	_, err := parseDoc(t, doc)
	require.Error(t, err)

	kernel.KnownProbes = append(append([]string{}, saved...), "sysfs-node")
	_, err = parseDoc(t, doc)
	require.NoError(t, err)
}
