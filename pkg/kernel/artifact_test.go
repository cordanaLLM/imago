// Copyright 2026 Lusoris
package kernel_test

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/kernel"
)

const (
	testProvider = "cordanaLLM/nucleus"
	testRevision = "188c35d188c35d188c35d188c35d188c35d18800"
)

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// writeRelease lays out a nucleus-style release in dir (artifacts, SHA256SUMS,
// bundle) and returns the matching manifest. The bundle is a placeholder: its
// signature is verified by cosign in the workflow, not by this package.
func writeRelease(t *testing.T, dir string) *kernel.ArtifactManifest {
	t.Helper()
	files := map[string][]byte{
		"linux-image-7.2.4-lusoris1_x86_64.deb":   bytes.Repeat([]byte("deb-payload\n"), 128),
		"linux-mainstream-7.2.4-lusoris1-uki.efi": bytes.Repeat([]byte{0x4d, 0x5a, 0x00}, 1024),
		"kernel-mainstream.config":                []byte("CONFIG_KVM=m\nCONFIG_BPF_SYSCALL=y\n"),
	}
	var sums strings.Builder
	artifacts := make([]kernel.Artifact, 0, len(files))
	for _, name := range []string{"kernel-mainstream.config", "linux-image-7.2.4-lusoris1_x86_64.deb", "linux-mainstream-7.2.4-lusoris1-uki.efi"} {
		data := files[name]
		require.NoError(t, os.WriteFile(filepath.Join(dir, name), data, 0o600))
		digest := sha256Hex(data)
		fmt.Fprintf(&sums, "%s  %s\n", digest, name)
		artifacts = append(artifacts, kernel.Artifact{Name: name, SHA256: digest, Size: int64(len(data))})
	}
	sumsData := []byte(sums.String())
	require.NoError(t, os.WriteFile(filepath.Join(dir, kernel.ChecksumsFile), sumsData, 0o600))
	require.NoError(t, os.WriteFile(filepath.Join(dir, kernel.BundleFile), []byte(`{"placeholder":"bundle"}`), 0o600))
	return &kernel.ArtifactManifest{
		Schema:   kernel.ArtifactSchema,
		Provider: testProvider,
		Stream:   "mainstream",
		Version:  "7.2.4-lusoris1",
		Kernel: kernel.KernelInfo{
			Release:      "7.2.4-lusoris1",
			ConfigDigest: "sha256:" + sha256Hex(files["kernel-mainstream.config"]),
		},
		Artifacts: artifacts,
		Checksums: kernel.Checksums{File: kernel.ChecksumsFile, SHA256: sha256Hex(sumsData)},
		Provenance: kernel.Provenance{
			Repository:     testProvider,
			Tag:            "v7.2.4-lusoris1",
			Revision:       testRevision,
			Bundle:         kernel.BundleFile,
			SignerIdentity: "https://github.com/cordanaLLM/nucleus/.github/workflows/publish-release.yml@refs/tags/v7.2.4-lusoris1",
		},
	}
}

func manifestDoc(t *testing.T, m *kernel.ArtifactManifest) map[string]any {
	t.Helper()
	raw, err := json.Marshal(m)
	require.NoError(t, err)
	var doc map[string]any
	require.NoError(t, json.Unmarshal(raw, &doc))
	return doc
}

func parseManifestDoc(t *testing.T, doc map[string]any) (*kernel.ArtifactManifest, error) {
	t.Helper()
	raw, err := json.Marshal(doc)
	require.NoError(t, err)
	return kernel.ParseArtifactManifest(bytes.NewReader(raw))
}

func TestVerifyPinnedReleaseIsConsumed(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)

	res, err := kernel.Verify(m, dir)
	require.NoError(t, err)
	assert.Equal(t, "mainstream", res.Stream)
	assert.Equal(t, "7.2.4-lusoris1", res.Version)
	assert.Equal(t, "7.2.4-lusoris1", res.KernelRelease)
	assert.Equal(t, "sha256:"+m.Checksums.SHA256, res.ArtifactDigest)
	assert.Equal(t, m.Kernel.ConfigDigest, res.ConfigDigest)
	assert.Len(t, res.Artifacts, 3)
	assert.Empty(t, res.Extra)
	assert.True(t, res.BundlePresent)
	assert.Equal(t, m.Provenance, res.Provenance)
}

