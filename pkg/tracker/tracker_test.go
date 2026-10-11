// Copyright 2026 Lusoris
package tracker_test

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/tracker"
)

func TestLoadActualEpics(t *testing.T) {
	epicsPath, err := filepath.Abs("../../.github/epics.json")
	require.NoError(t, err)

	epics, err := tracker.LoadEpics(epicsPath)
	require.NoError(t, err)
	assert.NotEmpty(t, epics)

	for _, e := range epics {
		assert.NotEmpty(t, e.ID)
		assert.NotEmpty(t, e.Title)
		assert.NotEmpty(t, e.Cadence)
		assert.Equal(t, "active", e.Status)
		assert.NotEmpty(t, e.RequiredLabels)
	}
}

func TestLoadActualMilestones(t *testing.T) {
	msPath, err := filepath.Abs("../../.github/milestones.json")
	require.NoError(t, err)

	milestones, err := tracker.LoadMilestones(msPath)
	require.NoError(t, err)
	require.NotEmpty(t, milestones)

	// The file copies the forge milestones, so it carries closed ones and
	// milestones without a due date. A pull request needs an open one.
	open := 0
	titles := make(map[string]bool, len(milestones))
	for _, m := range milestones {
		assert.NotEmpty(t, m.Title)
		assert.Falsef(t, titles[m.Title], "milestone %q is listed twice", m.Title)
		titles[m.Title] = true
		assert.Containsf(t, []string{"open", "closed"}, m.State, "milestone %q has an unknown state", m.Title)
		if m.State == "open" {
			open++
		}
		if m.DueOn != "" {
			_, err := time.Parse(time.RFC3339, m.DueOn)
			assert.NoErrorf(t, err, "milestone %q has a due date that is not RFC 3339", m.Title)
		}
	}
	assert.Positive(t, open, "no open milestone: no pull request could pass the milestone gate")
}

func TestValidatePRMetadata(t *testing.T) {
	validMilestones := []tracker.Milestone{
		{Title: "v2026.04.0", State: "open"},
		{Title: "v2026.03.0", State: "closed"},
	}

	// Valid PR
	validMeta := tracker.PRMetadata{
		Title:     "feat(base): add hyper-v integration daemons",
		Body:      "This PR adds hyperv daemons.\nFixes #42",
		Labels:    []string{"tier/base", "area/hardware"},
		Milestone: "v2026.04.0",
	}
	err := tracker.ValidatePRMetadata(validMeta, validMilestones)
	assert.NoError(t, err)

	// Missing milestone
	noMsMeta := validMeta
	noMsMeta.Milestone = ""
	assert.ErrorContains(t, tracker.ValidatePRMetadata(noMsMeta, validMilestones), "milestone is missing")

	// Closed milestone
	closedMsMeta := validMeta
	closedMsMeta.Milestone = "v2026.03.0"
	assert.ErrorContains(t, tracker.ValidatePRMetadata(closedMsMeta, validMilestones), "is closed")

	// Missing issue reference
	noIssueMeta := validMeta
	noIssueMeta.Body = "Just some changes with no issue link"
	assert.ErrorContains(t, tracker.ValidatePRMetadata(noIssueMeta, validMilestones), "reference a tracked issue")

	// Unknown milestone
	unknownMsMeta := validMeta
	unknownMsMeta.Milestone = "v9999.01.0"
	assert.ErrorContains(t, tracker.ValidatePRMetadata(unknownMsMeta, validMilestones), "unknown milestone")

	// Empty labels slice
	emptyLabelsMeta := validMeta
	emptyLabelsMeta.Labels = []string{}
	assert.ErrorContains(t, tracker.ValidatePRMetadata(emptyLabelsMeta, validMilestones), "at least one")
}

func TestLoadInvalidTrackerFiles(t *testing.T) {
	_, err := tracker.LoadEpics("non-existent.json")
	assert.Error(t, err)

	_, err = tracker.LoadMilestones("non-existent.json")
	assert.Error(t, err)
}
