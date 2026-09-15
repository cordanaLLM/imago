// Copyright 2026 Lusoris
package kernel

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Verification bounds.
const (
	MaxChecksumsBytes int64 = 1 << 20
	MaxChecksumLines        = 1024
	MaxDirEntries           = 4096
)

// Verification sentinels; every failure wraps exactly one of them.
var (
	ErrDigestMismatch  = errors.New("digest mismatch")
	ErrSizeMismatch    = errors.New("size mismatch")
	ErrMissingArtifact = errors.New("artifact missing")
	ErrChecksumEntry   = errors.New("checksum entry mismatch")
	ErrMissingBundle   = errors.New("signature bundle missing")
	ErrNotRegularFile  = errors.New("not a regular file")
)

// checksumLineRegex accepts the sha256sum text ("<hex>  <name>") and binary ("<hex> *<name>") forms.
var checksumLineRegex = regexp.MustCompile(`^([a-f0-9]{64}) [ *](\S.*)$`)

// Verification is the typed result of Verify. ArtifactDigest is the digest of
// SHA256SUMS, the value pinned as kernel.streams.<stream>.artifact_digest in
// versions.json. Extra lists unlisted files found next to the artifacts; they
// are reported, not rejected.
type Verification struct {
	Stream         string     `json:"stream"`
	Version        string     `json:"version"`
	KernelRelease  string     `json:"kernel_release"`
	ConfigDigest   string     `json:"config_digest"`
	ArtifactDigest string     `json:"artifact_digest"`
	Artifacts      []Artifact `json:"artifacts"`
	Extra          []string   `json:"extra"`
	Provenance     Provenance `json:"provenance"`
	BundlePresent  bool       `json:"bundle_present"`
}

// Verify recomputes every digest the manifest claims against the files in dir.
// Order: the manifest is validated; SHA256SUMS is digested and parsed; each
// listed artifact must appear in SHA256SUMS with the same digest and match on
// size and recomputed SHA-256; the cosign bundle must be present (its
// signature is checked by cosign verify-blob in the workflow, not here);
// unlisted files are reported in Extra.
func Verify(m *ArtifactManifest, dir string) (*Verification, error) {
	if err := m.Validate(); err != nil {
		return nil, err
	}
	sums, sumsDigest, err := verifyChecksums(m, dir)
	if err != nil {
		return nil, err
	}
	res := &Verification{
		Stream:         m.Stream,
		Version:        m.Version,
		KernelRelease:  m.Kernel.Release,
		ConfigDigest:   m.Kernel.ConfigDigest,
		ArtifactDigest: "sha256:" + sumsDigest,
		Artifacts:      make([]Artifact, 0, len(m.Artifacts)),
		Extra:          []string{},
		Provenance:     m.Provenance,
	}
	for _, a := range m.Artifacts {
		if err := verifyArtifact(m, dir, a, sums); err != nil {
			return nil, err
		}
		res.Artifacts = append(res.Artifacts, a)
	}
	if err := requireRegular(filepath.Join(dir, m.Provenance.Bundle)); err != nil {
		return nil, m.fieldWrap("provenance.bundle", fmt.Errorf("%w: %w", ErrMissingBundle, err))
	}
	res.BundlePresent = true
	if res.Extra, err = extraFiles(m, dir); err != nil {
		return nil, err
	}
	return res, nil
}

// verifyChecksums digests SHA256SUMS against the manifest and parses its entries.
func verifyChecksums(m *ArtifactManifest, dir string) (map[string]string, string, error) {
	path := filepath.Join(dir, m.Checksums.File)
	if err := requireRegular(path); err != nil {
		return nil, "", m.fieldWrap("checksums.file", err)
	}
	data, err := readBounded(path, MaxChecksumsBytes)
	if err != nil {
		return nil, "", m.fieldWrap("checksums.file", err)
	}
	sum := sha256.Sum256(data)
	digest := hex.EncodeToString(sum[:])
	if digest != m.Checksums.SHA256 {
		return nil, "", m.fieldWrap("checksums.sha256", fmt.Errorf("%w: manifest %s, file %s", ErrDigestMismatch, m.Checksums.SHA256, digest))
	}
	sums, err := parseChecksums(data)
	if err != nil {
		return nil, "", m.fieldWrap("checksums.file", err)
	}
	return sums, digest, nil
}

