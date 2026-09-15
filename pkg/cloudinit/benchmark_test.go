// Copyright 2026 Lusoris
package cloudinit_test

import (
	"testing"

	"github.com/cordanaLLM/imago/pkg/cloudinit"
)

func BenchmarkGenerateUserData(b *testing.B) {
	cfg := cloudinit.DefaultConfig("base-generic")
	cfg.SSHAuthorizedKeys = []string{"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGenericKeyForTestingOnly"}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := cloudinit.GenerateUserData(cfg)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkGenerateUserDataWithPlatform(b *testing.B) {
	cfg := cloudinit.DefaultConfig("ai-infer-nvidia")
	cfg.Platform = "truenas"
	cfg.SSHAuthorizedKeys = []string{
		"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGenericKeyForTestingOnly",
		"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAnotherKeyForBenchmarking",
	}
	cfg.ExtraPackages = []string{"curl", "htop", "nvtop"}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := cloudinit.GenerateUserData(cfg)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkGenerateMetaData(b *testing.B) {
	cfg := cloudinit.DefaultConfig("k8s-node-cilium")
	cfg.Hostname = "worker-node-04"

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := cloudinit.GenerateMetaData(cfg)
		if err != nil {
			b.Fatal(err)
		}
	}
}
