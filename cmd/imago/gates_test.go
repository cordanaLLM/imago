// Copyright 2026 Lusoris
package main

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/planning"
)

// Tests for the repository gate commands: lint, audit, plan validate and plan route.
// Each command runs once on a good input, once per planted defect it must refuse,
// and once on the edge of what it accepts.

const lintPassed = "All internal linter checks passed."

func repoRoot(t *testing.T) string {
	t.Helper()
	root, err := filepath.Abs("../..")
	require.NoError(t, err)
	return root
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o750))
	require.NoError(t, os.WriteFile(path, []byte(content), 0o600))
}

// lintTree copies the three files lint reads into a temporary directory and enters it.
func lintTree(t *testing.T) string {
	t.Helper()
	root, dir := repoRoot(t), t.TempDir()
	for _, name := range []string{"versions.json", ".github/epics.json", ".github/milestones.json"} {
		data, err := os.ReadFile(filepath.Join(root, name))
		require.NoError(t, err)
		writeFile(t, filepath.Join(dir, name), string(data))
	}
	t.Chdir(dir)
	return dir
}

func TestLintPassesOnRepository(t *testing.T) {
	t.Chdir(repoRoot(t))
	out, err := executeCommand("lint")
	require.NoError(t, err)
	assert.Contains(t, out, lintPassed)
}

func TestLintRefusesPlantedDefects(t *testing.T) {
	cases := []struct {
		name, file, content, want string
	}{
		{"manifest-malformed", "versions.json", "{", "manifest lint failed"},
		{"manifest-missing", "versions.json", "", "manifest lint failed"},
		{"epics-misspelled-list", ".github/epics.json", `{"epic": []}`, "epics lint failed"},
		{"epics-no-list", ".github/epics.json", `{}`, "epics lint failed"},
		{"epic-without-id", ".github/epics.json", `{"epics": [{"title": "no id"}]}`, "epics lint failed"},
		{"epics-extra-key", ".github/epics.json", `{"epics": [], "epicz": []}`, "epics lint failed"},
		{"epic-unknown-field", ".github/epics.json", `{"epics": [{"id": "E", "title": "t", "statuss": "x"}]}`, "epics lint failed"}, // codespell:ignore statuss
		{"epics-trailing-data", ".github/epics.json", `{"epics": []} {}`, "epics lint failed"},
		{"epics-missing", ".github/epics.json", "", "epics lint failed"},
		{"milestone-unknown-state", ".github/milestones.json", `{"milestones": [{"title": "x", "state": "draft"}]}`, "milestones lint failed"},
		{"milestone-without-title", ".github/milestones.json", `{"milestones": [{"state": "open"}]}`, "milestones lint failed"},
		{"milestones-missing", ".github/milestones.json", "", "milestones lint failed"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			path := filepath.Join(lintTree(t), tc.file)
			if tc.content == "" {
				require.NoError(t, os.Remove(path))
			} else {
				writeFile(t, path, tc.content)
			}
			out, err := executeCommand("lint")
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.want)
			assert.NotContains(t, out, lintPassed)
		})
	}
}

func TestLintAcceptsExplicitlyEmptyCatalogs(t *testing.T) {
	dir := lintTree(t)
	writeFile(t, filepath.Join(dir, ".github/epics.json"), `{"$schema": "s", "version": "1", "epics": []}`)
	writeFile(t, filepath.Join(dir, ".github/milestones.json"), `{"milestones": [{"title": "x", "state": "closed", "due_on": null}]}`)
	out, err := executeCommand("lint")
	require.NoError(t, err)
	assert.Contains(t, out, lintPassed)
}

// auditTree writes a stand-in audit script into a temporary directory and enters it.
func auditTree(t *testing.T, script string) {
	t.Helper()
	dir := t.TempDir()
	if script != "" {
		writeFile(t, filepath.Join(dir, "scripts", "audit-repository-health.sh"), script)
	}
	t.Chdir(dir)
}

func TestAuditRunsTheRepositoryScript(t *testing.T) {
	auditTree(t, "echo audit-ran\n")
	out, err := executeCommand("audit")
	require.NoError(t, err)
	assert.Contains(t, out, "audit-ran")
}

func TestAuditRefusesMissingScript(t *testing.T) {
	auditTree(t, "")
	_, err := executeCommand("audit")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "audit script scripts/audit-repository-health.sh not found")
}

func TestAuditFailsWhenTheScriptFails(t *testing.T) {
	auditTree(t, "echo planted-finding >&2\nexit 3\n")
	out, err := executeCommand("audit")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "exit status 3")
	assert.Contains(t, out, "planted-finding")
}

// The script's own children hold its output open; the deadline must end the run anyway.
func TestAuditStopsAtTheDeadline(t *testing.T) {
	auditTree(t, "sleep 60\necho never\n")
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()
	cmd := newRootCmd()
	cmd.SetOut(new(strings.Builder))
	cmd.SetErr(new(strings.Builder))
	cmd.SetArgs([]string{"audit"})
	start := time.Now()
	err := cmd.ExecuteContext(ctx)
	require.Error(t, err)
	assert.Less(t, time.Since(start), auditWaitDelay+10*time.Second)
}

