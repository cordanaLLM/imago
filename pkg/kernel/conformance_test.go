// Copyright 2026 Lusoris
package kernel_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/kernel"
)

// conformanceCorpus is testdata/aegis/conformance.json: rows built by
// tools/kernel/aegis_conformance.py, each with the verdict of the schema
// owner's decoder at the recorded Aegis-OS commit (ADR-0030).
type conformanceCorpus struct {
	AegisCommit string `json:"aegis-commit"`
	Rows        []struct {
		Name   string `json:"name"`
		Owner  string `json:"owner"`
		Reason string `json:"reason"`
		Text   string `json:"text"`
	} `json:"rows"`
}

func loadConformance(t *testing.T) conformanceCorpus {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "aegis", "conformance.json"))
	require.NoError(t, err)
	var c conformanceCorpus
	require.NoError(t, json.Unmarshal(raw, &c))
	require.Len(t, c.AegisCommit, 40, "corpus must name the full Aegis-OS commit")
	return c
}

// TestRequirementDecoderAgreesWithTheOwner replays every owner verdict: a row
// the owner accepts must decode here, and a row it refuses must be refused.
func TestRequirementDecoderAgreesWithTheOwner(t *testing.T) {
	c := loadConformance(t)
	var accepted, refused int
	for _, row := range c.Rows {
		t.Run(row.Name, func(t *testing.T) {
			_, err := kernel.ParseRequirement(strings.NewReader(row.Text))
			switch row.Owner {
			case "accepted":
				assert.NoError(t, err, "the owner at %s accepts this row", c.AegisCommit[:7])
			case "refused":
				assert.Error(t, err, "the owner at %s refuses this row: %s", c.AegisCommit[:7], row.Reason)
			default:
				t.Fatalf("unknown owner verdict %q", row.Owner)
			}
		})
		if row.Owner == "accepted" {
			accepted++
		} else {
			refused++
		}
	}
	assert.GreaterOrEqual(t, accepted, 20, "too few accepted rows to prove the decoder accepts the owner's range")
	assert.GreaterOrEqual(t, refused, 40, "too few refused rows to prove the decoder refuses what the owner refuses")
}

// TestRepositoryRequirementDecodes holds the flavor-tier ids of
// kernel/requirement.json inside the owner's rules (issue #48).
func TestRepositoryRequirementDecodes(t *testing.T) {
	q, err := kernel.LoadRequirement(filepath.Join("..", "..", "kernel", "requirement.json"))
	require.NoError(t, err)
	for _, f := range q.Features {
		assert.True(t, strings.HasPrefix(f.RequiredBy, "FLAVOR-"), "%s: required-by %q", f.Symbol, f.RequiredBy)
	}
}