func TestVerifyRoundTripsThroughJSON(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	raw, err := json.MarshalIndent(m, "", "  ")
	require.NoError(t, err)
	path := filepath.Join(t.TempDir(), "kernel-mainstream.manifest.json")
	require.NoError(t, os.WriteFile(path, raw, 0o600))

	loaded, err := kernel.LoadArtifactManifest(path)
	require.NoError(t, err)
	require.NoError(t, loaded.Conform(kernel.Policy{Provider: testProvider, Stream: "mainstream", Version: "7.2.4-lusoris1", Tag: "v7.2.4-lusoris1"}))
	_, err = kernel.Verify(loaded, dir)
	require.NoError(t, err)

	_, err = kernel.LoadArtifactManifest(filepath.Join(dir, "missing.json"))
	require.Error(t, err)
}

func TestVerifyRejectsTamperedArtifact(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	name := m.Artifacts[1].Name
	data, err := os.ReadFile(filepath.Join(dir, name))
	require.NoError(t, err)
	data[0] ^= 0xff // same size, different content
	require.NoError(t, os.WriteFile(filepath.Join(dir, name), data, 0o600))

	_, err = kernel.Verify(m, dir)
	require.Error(t, err)
	assert.True(t, errors.Is(err, kernel.ErrDigestMismatch), "expected ErrDigestMismatch, got %v", err)
	assert.Contains(t, err.Error(), "kernel artifact mainstream@7.2.4-lusoris1: artifacts["+name+"]")
}

func TestVerifyRejectsSizeMismatch(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	name := m.Artifacts[0].Name
	f, err := os.OpenFile(filepath.Join(dir, name), os.O_APPEND|os.O_WRONLY, 0o600)
	require.NoError(t, err)
	_, err = f.Write([]byte("\n"))
	require.NoError(t, err)
	require.NoError(t, f.Close())

	_, err = kernel.Verify(m, dir)
	assert.True(t, errors.Is(err, kernel.ErrSizeMismatch), "expected ErrSizeMismatch, got %v", err)
}

func TestVerifyRejectsMissingArtifactAndBundle(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	require.NoError(t, os.Remove(filepath.Join(dir, m.Artifacts[2].Name)))
	_, err := kernel.Verify(m, dir)
	assert.True(t, errors.Is(err, kernel.ErrMissingArtifact), "expected ErrMissingArtifact, got %v", err)

	dir = t.TempDir()
	m = writeRelease(t, dir)
	require.NoError(t, os.Remove(filepath.Join(dir, kernel.BundleFile)))
	_, err = kernel.Verify(m, dir)
	assert.True(t, errors.Is(err, kernel.ErrMissingBundle), "expected ErrMissingBundle, got %v", err)
}

func TestVerifyRejectsTamperedChecksumList(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	sums, err := os.ReadFile(filepath.Join(dir, kernel.ChecksumsFile))
	require.NoError(t, err)
	require.NoError(t, os.WriteFile(filepath.Join(dir, kernel.ChecksumsFile), append(sums, '\n'), 0o600))

	_, err = kernel.Verify(m, dir)
	require.Error(t, err)
	assert.True(t, errors.Is(err, kernel.ErrDigestMismatch))
	assert.Contains(t, err.Error(), "checksums.sha256")

	dir = t.TempDir()
	m = writeRelease(t, dir)
	require.NoError(t, os.Remove(filepath.Join(dir, kernel.ChecksumsFile)))
	_, err = kernel.Verify(m, dir)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "checksums.file")
}

