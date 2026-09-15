// Copyright 2026 Lusoris
package tracker_test

import (
	"path/filepath"
	"testing"

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
	assert.NotEmpty(t, milestones)

	for _, m := range milestones {
		assert.NotEmpty(t, m.Title)
		assert.Equal(t, "open", m.State)
		assert.NotEmpty(t, m.DueOn)
	}
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
