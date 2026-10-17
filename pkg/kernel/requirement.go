// Copyright 2026 Lusoris
package kernel

import (
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"slices"
)

// RequirementSchema is the exact schema identifier of the Aegis kernel-requirement payload.
const RequirementSchema = "aegis.p01-nucleus.kernel-requirement.v1"

// MaxRequirementBytes bounds a requirement document. It is the payload bound
// of the schema owner, Aegis-OS, at the commit ADR-0030 pins.
const MaxRequirementBytes int64 = 16384

// Requirement field bounds, each the bound of the schema owner (ADR-0030).
const (
	MaxCorrelationIDLen = 128
	MaxArchitectures    = 4
	MaxFeatures         = 64
	maxReleaseTokenLen  = 64
	maxReleaseParts     = 8
	maxSymbolLen        = 64
	maxRequiredByLen    = 128
	digestHexLen        = 64
	maxSignatureHexLen  = 256
)

// Feature states the Aegis payload may request.
const (
	StateBuiltIn = "built-in"
	StateModule  = "module"
	StatePresent = "present"
	StateAbsent  = "absent"
)

// KnownStates is the allow-list of feature states.
var KnownStates = []string{StateBuiltIn, StateModule, StatePresent, StateAbsent}

// KnownArchitectures is the allow-list of architectures a requirement may name.
var KnownArchitectures = []string{"x86-64", "arm64"}

// KnownProbes is the allow-list of probe methods a feature may name. Extending
// the Aegis contract with a new probe is a one-line change here.
var KnownProbes = []string{"kernel-config", "lsm-list", "btf-vmlinux", "powercap", "iommu-groups"}

// ErrEmptyRequirement is returned when a requirement carries no features. An
// empty requirement would let any kernel pass, so it is rejected explicitly.
var ErrEmptyRequirement = errors.New("feature list is empty")

var (
	correlationIDRegex = regexp.MustCompile(`^[A-Za-z0-9._:-]+$`)
	releaseRegex       = regexp.MustCompile(`^[0-9][0-9A-Za-z._+-]*$`)
	symbolRegex        = regexp.MustCompile(`^CONFIG_[A-Z0-9_]+$`)
	requiredByRegex    = regexp.MustCompile(`^[A-Z][A-Z0-9-]*$`)
	signatureRegex     = regexp.MustCompile(`^(?:[0-9a-f]{2})+$`)
)

// Requirement is the aegis.p01-nucleus.kernel-requirement.v1 document.
type Requirement struct {
	Schema        string    `json:"schema"`
	CorrelationID string    `json:"correlation-id"`
	Architectures []string  `json:"architectures"`
	ABI           ABI       `json:"abi"`
	Features      []Feature `json:"features"`
	// Artifact is absent or null while no artifact is expected.
	Artifact *ArtifactExpectation `json:"artifact,omitempty"`
}

// ABI carries the kernel release floor and the optional target release or
// module ABI. An absent or null optional release is nil; an empty one is refused.
type ABI struct {
	MinimumRelease string  `json:"minimum-release"`
	TargetRelease  *string `json:"target-release,omitempty"`
	ModuleABI      *string `json:"module-abi,omitempty"`
}

// Feature is one requested kernel configuration symbol and how nucleus proves it.
type Feature struct {
	Symbol     string `json:"symbol"`
	State      string `json:"state"`
	Probe      string `json:"probe"`
	RequiredBy string `json:"required-by"`
}

// ArtifactExpectation is the digest, and optionally the signature, a
// conforming kernel artifact is expected to carry, both lowercase hex.
type ArtifactExpectation struct {
	Digest    string  `json:"digest"`
	Signature *string `json:"signature,omitempty"`
}

// LoadRequirement reads, strictly decodes, and validates a requirement file.
func LoadRequirement(path string) (*Requirement, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, bounded(fmt.Errorf("kernel requirement: open %s: %w", path, err))
	}
	defer f.Close()
	return ParseRequirement(f)
}

// ParseRequirement strictly decodes a requirement: unknown fields, trailing
// data, and documents above MaxRequirementBytes are rejected before validation.
func ParseRequirement(r io.Reader) (*Requirement, error) {
	var q Requirement
	if err := decodeStrict(r, MaxRequirementBytes, &q); err != nil {
		return nil, bounded(fmt.Errorf("kernel requirement: %w", err))
	}
	if err := q.Validate(); err != nil {
		return nil, err
	}
	return &q, nil
}

// Validate checks every field against the contract bounds. Errors name the
// correlation id, the field, and the reason.
func (q *Requirement) Validate() error {
	if q.Schema != RequirementSchema {
		return q.fieldErr("schema", fmt.Sprintf("must be %q", RequirementSchema))
	}
	if !boundedToken(q.CorrelationID, MaxCorrelationIDLen, correlationIDRegex) {
		return q.fieldErr("correlation-id", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._:-]", MaxCorrelationIDLen))
	}
	if err := q.validateArchitectures(); err != nil {
		return err
	}
	if err := q.validateABI(); err != nil {
		return err
	}
	if err := q.validateFeatures(); err != nil {
		return err
	}
	return q.validateArtifact()
}

// fieldErr formats "kernel requirement <cid>: <field>: <reason>".
func (q *Requirement) fieldErr(field, reason string) error {
	return q.fieldWrap(field, errors.New(reason))
}

