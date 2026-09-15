// Copyright 2026 Lusoris
// Package tracker provides declarative Epic, Milestone, and Project lifecycle
// management with PR metadata verification for GitHub, Gitea, and GitLab.
package tracker

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Epic describes a tracked high-level architectural or operational initiative.
type Epic struct {
	ID             string   `json:"id"`
	Title          string   `json:"title"`
	Cadence        string   `json:"cadence"`
	Status         string   `json:"status"`
	RequiredLabels []string `json:"required_labels"`
	Description    string   `json:"description"`
}

// Milestone describes a release target window.
type Milestone struct {
	Title       string `json:"title"`
	State       string `json:"state"`
	DueOn       string `json:"due_on"`
	Description string `json:"description"`
}

type epicsFile struct {
	Epics []Epic `json:"epics"`
}

type milestonesFile struct {
	Milestones []Milestone `json:"milestones"`
}

var (
	issueRefRegex = regexp.MustCompile(`(?i)(?:fixes|closes|resolves|relates to|ref)\s+(?:#\d+|[a-zA-Z0-9_\-\.\/]+#\d+|EPIC-\d+)`)
)

// LoadEpics parses an epics catalog JSON file.
func LoadEpics(path string) ([]Epic, error) {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("tracker: read epics %s: %w", path, err)
	}
	var f epicsFile
	if err := json.Unmarshal(data, &f); err != nil {
		return nil, fmt.Errorf("tracker: parse epics %s: %w", path, err)
	}
	return f.Epics, nil
}

// LoadMilestones parses a milestones catalog JSON file.
func LoadMilestones(path string) ([]Milestone, error) {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("tracker: read milestones %s: %w", path, err)
	}
	var f milestonesFile
	if err := json.Unmarshal(data, &f); err != nil {
		return nil, fmt.Errorf("tracker: parse milestones %s: %w", path, err)
	}
	return f.Milestones, nil
}

// PRMetadata encapsulates the fields required for the PR hard gate.
type PRMetadata struct {
	Title     string
	Body      string
	Labels    []string
	Milestone string
}

// ValidatePRMetadata enforces hard gates on PR descriptions, milestones, and labels.
func ValidatePRMetadata(meta PRMetadata, validMilestones []Milestone) error {
	if err := validateMilestone(meta.Milestone, validMilestones); err != nil {
		return err
	}
	if err := validateIssueReference(meta.Title, meta.Body); err != nil {
		return err
	}
	return validateLabels(meta.Labels)
}

func validateMilestone(milestone string, valid []Milestone) error {
	if strings.TrimSpace(milestone) == "" {
		return fmt.Errorf("pr hard gate: milestone is missing; PR must be assigned to an active milestone")
	}
	for _, m := range valid {
		if strings.EqualFold(m.Title, milestone) {
			if m.State != "open" {
				return fmt.Errorf("pr hard gate: milestone %q is closed", milestone)
			}
			return nil
		}
	}
	return fmt.Errorf("pr hard gate: unknown milestone %q", milestone)
}

func validateIssueReference(title, body string) error {
	combined := title + "\n" + body
	if !issueRefRegex.MatchString(combined) {
		return fmt.Errorf("pr hard gate: PR description must reference a tracked issue or epic (e.g. 'Fixes #123' or 'Relates to EPIC-01')")
	}
	return nil
}

func validateLabels(labels []string) error {
	if len(labels) == 0 {
		return fmt.Errorf("pr hard gate: PR must have at least one 'tier/*' or 'area/*' label")
	}
	for _, l := range labels {
		if strings.HasPrefix(l, "tier/") || strings.HasPrefix(l, "area/") {
			return nil
		}
	}
	return fmt.Errorf("pr hard gate: PR lacks required 'tier/*' or 'area/*' label (found: %s)", strings.Join(labels, ", "))
}
