// Copyright 2026 Lusoris
package flavors_test

import (
	"testing"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

func BenchmarkGet(b *testing.B) {
	target := "ai-infer-nvidia"
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := flavors.Get(target)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkGetNonExistent(b *testing.B) {
	target := "nonexistent-flavor"
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, _ = flavors.Get(target)
	}
}

func BenchmarkFilterByTier(b *testing.B) {
	tier := "kubernetes"
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		res := flavors.FilterByTier(tier)
		if len(res) == 0 {
			b.Fatal("expected flavors in tier")
		}
	}
}

func BenchmarkSearch(b *testing.B) {
	query := "nvidia"
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		res := flavors.Search(query)
		if len(res) == 0 {
			b.Fatal("expected search results")
		}
	}
}

func BenchmarkAll(b *testing.B) {
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		res := flavors.All()
		if len(res) != 44 {
			b.Fatalf("expected 44 flavors, got %d", len(res))
		}
	}
}
