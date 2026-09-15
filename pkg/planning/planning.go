// Copyright 2026 Lusoris
// Package planning loads the repository's typed planning graph (praetor planning
// schema version 1, planning/plan.json) and routes its steps: it validates the
// dependency DAG, derives the ready set from a routing overlay, and ranks ready
// steps by how much downstream work each one unblocks per unit of cost.
package planning

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
)

const (
	// SchemaVersion is the praetor planning draft schema this package understands.
	SchemaVersion = 1
	// MaxPlanBytes bounds a plan file read (mirrors praetor's 512 KiB input limit).
	MaxPlanBytes = 512 * 1024
	// MaxSteps bounds the graph size (mirrors praetor's 512-step limit).
	MaxSteps = 512
)

// Plan is the subset of the praetor planning draft this package consumes.
// Fields it does not route on (sources, acceptance, actions) are ignored.
type Plan struct {
	SchemaVersion int           `json:"schema_version"`
	ID            string        `json:"id"`
	Project       Project       `json:"project"`
	Requirements  []Requirement `json:"requirements"`
	Milestones    []Milestone   `json:"milestones"`
	Steps         []Step        `json:"steps"`
}

// Project identifies the planned repository revision.
type Project struct {
	ID         string `json:"id"`
	Title      string `json:"title"`
	Repository string `json:"repository"`
	Revision   string `json:"revision"`
}

// Requirement is a cited requirement the steps satisfy.
type Requirement struct {
	ID          string `json:"id"`
	Detail      string `json:"detail"`
	Disposition string `json:"disposition"`
}

// Milestone groups steps into a verifiable outcome.
type Milestone struct {
	ID        string   `json:"id"`
	Title     string   `json:"title"`
	Outcome   string   `json:"outcome"`
	DependsOn []string `json:"depends_on"`
}

// Step is one routable unit of work.
type Step struct {
	ID             string   `json:"id"`
	Title          string   `json:"title"`
	Detail         string   `json:"detail"`
	Kind           string   `json:"kind"`
	Status         string   `json:"status"`
	RequirementIDs []string `json:"requirement_ids"`
	MilestoneID    string   `json:"milestone_id"`
	DependsOn      []string `json:"depends_on"`
}

// Load reads, decodes, and validates a plan file.
func Load(path string) (*Plan, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("planning: stat plan: %w", err)
	}
	if info.Size() > MaxPlanBytes {
		return nil, fmt.Errorf("planning: plan exceeds %d bytes", MaxPlanBytes)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("planning: read plan: %w", err)
	}
	var p Plan
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, fmt.Errorf("planning: decode plan: %w", err)
	}
	if err := p.Validate(); err != nil {
		return nil, err
	}
	return &p, nil
}

// Validate checks the schema version, identifier uniqueness, reference
// integrity, and that the step dependency graph is acyclic.
func (p *Plan) Validate() error {
	if p.SchemaVersion != SchemaVersion {
		return fmt.Errorf("planning: unsupported schema_version %d (want %d)", p.SchemaVersion, SchemaVersion)
	}
	if p.ID == "" {
		return errors.New("planning: plan id is required")
	}
	if len(p.Steps) == 0 || len(p.Steps) > MaxSteps {
		return fmt.Errorf("planning: step count %d outside 1..%d", len(p.Steps), MaxSteps)
	}
	milestones := make(map[string]bool, len(p.Milestones))
	for _, m := range p.Milestones {
		if milestones[m.ID] {
			return fmt.Errorf("planning: duplicate milestone %q", m.ID)
		}
		milestones[m.ID] = true
	}
	steps, err := p.indexSteps()
	if err != nil {
		return err
	}
	for _, s := range p.Steps {
		if !milestones[s.MilestoneID] {
			return fmt.Errorf("planning: step %q references unknown milestone %q", s.ID, s.MilestoneID)
		}
		for _, dep := range s.DependsOn {
			if _, ok := steps[dep]; !ok {
				return fmt.Errorf("planning: step %q depends on unknown step %q", s.ID, dep)
			}
		}
	}
	return checkAcyclic(steps)
}

// indexSteps maps step IDs to steps, rejecting duplicates and empty IDs.
func (p *Plan) indexSteps() (map[string]Step, error) {
	steps := make(map[string]Step, len(p.Steps))
	for _, s := range p.Steps {
		if s.ID == "" {
			return nil, errors.New("planning: step id is required")
		}
		if _, dup := steps[s.ID]; dup {
			return nil, fmt.Errorf("planning: duplicate step %q", s.ID)
		}
		steps[s.ID] = s
	}
	return steps, nil
}

// checkAcyclic runs Kahn's algorithm over the dependency edges. The loop is
// bounded by the step count, so a cycle leaves unvisited nodes behind.
func checkAcyclic(steps map[string]Step) error {
	indegree := make(map[string]int, len(steps))
	dependents := make(map[string][]string, len(steps))
	for id, s := range steps {
		indegree[id] += 0
		for _, dep := range s.DependsOn {
			indegree[id]++
			dependents[dep] = append(dependents[dep], id)
		}
	}
	queue := make([]string, 0, len(steps))
	for id, deg := range indegree {
		if deg == 0 {
			queue = append(queue, id)
		}
	}
	sort.Strings(queue)
	visited := 0
	for i := 0; i < len(queue) && i < MaxSteps; i++ {
		visited++
		for _, next := range dependents[queue[i]] {
			indegree[next]--
			if indegree[next] == 0 {
				queue = append(queue, next)
			}
		}
	}
	if visited != len(steps) {
		return errors.New("planning: step dependency graph contains a cycle")
	}
	return nil
}
