// Copyright 2026 Lusoris
package planning

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDependencyGraph(t *testing.T) {
	steps := map[string]Step{
		"a": {ID: "a"},
		"b": {ID: "b", DependsOn: []string{"a"}},
		"c": {ID: "c", DependsOn: []string{"a", "b"}},
	}
	indegree, dependents := dependencyGraph(steps)
	assert.Equal(t, map[string]int{"a": 0, "b": 1, "c": 2}, indegree)
	assert.ElementsMatch(t, []string{"b", "c"}, dependents["a"])
	assert.Equal(t, []string{"c"}, dependents["b"])
	assert.Empty(t, dependents["c"])
}

func TestDependencyGraphEmpty(t *testing.T) {
	indegree, dependents := dependencyGraph(map[string]Step{})
	assert.Empty(t, indegree)
	assert.Empty(t, dependents)
}

func TestReleaseDependentsQueuesOnlyFreedSteps(t *testing.T) {
	indegree := map[string]int{"b": 1, "c": 2}
	queue := releaseDependents([]string{"a"}, []string{"b", "c"}, indegree)
	assert.Equal(t, []string{"a", "b"}, queue)
	assert.Equal(t, map[string]int{"b": 0, "c": 1}, indegree)
	assert.Equal(t, []string{"a"}, releaseDependents([]string{"a"}, nil, indegree))
}

func TestCheckAcyclic(t *testing.T) {
	require.NoError(t, checkAcyclic(map[string]Step{}))
	require.NoError(t, checkAcyclic(map[string]Step{"a": {ID: "a"}, "b": {ID: "b", DependsOn: []string{"a"}}}))
	self := map[string]Step{"a": {ID: "a", DependsOn: []string{"a"}}}
	assert.ErrorContains(t, checkAcyclic(self), "cycle")
	loop := map[string]Step{"a": {ID: "a", DependsOn: []string{"b"}}, "b": {ID: "b", DependsOn: []string{"a"}}}
	assert.ErrorContains(t, checkAcyclic(loop), "cycle")
}

func TestIndexSteps(t *testing.T) {
	p := Plan{Steps: []Step{{ID: "a"}, {ID: "b"}}}
	steps, err := p.indexSteps()
	require.NoError(t, err)
	assert.Len(t, steps, 2)
	_, err = (&Plan{Steps: []Step{{ID: ""}}}).indexSteps()
	assert.ErrorContains(t, err, "step id is required")
	_, err = (&Plan{Steps: []Step{{ID: "a"}, {ID: "a"}}}).indexSteps()
	assert.ErrorContains(t, err, `duplicate step "a"`)
}

func TestCheckReferences(t *testing.T) {
	milestones := map[string]bool{"m": true}
	steps := map[string]Step{"a": {ID: "a"}}
	ok := Plan{Steps: []Step{{ID: "a", MilestoneID: "m"}}}
	require.NoError(t, ok.checkReferences(milestones, steps))
	badMilestone := Plan{Steps: []Step{{ID: "a", MilestoneID: "x"}}}
	assert.ErrorContains(t, badMilestone.checkReferences(milestones, steps), `unknown milestone "x"`)
	badDep := Plan{Steps: []Step{{ID: "a", MilestoneID: "m", DependsOn: []string{"z"}}}}
	assert.ErrorContains(t, badDep.checkReferences(milestones, steps), `unknown step "z"`)
}
