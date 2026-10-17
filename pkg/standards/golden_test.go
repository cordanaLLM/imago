// Copyright 2026 Lusoris
package standards_test

import (
	"encoding/json"
	"flag"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/standards"
)

// The golden file pins the standard of every flavor field by field, so a split of
// the tier rules cannot move a package, unit or kernel parameter unnoticed. After an
// intended change, rewrite it with
//
//	go test ./pkg/standards -run TestAllStandardsGolden -update
//
// and review the diff.
var update = flag.Bool("update", false, "rewrite testdata/standards.golden.json")

func TestAllStandardsGolden(t *testing.T) {
	got, err := json.MarshalIndent(standards.All(), "", "  ")
	require.NoError(t, err)
	got = append(got, '\n')
	path := filepath.Join("testdata", "standards.golden.json")
	if *update {
		require.NoError(t, os.MkdirAll("testdata", 0o750))
		require.NoError(t, os.WriteFile(path, got, 0o600))
	}
	want, err := os.ReadFile(path)
	require.NoError(t, err, "golden file missing; run with -update to create it")
	require.Equal(t, string(want), string(got))
}
