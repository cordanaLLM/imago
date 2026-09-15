// Copyright 2026 Lusoris
package kernel

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// ArtifactSchema is the contract identifier of the manifest nucleus publishes
// as kernel-<stream>.manifest.json with every GitHub release.
const ArtifactSchema = "imago.nucleus.kernel-artifact.v1"

// ChecksumsFile and BundleFile are the fixed names of the release checksum
// list and the keyless cosign bundle signed over it.
const (
	ChecksumsFile = "SHA256SUMS"
	BundleFile    = "SHA256SUMS.bundle"
)

// Artifact manifest bounds.
const (
	MaxArtifactManifestBytes int64 = 1 << 20
	MaxArtifacts                   = 64
	maxProviderLen                 = 128
	maxVersionLen                  = 64
	maxArtifactNameLen             = 255
	maxTagLen                      = 64
	maxSignerIdentityLen           = 512
)

// MaxArtifactBytes bounds one artifact read during verification. A kernel
// .deb or UKI is tens of megabytes; 512 MiB leaves room for debug symbols.
const MaxArtifactBytes int64 = 512 << 20

// Streams are the kernel streams nucleus builds (its versions.json streams map).
var Streams = []string{"bleeding", "mainstream", "lts", "realtime"}

var (
	providerRegex     = regexp.MustCompile(`^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`)
	versionRegex      = regexp.MustCompile(`^[0-9][A-Za-z0-9._+-]*$`)
	digestRegex       = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)
	hexDigestRegex    = regexp.MustCompile(`^[a-f0-9]{64}$`)
	artifactNameRegex = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._+-]*$`)
	tagRegex          = regexp.MustCompile(`^v[0-9][A-Za-z0-9._-]*$`)
	revisionRegex     = regexp.MustCompile(`^[a-f0-9]{40}$`)
)

// ArtifactManifest is the imago.nucleus.kernel-artifact.v1 document.
type ArtifactManifest struct {
	Schema     string     `json:"schema"`
	Provider   string     `json:"provider"`
	Stream     string     `json:"stream"`
	Version    string     `json:"version"`
	Kernel     KernelInfo `json:"kernel"`
	Artifacts  []Artifact `json:"artifacts"`
	Checksums  Checksums  `json:"checksums"`
	Provenance Provenance `json:"provenance"`
}

// KernelInfo names the kernel release (uname -r) and the digest of the shipped configuration.
type KernelInfo struct {
	Release      string `json:"release"`
	ConfigDigest string `json:"config_digest"`
}

// Artifact is one release asset listed in SHA256SUMS.
type Artifact struct {
	Name   string `json:"name"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
}

// Checksums names the checksum list and its own digest, the value pinned in versions.json.
type Checksums struct {
	File   string `json:"file"`
	SHA256 string `json:"sha256"`
}

// Provenance binds the manifest to the nucleus release and its keyless signature.
type Provenance struct {
	Repository     string `json:"repository"`
	Tag            string `json:"tag"`
	Revision       string `json:"revision"`
	Bundle         string `json:"bundle"`
	SignerIdentity string `json:"signer_identity"`
}

// Policy pins what the consumer expects before verification: the provider
// from versions.json and the stream, version, and tag the dispatch payload
// named. Empty fields are not checked.
type Policy struct {
	Provider string
	Stream   string
	Version  string
	Tag      string
}

// LoadArtifactManifest reads, strictly decodes, and validates a manifest file.
func LoadArtifactManifest(path string) (*ArtifactManifest, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("kernel artifact: open %s: %w", path, err)
	}
	defer f.Close()
	return ParseArtifactManifest(f)
}

// ParseArtifactManifest strictly decodes a manifest and validates it.
func ParseArtifactManifest(r io.Reader) (*ArtifactManifest, error) {
	var m ArtifactManifest
	if err := decodeStrict(r, MaxArtifactManifestBytes, &m); err != nil {
		return nil, fmt.Errorf("kernel artifact: %w", err)
	}
	if err := m.Validate(); err != nil {
		return nil, err
	}
	return &m, nil
}

// Validate checks every field against the contract. Errors are correlated by
// stream and version: "kernel artifact <stream>@<version>: <field>: <reason>".
func (m *ArtifactManifest) Validate() error {
	if m.Schema != ArtifactSchema {
		return m.fieldErr("schema", fmt.Sprintf("must be %q", ArtifactSchema))
	}
	if !boundedToken(m.Provider, maxProviderLen, providerRegex) {
		return m.fieldErr("provider", "must be an owner/repository slug")
	}
	if !knownStream(m.Stream) {
		return m.fieldErr("stream", fmt.Sprintf("must be one of %s", strings.Join(Streams, ", ")))
	}
	if !boundedToken(m.Version, maxVersionLen, versionRegex) {
		return m.fieldErr("version", "must be a bounded version token such as 7.2.4-lusoris1")
	}
	if !boundedToken(m.Kernel.Release, maxVersionLen, versionRegex) {
		return m.fieldErr("kernel.release", "must be a bounded kernel release token")
	}
	if !digestRegex.MatchString(m.Kernel.ConfigDigest) {
		return m.fieldErr("kernel.config_digest", "must be sha256:<64 hex>")
	}
	if err := m.validateArtifacts(); err != nil {
		return err
	}
	if err := m.validateChecksums(); err != nil {
		return err
	}
	return m.validateProvenance()
}

