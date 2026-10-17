// Copyright 2026 Lusoris
package kernel_test

import (
	"bytes"
	"encoding/json"
	"io"
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
	for _, name := range []string{"aegis-kernel-requirement.json", "aegis-kernel-requirement.reference.json"} {
		data, err := os.ReadFile(filepath.Join("testdata", name))
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
		checkParse(t, "requirement", kernel.ParseRequirement, data)
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
		checkParse(t, "manifest", kernel.ParseArtifactManifest, data)
	})
}

// checkParse holds every fuzz input to one contract: a rejection carries a
// bounded text and no value; an accepted document passes Validate and
// survives an encode and parse round trip unchanged.
func checkParse[T any, P interface {
	*T
	Validate() error
}](t *testing.T, kind string, parse func(io.Reader) (P, error), data []byte) {
	t.Helper()
	v, err := parse(bytes.NewReader(data))
	if err != nil {
		requireBoundedText(t, err)
		if v != nil {
			t.Fatalf("a rejected %s returned a value: %+v", kind, v)
		}
		return
	}
	if err := v.Validate(); err != nil {
		t.Fatalf("the parser accepted a %s that Validate rejects: %v", kind, err)
	}
	again, err := parse(bytes.NewReader(encode(t, v)))
	if err != nil {
		t.Fatalf("the encoding of an accepted %s is rejected: %v", kind, err)
	}
	if !reflect.DeepEqual(v, again) {
		t.Fatalf("round trip changed the %s:\n first %+v\nsecond %+v", kind, v, again)
	}
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