func TestVerifyRejectsChecksumEntryDrift(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	// SHA256SUMS omits one listed artifact; its own digest is re-pinned so only the entry check can fail.
	lines := []string{}
	for _, a := range m.Artifacts[1:] {
		lines = append(lines, a.SHA256+"  "+a.Name)
	}
	sums := []byte(strings.Join(lines, "\n") + "\n")
	require.NoError(t, os.WriteFile(filepath.Join(dir, kernel.ChecksumsFile), sums, 0o600))
	m.Checksums.SHA256 = sha256Hex(sums)

	_, err := kernel.Verify(m, dir)
	assert.True(t, errors.Is(err, kernel.ErrChecksumEntry), "expected ErrChecksumEntry, got %v", err)

	malformed := []byte("not-a-checksum-line\n")
	require.NoError(t, os.WriteFile(filepath.Join(dir, kernel.ChecksumsFile), malformed, 0o600))
	m.Checksums.SHA256 = sha256Hex(malformed)
	_, err = kernel.Verify(m, dir)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "line 1 is not")
}

func TestVerifyReportsExtraFilesWithoutFailing(t *testing.T) {
	dir := t.TempDir()
	m := writeRelease(t, dir)
	require.NoError(t, os.WriteFile(filepath.Join(dir, "kernel-mainstream.manifest.json"), []byte("{}"), 0o600))
	require.NoError(t, os.Mkdir(filepath.Join(dir, "subdir"), 0o700))

	res, err := kernel.Verify(m, dir)
	require.NoError(t, err)
	assert.Equal(t, []string{"kernel-mainstream.manifest.json"}, res.Extra)
}

func TestVerifyRejectsInvalidManifestBeforeReadingFiles(t *testing.T) {
	m := writeRelease(t, t.TempDir())
	m.Schema = "other"
	_, err := kernel.Verify(m, filepath.Join(t.TempDir(), "absent"))
	require.Error(t, err)
	assert.Contains(t, err.Error(), "schema: must be")
}

func TestConformPolicy(t *testing.T) {
	m := writeRelease(t, t.TempDir())
	require.NoError(t, m.Conform(kernel.Policy{}))
	require.NoError(t, m.Conform(kernel.Policy{Provider: testProvider, Stream: "mainstream"}))

	err := m.Conform(kernel.Policy{Stream: "lts"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), `stream: expected "lts", manifest has "mainstream"`)
	assert.Error(t, m.Conform(kernel.Policy{Provider: "lusoris/lusoris-kernel-forge"}))
	assert.Error(t, m.Conform(kernel.Policy{Version: "7.2.5-lusoris1"}))
	assert.Error(t, m.Conform(kernel.Policy{Tag: "v7.2.5-lusoris1"}))
}