// Conform rejects a manifest that does not match the consumer's expectations.
func (m *ArtifactManifest) Conform(p Policy) error {
	checks := [...]struct{ field, want, got string }{
		{"provider", p.Provider, m.Provider},
		{"stream", p.Stream, m.Stream},
		{"version", p.Version, m.Version},
		{"provenance.tag", p.Tag, m.Provenance.Tag},
	}
	for _, c := range checks {
		if c.want != "" && c.want != c.got {
			return m.fieldErr(c.field, fmt.Sprintf("expected %q, manifest has %q", c.want, c.got))
		}
	}
	return nil
}

func (m *ArtifactManifest) fieldErr(field, reason string) error {
	return m.fieldWrap(field, errors.New(reason))
}

func (m *ArtifactManifest) fieldWrap(field string, err error) error {
	if m.Stream == "" && m.Version == "" {
		return fmt.Errorf("kernel artifact: %s: %w", field, err)
	}
	return fmt.Errorf("kernel artifact %s@%s: %s: %w", m.Stream, m.Version, field, err)
}

func (m *ArtifactManifest) validateArtifacts() error {
	if n := len(m.Artifacts); n == 0 || n > MaxArtifacts {
		return m.fieldErr("artifacts", fmt.Sprintf("must list 1..%d entries", MaxArtifacts))
	}
	seen := make(map[string]struct{}, len(m.Artifacts))
	for i, a := range m.Artifacts {
		field := fmt.Sprintf("artifacts[%d]", i)
		if !safeBasename(a.Name) {
			return m.fieldErr(field+".name", "must be a safe basename without path separators or ..")
		}
		if a.Name == ChecksumsFile || a.Name == BundleFile {
			return m.fieldErr(field+".name", a.Name+" is verified separately and must not be listed")
		}
		if !hexDigestRegex.MatchString(a.SHA256) {
			return m.fieldErr(field+".sha256", "must be 64 lowercase hex characters")
		}
		if a.Size < 0 || a.Size > MaxArtifactBytes {
			return m.fieldErr(field+".size", fmt.Sprintf("must be 0..%d bytes", MaxArtifactBytes))
		}
		if _, dup := seen[a.Name]; dup {
			return m.fieldErr(field+".name", "duplicate artifact "+a.Name)
		}
		seen[a.Name] = struct{}{}
	}
	return nil
}

func (m *ArtifactManifest) validateChecksums() error {
	if m.Checksums.File != ChecksumsFile {
		return m.fieldErr("checksums.file", fmt.Sprintf("must be %q", ChecksumsFile))
	}
	if !hexDigestRegex.MatchString(m.Checksums.SHA256) {
		return m.fieldErr("checksums.sha256", "must be 64 lowercase hex characters")
	}
	return nil
}

func (m *ArtifactManifest) validateProvenance() error {
	p := m.Provenance
	if p.Repository != m.Provider {
		return m.fieldErr("provenance.repository", fmt.Sprintf("must equal provider %q", m.Provider))
	}
	if !boundedToken(p.Tag, maxTagLen, tagRegex) {
		return m.fieldErr("provenance.tag", "must be a release tag such as v7.2.4-lusoris1")
	}
	if !revisionRegex.MatchString(p.Revision) {
		return m.fieldErr("provenance.revision", "must be a 40-character lowercase git commit hash")
	}
	if p.Bundle != BundleFile {
		return m.fieldErr("provenance.bundle", fmt.Sprintf("must be %q", BundleFile))
	}
	identityPrefix := "https://github.com/" + m.Provider + "/"
	if len(p.SignerIdentity) > maxSignerIdentityLen || !strings.HasPrefix(p.SignerIdentity, identityPrefix) {
		return m.fieldErr("provenance.signer_identity", "must be a bounded workflow identity under "+identityPrefix)
	}
	return nil
}

// knownStream checks the stream against the Streams allow-list.
func knownStream(stream string) bool {
	for _, s := range Streams {
		if s == stream {
			return true
		}
	}
	return false
}

// safeBasename accepts a bounded file name with no path separators and no "..".
func safeBasename(name string) bool {
	return boundedToken(name, maxArtifactNameLen, artifactNameRegex) && !strings.Contains(name, "..")
}
