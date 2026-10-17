// Copyright 2026 Lusoris
package imageless_test

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/flavors"
	"github.com/cordanaLLM/imago/pkg/imageless"
)

// The golden file pins the apply script of every flavor in all three modes (full,
// skip-cleanup, dry run) byte for byte. After an intended change, rewrite it with
//
//	go test ./pkg/imageless -run TestApplyScriptsGolden -update
//
// and review the diff.
var update = flag.Bool("update", false, "rewrite testdata/apply-scripts.golden.txt")

func TestApplyScriptsGolden(t *testing.T) {
	modes := []struct {
		name string
		opts imageless.ApplyOptions
	}{
		{"full", imageless.ApplyOptions{}},
		{"skip-cleanup", imageless.ApplyOptions{SkipCleanup: true}},
		{"dry-run", imageless.ApplyOptions{DryRun: true}},
	}
	var sb strings.Builder
	for _, fl := range flavors.All() {
		for _, m := range modes {
			opts := m.opts
			opts.FlavorID = fl.ID
			script, err := imageless.GenerateApplyScript(opts)
			require.NoError(t, err)
			sb.WriteString("=== " + fl.ID + " " + m.name + "\n" + script)
		}
	}
	path := filepath.Join("testdata", "apply-scripts.golden.txt")
	if *update {
		require.NoError(t, os.MkdirAll("testdata", 0o750))
		require.NoError(t, os.WriteFile(path, []byte(sb.String()), 0o600))
	}
	want, err := os.ReadFile(path)
	require.NoError(t, err, "golden file missing; run with -update to create it")
	require.Equal(t, string(want), sb.String())
}
