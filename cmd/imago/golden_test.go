// Copyright 2026 Lusoris
package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// The golden transcripts pin the human-readable output byte for byte: a Contains check
// passes while a column shifts, a header goes missing or a separator turns into NUL bytes.
// After an intended output change, rewrite them with
//
//	go test ./cmd/imago -run TestGoldenTranscripts -update
//
// and review the diff; TestGoldenFilesArePrintable refuses a rewrite that blesses
// unprintable output.
var update = flag.Bool("update", false, "rewrite the golden transcripts under testdata/golden")

const goldenDir = "testdata/golden"

var goldenCases = []struct {
	name string
	args []string
}{
	{"root-help", []string{"--help"}},
	{"build-help", []string{"build", "--help"}},
	{"flavors-list", []string{"flavors", "list"}},
	{"standards-list", []string{"standards", "list"}},
	{"epics-list", []string{"epics", "list", "--path", filepath.Join(goldenDir, "epics.json")}},
	{"milestones-list", []string{"milestones", "list", "--path", filepath.Join(goldenDir, "milestones.json")}},
}

func TestGoldenTranscripts(t *testing.T) {
	for _, tc := range goldenCases {
		t.Run(tc.name, func(t *testing.T) {
			out, err := executeCommand(tc.args...)
			require.NoError(t, err)
			path := filepath.Join(goldenDir, tc.name+".txt")
			if *update {
				require.NoError(t, os.WriteFile(path, []byte(out), 0o644))
			}
			want, err := os.ReadFile(path)
			require.NoError(t, err, "golden transcript missing; run with -update to create it")
			assert.Equal(t, string(want), out,
				"output of imago %s differs from %s; after an intended change run with -update and review the diff",
				strings.Join(tc.args, " "), path)
		})
	}
}

// Every case has its golden file and every golden file has its case, so a renamed case
// cannot leave a stale transcript behind that nothing compares any more.
func TestGoldenFilesMatchCases(t *testing.T) {
	want := map[string]bool{}
	for _, tc := range goldenCases {
		want[tc.name+".txt"] = true
	}
	files, err := filepath.Glob(filepath.Join(goldenDir, "*.txt"))
	require.NoError(t, err)
	got := map[string]bool{}
	for _, f := range files {
		got[filepath.Base(f)] = true
	}
	assert.Equal(t, want, got)
}

func TestGoldenFilesArePrintable(t *testing.T) {
	files, err := filepath.Glob(filepath.Join(goldenDir, "*.txt"))
	require.NoError(t, err)
	require.NotEmpty(t, files)
	for _, f := range files {
		data, err := os.ReadFile(f)
		require.NoError(t, err)
		assert.True(t, utf8.Valid(data), "%s is not valid UTF-8", f)
		assert.True(t, strings.HasSuffix(string(data), "\n"), "%s does not end with a newline", f)
		for i, r := range string(data) {
			if r != '\n' && (r < 0x20 || r == 0x7f) {
				t.Errorf("%s holds control character %U at byte %d", f, r, i)
				break
			}
		}
	}
}
