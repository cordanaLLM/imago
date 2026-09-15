// Copyright 2026 Lusoris
package planning_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/planning"
)

func fixturePlan() planning.Plan {
	return planning.Plan{
		SchemaVersion: 1,
		ID:            "plan-test",
		Project:       planning.Project{ID: "project-test", Title: "Test", Repository: "example/test", Revision: "rev"},
		Milestones:    []planning.Milestone{{ID: "m1", Title: "M1", Outcome: "done", DependsOn: []string{}}},
		Steps: []planning.Step{
			{ID: "s-root", Title: "Root", Kind: "implementation", Status: "proposed", MilestoneID: "m1", DependsOn: []string{}},
			{ID: "s-mid", Title: "Mid", Kind: "implementation", Status: "proposed", MilestoneID: "m1", DependsOn: []string{"s-root"}},
			{ID: "s-leaf", Title: "Leaf", Kind: "manual", Status: "proposed", MilestoneID: "m1", DependsOn: []string{"s-mid"}},
			{ID: "s-side", Title: "Side", Kind: "research", Status: "proposed", MilestoneID: "m1", DependsOn: []string{}},
		},
	}
}

func fixtureOverlay() planning.Overlay {
	return planning.Overlay{
		SchemaVersion: 1,
		PlanID:        "plan-test",
		Steps: map[string]planning.StepRoute{
			"s-root": {Cost: planning.CostSmall, Done: true},
			"s-mid":  {Cost: planning.CostSmall},
			"s-leaf": {Cost: planning.CostTrivial},
			"s-side": {Cost: planning.CostTrivial, NeedsExternalContract: true},
		},
	}
}

func writeJSON(t *testing.T, dir, name string, v any) string {
	t.Helper()
	data, err := json.Marshal(v)
	require.NoError(t, err)
	path := filepath.Join(dir, name)
	require.NoError(t, os.WriteFile(path, data, 0o600))
	return path
}

func TestLoadAndRoutePositive(t *testing.T) {
	dir := t.TempDir()
	planPath := writeJSON(t, dir, "plan.json", fixturePlan())
	overlayPath := writeJSON(t, dir, "routing.json", fixtureOverlay())

	plan, err := planning.Load(planPath)
	require.NoError(t, err)
	overlay, err := planning.LoadOverlay(overlayPath, plan)
	require.NoError(t, err)

	routed, err := planning.Route(plan, overlay)
	require.NoError(t, err)
	require.Len(t, routed, 4)

	// s-mid is ready (its only dependency is done), local, and unblocks s-leaf:
	// score (1+1)/2 = 1.0. s-side is ready but needs an external contract, so it
	// ranks behind every local ready step despite its equal raw score (1/1).
	assert.Equal(t, "s-mid", routed[0].ID)
	assert.Equal(t, planning.StateReady, routed[0].State)
	assert.InDelta(t, 1.0, routed[0].Score, 1e-9)
	assert.Equal(t, "s-side", routed[1].ID)
	assert.Equal(t, "s-leaf", routed[2].ID)
	assert.Equal(t, planning.StateBlocked, routed[2].State)
	assert.Equal(t, []string{"s-mid"}, routed[2].BlockedBy)
	assert.Equal(t, "s-root", routed[3].ID)
	assert.Equal(t, planning.StateDone, routed[3].State)

	ready := planning.Ready(routed)
	require.Len(t, ready, 2)
	assert.Equal(t, 1, ready[0].Rank)
}

func TestValidateNegative(t *testing.T) {
	cyclic := fixturePlan()
	cyclic.Steps[0].DependsOn = []string{"s-leaf"}
	err := cyclic.Validate()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "cycle")

	unknownDep := fixturePlan()
	unknownDep.Steps[1].DependsOn = []string{"s-missing"}
	assert.ErrorContains(t, unknownDep.Validate(), "unknown step")

	unknownMilestone := fixturePlan()
	unknownMilestone.Steps[1].MilestoneID = "m-missing"
	assert.ErrorContains(t, unknownMilestone.Validate(), "unknown milestone")

	wrongVersion := fixturePlan()
	wrongVersion.SchemaVersion = 2
	assert.ErrorContains(t, wrongVersion.Validate(), "schema_version")

	duplicate := fixturePlan()
	duplicate.Steps = append(duplicate.Steps, duplicate.Steps[0])
	assert.ErrorContains(t, duplicate.Validate(), "duplicate step")
}

func TestOverlayNegative(t *testing.T) {
	plan := fixturePlan()

	missing := fixtureOverlay()
	delete(missing.Steps, "s-leaf")
	_, err := planning.Route(&plan, &missing)
	assert.ErrorContains(t, err, "missing step")

	badCost := fixtureOverlay()
	badCost.Steps["s-leaf"] = planning.StepRoute{Cost: "huge"}
	_, err = planning.Route(&plan, &badCost)
	assert.ErrorContains(t, err, "unknown cost")

	wrongPlan := fixtureOverlay()
	wrongPlan.PlanID = "other"
	_, err = planning.Route(&plan, &wrongPlan)
	assert.ErrorContains(t, err, "plan_id")

	extra := fixtureOverlay()
	extra.Steps["s-ghost"] = planning.StepRoute{Cost: planning.CostSmall}
	_, err = planning.Route(&plan, &extra)
	assert.ErrorContains(t, err, "unknown step")

	_, err = planning.Route(nil, &extra)
	assert.Error(t, err)
}

func TestBoundaries(t *testing.T) {
	empty := fixturePlan()
	empty.Steps = nil
	assert.ErrorContains(t, empty.Validate(), "step count")

	dir := t.TempDir()
	big := filepath.Join(dir, "plan.json")
	require.NoError(t, os.WriteFile(big, make([]byte, planning.MaxPlanBytes+1), 0o600))
	_, err := planning.Load(big)
	assert.ErrorContains(t, err, "exceeds")

	_, err = planning.Load(filepath.Join(dir, "absent.json"))
	assert.Error(t, err)

	// A step with no dependents has zero transitive unblocks and score 1/cost.
	plan := fixturePlan()
	overlay := fixtureOverlay()
	routed, err := planning.Route(&plan, &overlay)
	require.NoError(t, err)
	for _, r := range routed {
		if r.ID == "s-leaf" {
			assert.Equal(t, 0, r.TransitiveUnblocks)
			assert.InDelta(t, 1.0, r.Score, 1e-9)
		}
	}
}
