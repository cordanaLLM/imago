// Copyright 2026 Lusoris
package kernel

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestValidateArtifact(t *testing.T) {
	m := &ArtifactManifest{Stream: "6.12", Version: "6.12.1"}
	digest := strings.Repeat("a", 64)
	valid := Artifact{Name: "vmlinuz", SHA256: digest, Size: 1}
	assert.NoError(t, m.validateArtifact("artifacts[0]", valid))

	boundary := map[string]int64{"empty": 0, "largest": MaxArtifactBytes}
	for name, size := range boundary {
		a := valid
		a.Size = size
		assert.NoError(t, m.validateArtifact("artifacts[0]", a), name)
	}

	cases := map[string]struct {
		mutate func(*Artifact)
		field  string
	}{
		"path":      {func(a *Artifact) { a.Name = "../vmlinuz" }, "artifacts[0].name"},
		"checksums": {func(a *Artifact) { a.Name = ChecksumsFile }, "artifacts[0].name"},
		"bundle":    {func(a *Artifact) { a.Name = BundleFile }, "artifacts[0].name"},
		"digest":    {func(a *Artifact) { a.SHA256 = strings.Repeat("A", 64) }, "artifacts[0].sha256"},
		"negative":  {func(a *Artifact) { a.Size = -1 }, "artifacts[0].size"},
		"oversize":  {func(a *Artifact) { a.Size = MaxArtifactBytes + 1 }, "artifacts[0].size"},
	}
	for name, tc := range cases {
		a := valid
		tc.mutate(&a)
		err := m.validateArtifact("artifacts[0]", a)
		if assert.Error(t, err, name) {
			assert.Contains(t, err.Error(), tc.field, name)
		}
	}
}