// fieldWrap keeps err in the chain so callers can test sentinels with errors.Is.
// An invalid correlation id is reported as a placeholder, and the text is bounded.
func (q *Requirement) fieldWrap(field string, err error) error {
	if q.CorrelationID == "" {
		return bounded(fmt.Errorf("kernel requirement: %s: %w", field, err))
	}
	cid := reported(q.CorrelationID, boundedToken(q.CorrelationID, MaxCorrelationIDLen, correlationIDRegex))
	return bounded(fmt.Errorf("kernel requirement %s: %s: %w", cid, field, err))
}

func (q *Requirement) validateArchitectures() error {
	if n := len(q.Architectures); n == 0 || n > MaxArchitectures {
		return q.fieldErr("architectures", fmt.Sprintf("must list 1..%d entries", MaxArchitectures))
	}
	for i, a := range q.Architectures {
		if !slices.Contains(KnownArchitectures, a) {
			return q.fieldErr(fmt.Sprintf("architectures[%d]", i), fmt.Sprintf("must be one of %v", KnownArchitectures))
		}
	}
	return nil
}

func (q *Requirement) validateABI() error {
	const releaseRule = "must be 1..64 characters of [0-9A-Za-z._+-] starting with a digit"
	if !boundedToken(q.ABI.MinimumRelease, maxReleaseTokenLen, releaseRegex) {
		return q.fieldErr("abi.minimum-release", releaseRule)
	}
	if t := q.ABI.TargetRelease; t != nil {
		if !boundedToken(*t, maxReleaseTokenLen, releaseRegex) {
			return q.fieldErr("abi.target-release", releaseRule)
		}
		if !releaseAtLeast(*t, q.ABI.MinimumRelease) {
			return q.fieldErr("abi.target-release", fmt.Sprintf("target release %s is older than the minimum release %s", *t, q.ABI.MinimumRelease))
		}
	}
	if m := q.ABI.ModuleABI; m != nil && !boundedToken(*m, maxReleaseTokenLen, releaseRegex) {
		return q.fieldErr("abi.module-abi", releaseRule)
	}
	return nil
}

// releaseAtLeast reports whether release is floor or newer. Like the schema
// owner, it compares only the leading dotted numeric components, at most
// maxReleaseParts of them, and reads a missing component as zero; a
// distribution suffix is not ordered.
func releaseAtLeast(release, floor string) bool {
	mine, theirs := releaseParts(release), releaseParts(floor)
	for i := range maxReleaseParts {
		if mine[i] != theirs[i] {
			return mine[i] > theirs[i]
		}
	}
	return true
}

// releaseParts reads the leading dotted numeric components of a release. The
// scan stops at the first character that is neither a digit nor a dot
// following a digit, and a component saturates instead of overflowing.
func releaseParts(release string) [maxReleaseParts]uint64 {
	var parts [maxReleaseParts]uint64
	n, started := 0, false
	for i := 0; i < len(release) && i < maxReleaseTokenLen; i++ {
		c := release[i]
		if c >= '0' && c <= '9' {
			parts[n] = saturatingDigit(parts[n], uint64(c-'0'))
			started = true
			continue
		}
		if c != '.' || !started || n+1 >= maxReleaseParts {
			break
		}
		n++
		started = false
	}
	return parts
}

// saturatingDigit appends a decimal digit to v, stopping at the uint64 maximum.
func saturatingDigit(v, digit uint64) uint64 {
	if v > (math.MaxUint64-digit)/10 {
		return math.MaxUint64
	}
	return v*10 + digit
}

func (q *Requirement) validateFeatures() error {
	if len(q.Features) == 0 {
		return q.fieldWrap("features", ErrEmptyRequirement)
	}
	if len(q.Features) > MaxFeatures {
		return q.fieldErr("features", fmt.Sprintf("more than %d entries", MaxFeatures))
	}
	seen := make(map[string]struct{}, len(q.Features))
	for i, f := range q.Features {
		if err := q.validateFeature(i, f); err != nil {
			return err
		}
		if _, dup := seen[f.Symbol]; dup {
			return q.fieldErr(fmt.Sprintf("features[%d].symbol", i), "duplicate symbol "+f.Symbol)
		}
		seen[f.Symbol] = struct{}{}
	}
	return nil
}

func (q *Requirement) validateFeature(i int, f Feature) error {
	field := func(name string) string { return fmt.Sprintf("features[%d].%s", i, name) }
	if !boundedToken(f.Symbol, maxSymbolLen, symbolRegex) {
		return q.fieldErr(field("symbol"), "must match CONFIG_[A-Z0-9_]+")
	}
	if !slices.Contains(KnownStates, f.State) {
		return q.fieldErr(field("state"), fmt.Sprintf("must be one of %v", KnownStates))
	}
	if !slices.Contains(KnownProbes, f.Probe) {
		return q.fieldErr(field("probe"), fmt.Sprintf("unknown probe %q", f.Probe))
	}
	if !boundedToken(f.RequiredBy, maxRequiredByLen, requiredByRegex) || f.RequiredBy == "REQ-" {
		return q.fieldErr(field("required-by"), "must be 1..128 characters of [A-Z0-9-] starting with a letter, not the bare prefix REQ-")
	}
	return nil
}

func (q *Requirement) validateArtifact() error {
	a := q.Artifact
	if a == nil {
		return nil
	}
	const field = "artifact"
	if !hexDigestRegex.MatchString(a.Digest) {
		return q.fieldErr(field+".digest", fmt.Sprintf("must be %d lowercase hex characters", digestHexLen))
	}
	if s := a.Signature; s != nil && !boundedToken(*s, maxSignatureHexLen, signatureRegex) {
		return q.fieldErr(field+".signature", fmt.Sprintf("must be 2..%d lowercase hex characters of even length", maxSignatureHexLen))
	}
	return nil
}
