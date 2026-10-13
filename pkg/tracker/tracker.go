// Copyright 2026 Lusoris
// Package tracker provides declarative Epic, Milestone, and Project lifecycle
// management with PR metadata verification for GitHub, Gitea, and GitLab.
package tracker

import (
	"bytes"
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

// The catalogs carry a schema pointer and a version beside their list. Decoding
// refuses any other key, so a misspelled list key fails instead of reading as empty.
type epicsFile struct {
	Schema  string  `json:"$schema"`
	Version string  `json:"version"`
	Epics   *[]Epic `json:"epics"`
}

type milestonesFile struct {
	Schema     string       `json:"$schema"`
	Version    string       `json:"version"`
	Milestones *[]Milestone `json:"milestones"`
}

var (
	issueRefRegex = regexp.MustCompile(`(?i)(?:fixes|closes|resolves|relates to|ref)\s+(?:#\d+|[a-zA-Z0-9_\-\.\/]+#\d+|EPIC-\d+)`)
)

// decodeCatalog reads path and decodes it into v, refusing unknown keys and trailing data.
func decodeCatalog(kind, path string, v any) error {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return fmt.Errorf("tracker: read %s %s: %w", kind, path, err)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return fmt.Errorf("tracker: parse %s %s: %w", kind, path, err)
	}
	if dec.More() {
		return fmt.Errorf("tracker: parse %s %s: trailing data after the catalog", kind, path)
	}
	return nil
}

// LoadEpics parses an epics catalog JSON file. Every epic needs an id and a title.
func LoadEpics(path string) ([]Epic, error) {
	var f epicsFile
	if err := decodeCatalog("epics", path, &f); err != nil {
		return nil, err
	}
	if f.Epics == nil {
		return nil, fmt.Errorf("tracker: epics %s has no epics list", path)
	}
	for i, e := range *f.Epics {
		if e.ID == "" || e.Title == "" {
			return nil, fmt.Errorf("tracker: epics %s entry %d needs an id and a title", path, i)
		}
	}
	return *f.Epics, nil
}

// LoadMilestones parses a milestones catalog JSON file. Every milestone needs a
// title and a state of open or closed.
func LoadMilestones(path string) ([]Milestone, error) {
	var f milestonesFile
	if err := decodeCatalog("milestones", path, &f); err != nil {
		return nil, err
	}
	if f.Milestones == nil {
		return nil, fmt.Errorf("tracker: milestones %s has no milestones list", path)
	}
	for i, m := range *f.Milestones {
		if m.Title == "" || (m.State != "open" && m.State != "closed") {
			return nil, fmt.Errorf("tracker: milestones %s entry %d needs a title and a state of open or closed", path, i)
		}
	}
	return *f.Milestones, nil
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
