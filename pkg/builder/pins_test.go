// Copyright 2026 Lusoris
package builder_test

import (
	"path/filepath"
	"testing"

	"github.com/cordanaLLM/imago/pkg/builder"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoadPins(t *testing.T) {
	pins, err := builder.LoadPins(filepath.Join("testdata", "pins.json"))
	require.NoError(t, err)
	assert.Equal(t, "1.16.1", pins.PackerVersion)
	assert.Equal(t, "1.1.7", pins.QemuPluginVersion)
	assert.Equal(t, "28ad3bc910d916d182c5759e41939ec7b554f24535a32e44da6423a552593c52", pins.QemuPluginSHA256)
}

func TestLoadPinsRefusesInvalidManifest(t *testing.T) {
	for _, tc := range []struct{ name, file, message string }{
		{"missing key", "pins-missing.json", "sha256_"},
		{"duplicate root", "pins-duplicate.json", "duplicate JSON key"},
		{"duplicate nested", "pins-duplicate-nested.json", "duplicate JSON key"},
		{"malformed", "pins-malformed.json", "invalid JSON"},
		{"trailing document", "pins-trailing.json", "invalid JSON"},
		{"missing file", "not-present.json", "read pins"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			_, err := builder.LoadPins(filepath.Join("testdata", tc.file))
			require.ErrorContains(t, err, tc.message)
		})
	}
}
