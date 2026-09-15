// Copyright 2026 Lusoris
package mcp_test

import (
	"fmt"
	"testing"
	"time"

	"github.com/golusoris/golusoris/core/clock"

	"github.com/cordanaLLM/imago/pkg/mcp"
)

func BenchmarkStagerStage(b *testing.B) {
	stager := mcp.NewStager(clock.NewFake())
	payload := map[string]any{"flavor": "base-generic", "backend": "local"}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = stager.Stage("trigger_build", "base-generic", payload, "Build local base-generic")
	}
}

func BenchmarkStagerGet(b *testing.B) {
	stager := mcp.NewStager(clock.NewFake())
	payload := map[string]any{"flavor": "base-generic", "backend": "local"}
	act := stager.Stage("trigger_build", "base-generic", payload, "Build local base-generic")

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := stager.Get(act.ID)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkStagerList(b *testing.B) {
	stager := mcp.NewStager(clock.NewFake())
	payload := map[string]any{"flavor": "base-generic"}
	for i := 0; i < 50; i++ {
		stager.Stage("tool", fmt.Sprintf("target-%d", i), payload, "preview")
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = stager.List()
	}
}

func BenchmarkStagerPrune(b *testing.B) {
	stager := mcp.NewStager(clock.NewFake())
	payload := map[string]any{"flavor": "base-generic"}
	for i := 0; i < 100; i++ {
		stager.Stage("tool", fmt.Sprintf("target-%d", i), payload, "preview")
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = stager.Prune(1 * time.Hour)
	}
}

func BenchmarkStagerConcurrentParallel(b *testing.B) {
	stager := mcp.NewStager(clock.NewFake())
	payload := map[string]any{"flavor": "k8s-node-cilium"}
	act := stager.Stage("build", "k8s-node-cilium", payload, "Build")

	b.ResetTimer()
	b.ReportAllocs()

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_, _ = stager.Get(act.ID)
		}
	})
}
