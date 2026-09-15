// Copyright 2026 Lusoris
package flavors_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

func TestAllFlavorsCount(t *testing.T) {
	all := flavors.All()
	assert.Len(t, all, 44, "flavor catalog must contain exactly 44 flavors")
}

func TestAllTiersCount(t *testing.T) {
	tiers := flavors.Tiers()
	assert.Len(t, tiers, 7, "must define exactly 7 workload tiers")
}

func TestFlavorProperties(t *testing.T) {
	seen := make(map[string]bool)
	for _, f := range flavors.All() {
		assert.NotEmpty(t, f.ID, "flavor ID must not be empty")
		assert.False(t, seen[f.ID], "flavor ID must be unique: %s", f.ID)
		seen[f.ID] = true

		assert.NotEmpty(t, f.Name)
		assert.NotEmpty(t, f.HardwareStack)
		assert.NotEmpty(t, f.KernelProfile)
		assert.NotEmpty(t, f.Description)
		assert.NotEmpty(t, f.Provisioners, "flavor must have provisioners")
		assert.GreaterOrEqual(t, f.TierNumber, 1)
		assert.LessOrEqual(t, f.TierNumber, 7)
	}
}

func TestGetFlavor(t *testing.T) {
	fl, err := flavors.Get("base-generic")
	require.NoError(t, err)
	assert.Equal(t, "base-generic", fl.ID)
	assert.Equal(t, "base", fl.TierID)
	assert.Contains(t, fl.Provisioners, "00-base-strip.sh")

	_, err = flavors.Get("nonexistent-flavor")
	assert.Error(t, err)
}

func TestFilterByTier(t *testing.T) {
	baseFlavors := flavors.FilterByTier("base")
	assert.Len(t, baseFlavors, 8)

	containerFlavors := flavors.FilterByTier("containers")
	assert.Len(t, containerFlavors, 7)

	k8sFlavors := flavors.FilterByTier("kubernetes")
	assert.Len(t, k8sFlavors, 9)

	k3sFlavors := flavors.FilterByTier("k3s")
	assert.Len(t, k3sFlavors, 5)

	cloudnativeFlavors := flavors.FilterByTier("cloudnative")
	assert.Len(t, cloudnativeFlavors, 4)

	aiFlavors := flavors.FilterByTier("ai-infer")
	assert.Len(t, aiFlavors, 6)

	homelabFlavors := flavors.FilterByTier("homelab")
	assert.Len(t, homelabFlavors, 5)
}

func TestSearch(t *testing.T) {
	nvidiaResults := flavors.Search("nvidia")
	assert.NotEmpty(t, nvidiaResults)
	for _, r := range nvidiaResults {
		hasNvidia := assert.ObjectsAreEqual(true,
			assert.Contains(t, r.ID, "nvidia") ||
				assert.Contains(t, r.Name, "NVIDIA") ||
				assert.Contains(t, r.Description, "NVIDIA"))
		assert.True(t, hasNvidia)
	}
}
