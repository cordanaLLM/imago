// Copyright 2026 Lusoris
package standards

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

func TestHasGPUVendor(t *testing.T) {
	for _, id := range []string{"docker-nvidia", "k3s-agent-intel", "ai-infer-amd"} {
		assert.True(t, hasGPUVendor(id), id)
	}
	for _, id := range []string{"docker-generic", "", "podman-generic"} {
		assert.False(t, hasGPUVendor(id), id)
	}
}

// Every tier in the catalogue that is not base has a rule, and every rule names a tier in use.
func TestTierRulesMatchCatalogue(t *testing.T) {
	used := map[string]bool{}
	for _, fl := range flavors.All() {
		used[fl.TierID] = true
		if fl.TierID != "base" {
			assert.Contains(t, tierRules, fl.TierID, fl.ID)
		}
	}
	for tier := range tierRules {
		assert.True(t, used[tier], "rule for unused tier %q", tier)
	}
	for id := range homelabRules {
		fl, err := flavors.Get(id)
		require.NoError(t, err, id)
		assert.Equal(t, "homelab", fl.TierID, id)
	}
}

func TestEnrichTierStandardUnknownTierChangesNothing(t *testing.T) {
	std := Standard{KernelParameters: map[string]string{}}
	enrichTierStandard(&std, flavors.Flavor{ID: "x-nvidia", TierID: "no-such-tier"})
	assert.Equal(t, Standard{KernelParameters: map[string]string{}}, std)
}

func TestEnrichContainersCDIOnlyForGPUVendors(t *testing.T) {
	gpu := Standard{KernelParameters: map[string]string{}}
	enrichContainers(&gpu, flavors.Flavor{ID: "docker-amd"})
	assert.True(t, gpu.CDISpecRequired)
	plain := Standard{KernelParameters: map[string]string{}}
	enrichContainers(&plain, flavors.Flavor{ID: "podman-generic"})
	assert.False(t, plain.CDISpecRequired)
	assert.Equal(t, []string{"podman", "buildah", "skopeo"}, plain.RequiredPackages)
}
