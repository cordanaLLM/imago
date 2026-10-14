// Copyright 2026 Lusoris
package kernel_test

import (
	"bytes"
	"encoding/json"
	"errors"
	"io/fs"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/kernel"
	"github.com/cordanaLLM/imago/pkg/reason"
)

const long = 5000

// requireBounded asserts the rejection text is at most reason.MaxLen bytes of
// valid UTF-8, starts with prefix, and ends in the truncation mark exactly
// when cut is set.
func requireBounded(t *testing.T, err error, prefix string, cut bool) {
	t.Helper()
	require.Error(t, err)
	text := err.Error()
	assert.LessOrEqual(t, len(text), reason.MaxLen, text)
	assert.True(t, utf8.ValidString(text), "rejection text is not valid UTF-8")
	assert.True(t, strings.HasPrefix(text, prefix), text)
	assert.Equal(t, cut, strings.HasSuffix(text, reason.TruncatedMark), text)
}

func parseSeedWith(t *testing.T, mutate func(m *kernel.ArtifactManifest)) error {
	t.Helper()
	m := seedManifest()
	mutate(m)
	raw, err := json.Marshal(m)
	require.NoError(t, err)
	_, err = kernel.ParseArtifactManifest(bytes.NewReader(raw))
	return err
}

func TestBoundaryDecodeUnknownFieldText(t *testing.T) {
	const prefix = `kernel requirement: decode: json: unknown field "`
	fits := reason.MaxLen - len(prefix) - len(`"`)
	cases := []struct {
		name  string
		field string
		cut   bool
	}{
		{"short name is reported whole", "extra", false},
		{"text of exactly the bound is reported whole", strings.Repeat("a", fits), false},
		{"text one byte above the bound is cut", strings.Repeat("a", fits+1), true},
		{"name of 5000 bytes is cut", strings.Repeat("a", long), true},
		{"cut inside a multi-byte character leaves valid text", "a" + strings.Repeat("é", long), true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := kernel.ParseRequirement(strings.NewReader(`{"` + tc.field + `":1}`))
			requireBounded(t, err, prefix, tc.cut)
			if !tc.cut {
				assert.Equal(t, prefix+tc.field+`"`, err.Error())
			}
		})
	}
}

func TestNegativeManifestUnknownFieldIsCut(t *testing.T) {
	_, err := kernel.ParseArtifactManifest(strings.NewReader(`{"` + strings.Repeat("u", long) + `":1}`))
	requireBounded(t, err, `kernel artifact: decode: json: unknown field "`, true)
}

func TestNegativeLoadOpenPathIsCut(t *testing.T) {
	segment := strings.Repeat("d", 200)
	path := filepath.Join(t.TempDir(), segment, segment, segment+".json")
	_, err := kernel.LoadRequirement(path)
	requireBounded(t, err, "kernel requirement: open ", true)
	assert.ErrorIs(t, err, fs.ErrNotExist, "the cause stays reachable")
	_, err = kernel.LoadArtifactManifest(path)
	requireBounded(t, err, "kernel artifact: open ", true)
	assert.ErrorIs(t, err, fs.ErrNotExist, "the cause stays reachable")
}

func TestNegativeInvalidCorrelationIDIsNotEchoed(t *testing.T) {
	doc := requirementDoc()
	doc["correlation-id"] = strings.Repeat("c", long)
	_, err := parseDoc(t, doc)
	requireBounded(t, err, "kernel requirement (invalid): correlation-id: must be", false)
	assert.NotContains(t, err.Error(), "ccc")
}

func TestNegativeUnknownProbeIsCut(t *testing.T) {
	doc := requirementDoc()
	doc["features"].([]any)[0].(map[string]any)["probe"] = strings.Repeat("p", long)
	_, err := parseDoc(t, doc)
	requireBounded(t, err, "kernel requirement test-kernel-requirement-0001: features[0].probe: unknown probe", true)
}

func TestNegativeInvalidStreamAndVersionAreNotEchoed(t *testing.T) {
	err := parseSeedWith(t, func(m *kernel.ArtifactManifest) { m.Stream = strings.Repeat("s", long) })
	requireBounded(t, err, "kernel artifact (invalid)@7.2.4-lusoris1: stream: must be one of", false)

	err = parseSeedWith(t, func(m *kernel.ArtifactManifest) { m.Version = strings.Repeat("v", long) })
	requireBounded(t, err, "kernel artifact mainstream@(invalid): version: must be", false)

	err = parseSeedWith(t, func(m *kernel.ArtifactManifest) { m.Stream = "" })
	requireBounded(t, err, "kernel artifact (missing)@7.2.4-lusoris1: stream: must be one of", false)
}

func TestNegativeConformEchoIsCut(t *testing.T) {
	err := seedManifest().Conform(kernel.Policy{Provider: strings.Repeat("o", long)})
	requireBounded(t, err, `kernel artifact mainstream@7.2.4-lusoris1: provider: expected "`, true)
}

func TestPositiveBoundKeepsSentinels(t *testing.T) {
	doc := requirementDoc()
	doc["features"] = []any{}
	_, err := parseDoc(t, doc)
	assert.ErrorIs(t, err, kernel.ErrEmptyRequirement)

	_, err = kernel.ParseRequirement(bytes.NewReader(bytes.Repeat([]byte(" "), int(kernel.MaxRequirementBytes)+2)))
	assert.ErrorIs(t, err, kernel.ErrTooLarge)

	dir := t.TempDir()
	m := writeRelease(t, dir)
	m.Artifacts[0].Name = strings.Repeat("n", 240)
	_, err = kernel.Verify(m, dir)
	requireBounded(t, err, "kernel artifact mainstream@7.2.4-lusoris1: artifacts[", true)
	assert.True(t, errors.Is(err, kernel.ErrChecksumEntry) || errors.Is(err, kernel.ErrMissingArtifact), err)
}
