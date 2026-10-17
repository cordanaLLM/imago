// Copyright 2026 Lusoris
package kernel_test

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/cordanaLLM/imago/pkg/kernel"
	"github.com/cordanaLLM/imago/pkg/reason"
)

// FuzzParseRequirement feeds arbitrary bytes to the requirement parser. The
// seed corpus is the two vendored Aegis payloads plus one input per early
// rejection path; the seeds run as ordinary cases in every `go test`.
func FuzzParseRequirement(f *testing.F) {
	for _, name := range []string{"kernel-requirement.json", "kernel-requirement.reference.json"} {
		data, err := os.ReadFile(filepath.Join("testdata", "aegis", name))
		if err != nil {
			f.Fatal(err)
		}
		f.Add(data)
	}
	f.Add([]byte(`{"schema":"aegis.p01-nucleus.kernel-requirement.v1","features":[]}`))
	f.Add([]byte(`{"unknown":1}`))
	f.Add([]byte(`{"` + strings.Repeat("u", 2*reason.MaxLen) + `":1}`))
	f.Add([]byte(`{"schema":"aegis.p01-nucleus.kernel-requirement.v1","correlation-id":"` + strings.Repeat("c", 2*reason.MaxLen) + `"}`))
	f.Add([]byte(`{} {}`))
	f.Add([]byte{})
	f.Fuzz(func(t *testing.T, data []byte) {
		q, err := kernel.ParseRequirement(bytes.NewReader(data))
		if err != nil {
			requireBoundedText(t, err)
			if q != nil {
				t.Fatalf("a rejected requirement returned a value: %+v", q)
			}
			return
		}
		if err := q.Validate(); err != nil {
			t.Fatalf("the parser accepted a requirement that Validate rejects: %v", err)
		}
		again, err := kernel.ParseRequirement(bytes.NewReader(encode(t, q)))
		if err != nil {
			t.Fatalf("the encoding of an accepted requirement is rejected: %v", err)
		}
		if !reflect.DeepEqual(q, again) {
			t.Fatalf("round trip changed the requirement:\n first %+v\nsecond %+v", q, again)
		}
	})
}

// FuzzParseArtifactManifest feeds arbitrary bytes to the manifest parser. The
// valid seed is the manifest of the release the verification tests lay out.
func FuzzParseArtifactManifest(f *testing.F) {
	valid, err := json.Marshal(seedManifest())
	if err != nil {
		f.Fatal(err)
	}
	f.Add(valid)
	f.Add([]byte(`{"schema":"imago.nucleus.kernel-artifact.v1","artifacts":[]}`))
	f.Add([]byte(`{"unknown":1}`))
	f.Add([]byte(`{"` + strings.Repeat("u", 2*reason.MaxLen) + `":1}`))
	f.Add([]byte(`{"schema":"imago.nucleus.kernel-artifact.v1","provider":"a/b","stream":"` + strings.Repeat("s", 2*reason.MaxLen) + `"}`))
	f.Add([]byte(`{} {}`))
	f.Add([]byte{})
	f.Fuzz(func(t *testing.T, data []byte) {
		m, err := kernel.ParseArtifactManifest(bytes.NewReader(data))
		if err != nil {
			requireBoundedText(t, err)
			if m != nil {
				t.Fatalf("a rejected manifest returned a value: %+v", m)
			}
			return
		}
		if err := m.Validate(); err != nil {
			t.Fatalf("the parser accepted a manifest that Validate rejects: %v", err)
		}
		again, err := kernel.ParseArtifactManifest(bytes.NewReader(encode(t, m)))
		if err != nil {
			t.Fatalf("the encoding of an accepted manifest is rejected: %v", err)
		}
		if !reflect.DeepEqual(m, again) {
			t.Fatalf("round trip changed the manifest:\n first %+v\nsecond %+v", m, again)
		}
	})
}

// requireBoundedText fails when a rejection's text exceeds the reason bound
// (ADR-0028): no input may make the reported text arbitrarily long.
func requireBoundedText(t *testing.T, err error) {
	t.Helper()
	if n := len(err.Error()); n > reason.MaxLen {
		t.Fatalf("rejection text is %d bytes, bound %d", n, reason.MaxLen)
	}
}

// encode marshals an accepted document; a value the parser returned must encode.
func encode(t *testing.T, v any) []byte {
	t.Helper()
	data, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("an accepted document does not encode: %v", err)
	}
	return data
}

// seedManifest is a valid manifest with one artifact, built without touching the disk.
func seedManifest() *kernel.ArtifactManifest {
	config := []byte("CONFIG_KVM=m\n")
	sums := []byte(sha256Hex(config) + "  kernel-mainstream.config\n")
	return &kernel.ArtifactManifest{
		Schema:    kernel.ArtifactSchema,
		Provider:  testProvider,
		Stream:    "mainstream",
		Version:   "7.2.4-lusoris1",
		Kernel:    kernel.KernelInfo{Release: "7.2.4-lusoris1", ConfigDigest: "sha256:" + sha256Hex(config)},
		Artifacts: []kernel.Artifact{{Name: "kernel-mainstream.config", SHA256: sha256Hex(config), Size: int64(len(config))}},
		Checksums: kernel.Checksums{File: kernel.ChecksumsFile, SHA256: sha256Hex(sums)},
		Provenance: kernel.Provenance{
			Repository:     testProvider,
			Tag:            "v7.2.4-lusoris1",
			Revision:       testRevision,
			Bundle:         kernel.BundleFile,
			SignerIdentity: "https://github.com/cordanaLLM/nucleus/.github/workflows/publish-release.yml@refs/tags/v7.2.4-lusoris1",
		},
	}
}
