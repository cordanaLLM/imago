// Copyright 2026 Lusoris
package manifest_test

import (
	"path/filepath"
	"testing"

	"github.com/cordanaLLM/imago/pkg/manifest"
)

func BenchmarkLoadActualVersionsJSON(b *testing.B) {
	rootPath, err := filepath.Abs("../../versions.json")
	if err != nil {
		b.Fatalf("failed to resolve versions.json path: %v", err)
	}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		_, err := manifest.Load(rootPath)
		if err != nil {
			b.Fatalf("load failed: %v", err)
		}
	}
}

func BenchmarkValidateManifest(b *testing.B) {
	m := validTestManifest()

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		if err := m.Validate(); err != nil {
			b.Fatalf("validation failed: %v", err)
		}
	}
}