// parseChecksums maps artifact names to the digests SHA256SUMS lists.
func parseChecksums(data []byte) (map[string]string, error) {
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) > MaxChecksumLines {
		return nil, fmt.Errorf("%s has more than %d lines", ChecksumsFile, MaxChecksumLines)
	}
	sums := make(map[string]string, len(lines))
	for i, line := range lines {
		line = strings.TrimRight(line, "\r")
		if line == "" {
			continue
		}
		match := checksumLineRegex.FindStringSubmatch(line)
		if match == nil {
			return nil, fmt.Errorf("%s line %d is not '<sha256>  <name>'", ChecksumsFile, i+1)
		}
		if _, dup := sums[match[2]]; dup {
			return nil, fmt.Errorf("%s lists %s twice", ChecksumsFile, match[2])
		}
		sums[match[2]] = match[1]
	}
	return sums, nil
}

// verifyArtifact checks one artifact against SHA256SUMS, its size, and its recomputed digest.
func verifyArtifact(m *ArtifactManifest, dir string, a Artifact, sums map[string]string) error {
	field := "artifacts[" + a.Name + "]"
	listed, ok := sums[a.Name]
	if !ok {
		return m.fieldWrap(field, fmt.Errorf("%w: not listed in %s", ErrChecksumEntry, ChecksumsFile))
	}
	if listed != a.SHA256 {
		return m.fieldWrap(field, fmt.Errorf("%w: manifest %s, %s %s", ErrChecksumEntry, a.SHA256, ChecksumsFile, listed))
	}
	path := filepath.Join(dir, a.Name)
	info, err := os.Lstat(path)
	if err != nil {
		return m.fieldWrap(field, fmt.Errorf("%w: %w", ErrMissingArtifact, err))
	}
	if !info.Mode().IsRegular() {
		return m.fieldWrap(field, ErrNotRegularFile)
	}
	if info.Size() != a.Size {
		return m.fieldWrap(field, fmt.Errorf("%w: manifest %d bytes, file %d bytes", ErrSizeMismatch, a.Size, info.Size()))
	}
	digest, _, err := digestFile(path, MaxArtifactBytes)
	if err != nil {
		return m.fieldWrap(field, err)
	}
	if digest != a.SHA256 {
		return m.fieldWrap(field, fmt.Errorf("%w: manifest %s, file %s", ErrDigestMismatch, a.SHA256, digest))
	}
	return nil
}

// extraFiles lists regular files in dir that neither the manifest nor the contract names.
func extraFiles(m *ArtifactManifest, dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, m.fieldWrap("dir", err)
	}
	if len(entries) > MaxDirEntries {
		return nil, m.fieldWrap("dir", fmt.Errorf("more than %d entries", MaxDirEntries))
	}
	listed := make(map[string]struct{}, len(m.Artifacts)+2)
	for _, a := range m.Artifacts {
		listed[a.Name] = struct{}{}
	}
	listed[m.Checksums.File] = struct{}{}
	listed[m.Provenance.Bundle] = struct{}{}
	extra := []string{}
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if _, ok := listed[e.Name()]; !ok {
			extra = append(extra, e.Name())
		}
	}
	return extra, nil
}

// requireRegular rejects a missing path, a directory, or a symbolic link.
func requireRegular(path string) error {
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return fmt.Errorf("%s: %w", filepath.Base(path), ErrNotRegularFile)
	}
	return nil
}

// readBounded reads a file of at most limit bytes into memory.
func readBounded(path string, limit int64) ([]byte, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	if int64(len(data)) > limit {
		return nil, fmt.Errorf("%s %w of %d bytes", filepath.Base(path), ErrTooLarge, limit)
	}
	return data, nil
}
