// Copyright 2026 Lusoris
package planning

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// Cost is the coarse effort class of a step. The scale follows the fleet
// precedent in cordanaLLM/Aegis-OS planning/roadmap.json.
type Cost string

// Cost classes and their weights.
const (
	CostTrivial Cost = "trivial"
	CostSmall   Cost = "small"
	CostMedium  Cost = "medium"
	CostLarge   Cost = "large"
)

var costWeight = map[Cost]int{CostTrivial: 1, CostSmall: 2, CostMedium: 4, CostLarge: 8}

// State is the routed state of a step.
type State string

// Routed states: done steps are complete, ready steps have every dependency
// done, blocked steps wait on at least one open dependency.
const (
	StateDone    State = "done"
	StateReady   State = "ready"
	StateBlocked State = "blocked"
)

// Overlay is the routing sidecar (planning/routing.json). It carries the
// operational facts praetor's draft schema deliberately excludes: cost,
// completion, ownership, and the flags that push a step behind local work.
type Overlay struct {
	SchemaVersion int                  `json:"schema_version"`
	PlanID        string               `json:"plan_id"`
	Steps         map[string]StepRoute `json:"steps"`
}

// StepRoute is the per-step routing overlay.
type StepRoute struct {
	Cost                  Cost   `json:"cost"`
	Done                  bool   `json:"done"`
	Owner                 string `json:"owner,omitempty"`
	NeedsExternalContract bool   `json:"needs_external_contract,omitempty"`
	NeedsHardware         bool   `json:"needs_hardware,omitempty"`
	Evidence              string `json:"evidence,omitempty"`
}

// RoutedStep is one step with its derived routing facts.
type RoutedStep struct {
	Rank                  int      `json:"rank"`
	ID                    string   `json:"id"`
	Title                 string   `json:"title"`
	MilestoneID           string   `json:"milestone_id"`
	State                 State    `json:"state"`
	Cost                  Cost     `json:"cost"`
	Owner                 string   `json:"owner,omitempty"`
	BlockedBy             []string `json:"blocked_by"`
	Unblocks              []string `json:"unblocks"`
	TransitiveUnblocks    int      `json:"transitive_unblocks"`
	Score                 float64  `json:"score"`
	NeedsExternalContract bool     `json:"needs_external_contract"`
	NeedsHardware         bool     `json:"needs_hardware"`
}

// LoadOverlay reads and validates the routing sidecar for the given plan.
func LoadOverlay(path string, plan *Plan) (*Overlay, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("planning: stat routing overlay: %w", err)
	}
	if info.Size() > MaxPlanBytes {
		return nil, fmt.Errorf("planning: routing overlay exceeds %d bytes", MaxPlanBytes)
	}
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("planning: read routing overlay: %w", err)
	}
	var o Overlay
	if err := json.Unmarshal(data, &o); err != nil {
		return nil, fmt.Errorf("planning: decode routing overlay: %w", err)
	}
	if err := o.validate(plan); err != nil {
		return nil, err
	}
	return &o, nil
}

// validate requires the overlay to name the plan, cover every step, and use known costs.
func (o *Overlay) validate(plan *Plan) error {
	if o.SchemaVersion != SchemaVersion {
		return fmt.Errorf("planning: unsupported overlay schema_version %d", o.SchemaVersion)
	}
	if o.PlanID != plan.ID {
		return fmt.Errorf("planning: overlay plan_id %q does not match plan %q", o.PlanID, plan.ID)
	}
	for _, s := range plan.Steps {
		r, ok := o.Steps[s.ID]
		if !ok {
			return fmt.Errorf("planning: overlay is missing step %q", s.ID)
		}
		if _, known := costWeight[r.Cost]; !known {
			return fmt.Errorf("planning: step %q has unknown cost %q", s.ID, r.Cost)
		}
	}
	for id := range o.Steps {
		if !plan.hasStep(id) {
			return fmt.Errorf("planning: overlay names unknown step %q", id)
		}
	}
	return nil
}

func (p *Plan) hasStep(id string) bool {
	for _, s := range p.Steps {
		if s.ID == id {
			return true
		}
	}
	return false
}