func planFixture() (planning.Plan, planning.Overlay) {
	plan := planning.Plan{
		SchemaVersion: planning.SchemaVersion,
		ID:            "plan-cli-test",
		Milestones:    []planning.Milestone{{ID: "m1", Title: "M1", DependsOn: []string{}}},
		Steps: []planning.Step{
			{ID: "s-root", Title: "Root", MilestoneID: "m1", DependsOn: []string{}},
			{ID: "s-mid", Title: "Mid", MilestoneID: "m1", DependsOn: []string{"s-root"}},
			{ID: "s-leaf", Title: "Leaf", MilestoneID: "m1", DependsOn: []string{"s-mid"}},
		},
	}
	overlay := planning.Overlay{
		SchemaVersion: 1,
		PlanID:        plan.ID,
		Steps: map[string]planning.StepRoute{
			"s-root": {Cost: planning.CostSmall, Done: true},
			"s-mid":  {Cost: planning.CostSmall},
			"s-leaf": {Cost: planning.CostTrivial},
		},
	}
	return plan, overlay
}

// planArgs writes the fixture, changed by mutate, and returns the flags that point at it.
func planArgs(t *testing.T, mutate func(*planning.Plan, *planning.Overlay)) []string {
	t.Helper()
	plan, overlay := planFixture()
	if mutate != nil {
		mutate(&plan, &overlay)
	}
	dir := t.TempDir()
	paths := []string{filepath.Join(dir, "plan.json"), filepath.Join(dir, "routing.json")}
	for i, v := range []any{plan, overlay} {
		data, err := json.Marshal(v)
		require.NoError(t, err)
		writeFile(t, paths[i], string(data))
	}
	return []string{"--plan", paths[0], "--routing", paths[1]}
}

func TestPlanValidateRepositoryDefaults(t *testing.T) {
	t.Chdir(repoRoot(t))
	out, err := executeCommand("plan", "validate")
	require.NoError(t, err)
	assert.Contains(t, out, "✓ Plan plan-imago-fleet-migration")
}

func TestPlanValidateFixture(t *testing.T) {
	out, err := executeCommand(append([]string{"plan", "validate"}, planArgs(t, nil)...)...)
	require.NoError(t, err)
	assert.Contains(t, out, "✓ Plan plan-cli-test (3 steps, 1 milestones)")
}

func TestPlanValidateRefusesPlantedDefects(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(*planning.Plan, *planning.Overlay)
		want   string
	}{
		{"unknown-dependency", func(p *planning.Plan, _ *planning.Overlay) { p.Steps[2].DependsOn = []string{"s-ghost"} }, "depends on unknown step"},
		{"cycle", func(p *planning.Plan, _ *planning.Overlay) { p.Steps[0].DependsOn = []string{"s-leaf"} }, "contains a cycle"},
		{"overlay-other-plan", func(_ *planning.Plan, o *planning.Overlay) { o.PlanID = "plan-other" }, "does not match plan"},
		{"overlay-missing-step", func(_ *planning.Plan, o *planning.Overlay) { delete(o.Steps, "s-leaf") }, "overlay is missing step"},
		{"overlay-unknown-cost", func(_ *planning.Plan, o *planning.Overlay) { o.Steps["s-leaf"] = planning.StepRoute{Cost: "huge"} }, "unknown cost"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			for _, sub := range []string{"validate", "route"} {
				_, err := executeCommand(append([]string{"plan", sub}, planArgs(t, tc.mutate)...)...)
				require.Error(t, err, sub)
				assert.Contains(t, err.Error(), tc.want, sub)
			}
		})
	}
}

func TestPlanRefusesMissingFiles(t *testing.T) {
	dir := t.TempDir()
	args := planArgs(t, nil)
	_, err := executeCommand("plan", "validate", "--plan", filepath.Join(dir, "absent.json"), "--routing", args[3])
	require.Error(t, err)
	assert.Contains(t, err.Error(), "stat plan")
	_, err = executeCommand("plan", "route", "--plan", args[1], "--routing", filepath.Join(dir, "absent.json"))
	require.Error(t, err)
	assert.Contains(t, err.Error(), "stat routing overlay")
}

func TestPlanRouteTable(t *testing.T) {
	out, err := executeCommand(append([]string{"plan", "route"}, planArgs(t, nil)...)...)
	require.NoError(t, err)
	lines := strings.Split(strings.TrimSpace(out), "\n")
	require.Len(t, lines, 4)
	assert.Contains(t, lines[0], "RANK")
	assert.Regexp(t, `^1\s+ready\s.*s-mid`, lines[1])
	assert.Regexp(t, `^2\s+blocked\s.*s-leaf\s+s-mid$`, lines[2])
}

func TestPlanRouteReadyJSON(t *testing.T) {
	out, err := executeCommand(append([]string{"plan", "route", "--json", "--ready"}, planArgs(t, nil)...)...)
	require.NoError(t, err)
	var routed []planning.RoutedStep
	require.NoError(t, json.Unmarshal([]byte(out), &routed))
	require.Len(t, routed, 1)
	assert.Equal(t, "s-mid", routed[0].ID)
	assert.Equal(t, planning.StateReady, routed[0].State)
}

// With every step done the ready set is an empty JSON list, never null.
func TestPlanRouteReadyJSONWhenAllDone(t *testing.T) {
	args := planArgs(t, func(_ *planning.Plan, o *planning.Overlay) {
		for id, r := range o.Steps {
			r.Done = true
			o.Steps[id] = r
		}
	})
	out, err := executeCommand(append([]string{"plan", "route", "--json", "--ready"}, args...)...)
	require.NoError(t, err)
	assert.Equal(t, "[]", strings.TrimSpace(out))
}