func TestParseArtifactManifestNegative(t *testing.T) {
	validDigest := "sha256:" + strings.Repeat("a", 64)
	cases := []struct {
		name   string
		mutate func(doc map[string]any)
		want   string
	}{
		{"unknown field", func(d map[string]any) { d["signature"] = "x" }, `unknown field "signature"`},
		{"schema", func(d map[string]any) { d["schema"] = "imago.nucleus.kernel-artifact.v2" }, "schema: must be"},
		{"provider slug", func(d map[string]any) { d["provider"] = "nucleus" }, "provider: must be an owner/repository slug"},
		{"stream", func(d map[string]any) { d["stream"] = "nightly" }, "stream: must be one of bleeding, mainstream, lts, realtime"},
		{"version", func(d map[string]any) { d["version"] = "v7.2.4" }, "version: must be a bounded version token"},
		{"kernel release", func(d map[string]any) { d["kernel"] = map[string]any{"release": "", "config_digest": validDigest} }, "kernel.release"},
		{"config digest", func(d map[string]any) {
			d["kernel"] = map[string]any{"release": "7.2.4", "config_digest": "sha256:short"}
		}, "kernel.config_digest: must be sha256:<64 hex>"},
		{"empty artifacts", func(d map[string]any) { d["artifacts"] = []any{} }, "artifacts: must list 1..64 entries"},
		{"path traversal name", func(d map[string]any) {
			d["artifacts"] = []any{map[string]any{"name": "../etc/passwd", "sha256": strings.Repeat("b", 64), "size": 1}}
		}, "artifacts[0].name: must be a safe basename"},
		{"slash in name", func(d map[string]any) {
			d["artifacts"] = []any{map[string]any{"name": "dir/file.deb", "sha256": strings.Repeat("b", 64), "size": 1}}
		}, "artifacts[0].name"},
		{"checksum file listed as artifact", func(d map[string]any) {
			d["artifacts"] = []any{map[string]any{"name": "SHA256SUMS", "sha256": strings.Repeat("b", 64), "size": 1}}
		}, "SHA256SUMS is verified separately"},
		{"uppercase sha", func(d map[string]any) {
			d["artifacts"] = []any{map[string]any{"name": "a.deb", "sha256": strings.Repeat("B", 64), "size": 1}}
		}, "artifacts[0].sha256"},
		{"negative size", func(d map[string]any) {
			d["artifacts"] = []any{map[string]any{"name": "a.deb", "sha256": strings.Repeat("b", 64), "size": -1}}
		}, "artifacts[0].size"},
		{"duplicate name", func(d map[string]any) {
			a := map[string]any{"name": "a.deb", "sha256": strings.Repeat("b", 64), "size": 1}
			d["artifacts"] = []any{a, a}
		}, "artifacts[1].name: duplicate artifact a.deb"},
		{"checksums file name", func(d map[string]any) {
			d["checksums"] = map[string]any{"file": "sums.txt", "sha256": strings.Repeat("b", 64)}
		}, `checksums.file: must be "SHA256SUMS"`},
		{"checksums digest", func(d map[string]any) { d["checksums"] = map[string]any{"file": "SHA256SUMS", "sha256": "abc"} }, "checksums.sha256"},
		{"provenance repository", func(d map[string]any) {
			d["provenance"].(map[string]any)["repository"] = "lusoris/lusoris-kernel-forge"
		}, "provenance.repository: must equal provider"},
		{"provenance tag", func(d map[string]any) { d["provenance"].(map[string]any)["tag"] = "7.2.4-lusoris1" }, "provenance.tag"},
		{"provenance revision", func(d map[string]any) { d["provenance"].(map[string]any)["revision"] = "188c35d" }, "provenance.revision"},
		{"provenance bundle", func(d map[string]any) { d["provenance"].(map[string]any)["bundle"] = "SHA256SUMS.sig" }, `provenance.bundle: must be "SHA256SUMS.bundle"`},
		{"signer identity outside provider", func(d map[string]any) {
			d["provenance"].(map[string]any)["signer_identity"] = "https://github.com/someone-else/nucleus/.github/workflows/publish-release.yml@refs/tags/v1"
		}, "provenance.signer_identity"},
		{"signer identity empty", func(d map[string]any) { d["provenance"].(map[string]any)["signer_identity"] = "" }, "provenance.signer_identity"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			doc := manifestDoc(t, writeRelease(t, t.TempDir()))
			tc.mutate(doc)
			_, err := parseManifestDoc(t, doc)
			require.Error(t, err)
			assert.Contains(t, err.Error(), tc.want)
		})
	}
}

func TestParseArtifactManifestBoundaries(t *testing.T) {
	m := writeRelease(t, t.TempDir())
	base := m.Artifacts[0]
	list := make([]kernel.Artifact, 0, kernel.MaxArtifacts+1)
	for i := 0; i <= kernel.MaxArtifacts; i++ {
		list = append(list, kernel.Artifact{Name: fmt.Sprintf("artifact-%d.deb", i), SHA256: base.SHA256, Size: 0})
	}
	m.Artifacts = list[:kernel.MaxArtifacts]
	require.NoError(t, m.Validate())
	m.Artifacts = list
	require.Error(t, m.Validate())

	m = writeRelease(t, t.TempDir())
	m.Artifacts[0].Size = kernel.MaxArtifactBytes
	require.NoError(t, m.Validate())
	m.Artifacts[0].Size = kernel.MaxArtifactBytes + 1
	require.Error(t, m.Validate())

	m = writeRelease(t, t.TempDir())
	m.Stream, m.Version = "", ""
	err := m.Validate()
	require.Error(t, err)
	assert.True(t, strings.HasPrefix(err.Error(), "kernel artifact: stream:"), err.Error())
}