// Route derives the state, unblock counts, and score of every step and returns
// them ranked: ready steps first in priority order, then blocked, then done.
func Route(plan *Plan, overlay *Overlay) ([]RoutedStep, error) {
	if plan == nil || overlay == nil {
		return nil, errors.New("planning: plan and overlay are required")
	}
	if err := overlay.validate(plan); err != nil {
		return nil, err
	}
	dependents := make(map[string][]string, len(plan.Steps))
	for _, s := range plan.Steps {
		for _, dep := range s.DependsOn {
			dependents[dep] = append(dependents[dep], s.ID)
		}
	}
	routed := make([]RoutedStep, 0, len(plan.Steps))
	for _, s := range plan.Steps {
		routed = append(routed, routeStep(s, overlay.Steps[s.ID], overlay, dependents))
	}
	sort.SliceStable(routed, func(i, j int) bool { return rankLess(routed[i], routed[j]) })
	for i := range routed {
		routed[i].Rank = i + 1
	}
	return routed, nil
}

// routeStep derives one step's routing facts from its overlay entry and the inverse edges.
func routeStep(s Step, r StepRoute, overlay *Overlay, dependents map[string][]string) RoutedStep {
	open := openDependencies(s, overlay)
	unblocks := append([]string(nil), dependents[s.ID]...)
	sort.Strings(unblocks)
	transitive := countTransitive(s.ID, dependents)
	return RoutedStep{
		ID:                    s.ID,
		Title:                 s.Title,
		MilestoneID:           s.MilestoneID,
		State:                 deriveState(r.Done, open),
		Cost:                  r.Cost,
		Owner:                 r.Owner,
		BlockedBy:             open,
		Unblocks:              unblocks,
		TransitiveUnblocks:    transitive,
		Score:                 float64(1+transitive) / float64(costWeight[r.Cost]),
		NeedsExternalContract: r.NeedsExternalContract,
		NeedsHardware:         r.NeedsHardware,
	}
}

// openDependencies lists the direct dependencies that are not yet done.
func openDependencies(s Step, overlay *Overlay) []string {
	open := make([]string, 0, len(s.DependsOn))
	for _, dep := range s.DependsOn {
		if !overlay.Steps[dep].Done {
			open = append(open, dep)
		}
	}
	sort.Strings(open)
	return open
}

func deriveState(done bool, open []string) State {
	switch {
	case done:
		return StateDone
	case len(open) == 0:
		return StateReady
	default:
		return StateBlocked
	}
}

// countTransitive counts every step reachable through dependents edges. The
// walk is bounded by MaxSteps and a visited set, so a malformed overlay cannot loop.
func countTransitive(id string, dependents map[string][]string) int {
	visited := map[string]bool{id: true}
	queue := append([]string(nil), dependents[id]...)
	count := 0
	for i := 0; i < len(queue) && i < MaxSteps; i++ {
		next := queue[i]
		if visited[next] {
			continue
		}
		visited[next] = true
		count++
		queue = append(queue, dependents[next]...)
	}
	return count
}

// stateOrder places ready work first, blocked work next, and done work last.
var stateOrder = map[State]int{StateReady: 0, StateBlocked: 1, StateDone: 2}

// rankLess is the routing policy. It follows the Aegis-OS precedent: ready
// steps first; among them, purely local work outranks anything that needs an
// unverified external contract or hardware; then the higher score
// (1 + transitive unblocks) / cost wins; ties break toward more transitive
// unblocks and finally toward the lexicographically smaller ID so the order is
// deterministic.
func rankLess(a, b RoutedStep) bool {
	if stateOrder[a.State] != stateOrder[b.State] {
		return stateOrder[a.State] < stateOrder[b.State]
	}
	aExt := a.NeedsExternalContract || a.NeedsHardware
	bExt := b.NeedsExternalContract || b.NeedsHardware
	if aExt != bExt {
		return !aExt
	}
	if a.Score != b.Score {
		return a.Score > b.Score
	}
	if a.TransitiveUnblocks != b.TransitiveUnblocks {
		return a.TransitiveUnblocks > b.TransitiveUnblocks
	}
	return a.ID < b.ID
}

// Ready filters routed steps down to the ready set, preserving rank order.
func Ready(routed []RoutedStep) []RoutedStep {
	out := make([]RoutedStep, 0, len(routed))
	for _, r := range routed {
		if r.State == StateReady {
			out = append(out, r)
		}
	}
	return out
}
