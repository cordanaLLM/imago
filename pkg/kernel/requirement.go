// Copyright 2026 Lusoris
package kernel

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
)

// RequirementSchema is the exact schema identifier of the Aegis kernel-requirement payload.
const RequirementSchema = "aegis.p01-nucleus.kernel-requirement.v1"

// MaxRequirementBytes bounds a requirement document; a real payload is a few kilobytes.
const MaxRequirementBytes int64 = 1 << 20

// Requirement field bounds.
const (
	MaxCorrelationIDLen = 128
	MaxArchitectures    = 8
	MaxFeatures         = 512
	maxArchitectureLen  = 32
	maxReleaseTokenLen  = 64
	maxSymbolLen        = 128
	maxRequiredByLen    = 64
)

// Feature states the Aegis payload may request.
const (
	StateBuiltIn = "built-in"
	StateModule  = "module"
)

// KnownProbes is the allow-list of probe methods a feature may name. Extending
// the Aegis contract with a new probe is a one-line change here.
var KnownProbes = []string{"kernel-config", "lsm-list", "btf-vmlinux", "powercap", "iommu-groups"}

// ErrEmptyRequirement is returned when a requirement carries no features. An
// empty requirement would let any kernel pass, so it is rejected explicitly.
var ErrEmptyRequirement = errors.New("feature list is empty")

var (
	correlationIDRegex = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)
	architectureRegex  = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]*$`)
	dottedReleaseRegex = regexp.MustCompile(`^[0-9]+(\.[0-9]+){1,3}$`)
	releaseTokenRegex  = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._+-]*$`)
	symbolRegex        = regexp.MustCompile(`^CONFIG_[A-Z0-9_]+$`)
	requiredByRegex    = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)
)

// Requirement is the aegis.p01-nucleus.kernel-requirement.v1 document.
type Requirement struct {
	Schema        string    `json:"schema"`
	CorrelationID string    `json:"correlation-id"`
	Architectures []string  `json:"architectures"`
	ABI           ABI       `json:"abi"`
	Features      []Feature `json:"features"`
}

// ABI carries the kernel release floor and the optional target release or module ABI.
type ABI struct {
	MinimumRelease string `json:"minimum-release"`
	TargetRelease  string `json:"target-release,omitempty"`
	ModuleABI      string `json:"module-abi,omitempty"`
}

// Feature is one requested kernel configuration symbol and how nucleus proves it.
type Feature struct {
	Symbol     string `json:"symbol"`
	State      string `json:"state"`
	Probe      string `json:"probe"`
	RequiredBy string `json:"required-by"`
}

// LoadRequirement reads, strictly decodes, and validates a requirement file.
func LoadRequirement(path string) (*Requirement, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("kernel requirement: open %s: %w", path, err)
	}
	defer f.Close()
	return ParseRequirement(f)
}

// ParseRequirement strictly decodes a requirement: unknown fields, trailing
// data, and documents above MaxRequirementBytes are rejected before validation.
func ParseRequirement(r io.Reader) (*Requirement, error) {
	var q Requirement
	if err := decodeStrict(r, MaxRequirementBytes, &q); err != nil {
		return nil, fmt.Errorf("kernel requirement: %w", err)
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
		return q.fieldErr("correlation-id", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._-]", MaxCorrelationIDLen))
	}
	if err := q.validateArchitectures(); err != nil {
		return err
	}
	if err := q.validateABI(); err != nil {
		return err
	}
	return q.validateFeatures()
}

// fieldErr formats "kernel requirement <cid>: <field>: <reason>".
func (q *Requirement) fieldErr(field, reason string) error {
	return q.fieldWrap(field, errors.New(reason))
}

// fieldWrap keeps err in the chain so callers can test sentinels with errors.Is.
func (q *Requirement) fieldWrap(field string, err error) error {
	if q.CorrelationID == "" {
		return fmt.Errorf("kernel requirement: %s: %w", field, err)
	}
	return fmt.Errorf("kernel requirement %s: %s: %w", q.CorrelationID, field, err)
}

func (q *Requirement) validateArchitectures() error {
	if n := len(q.Architectures); n == 0 || n > MaxArchitectures {
		return q.fieldErr("architectures", fmt.Sprintf("must list 1..%d entries", MaxArchitectures))
	}
	seen := make(map[string]struct{}, len(q.Architectures))
	for i, a := range q.Architectures {
		field := fmt.Sprintf("architectures[%d]", i)
		if !boundedToken(a, maxArchitectureLen, architectureRegex) {
			return q.fieldErr(field, "must be a lowercase token such as x86-64")
		}
		if _, dup := seen[a]; dup {
			return q.fieldErr(field, "duplicate architecture "+a)
		}
		seen[a] = struct{}{}
	}
	return nil
}

func (q *Requirement) validateABI() error {
	if !boundedToken(q.ABI.MinimumRelease, maxReleaseTokenLen, dottedReleaseRegex) {
		return q.fieldErr("abi.minimum-release", "must be a dotted numeric release such as 6.12")
	}
	if q.ABI.TargetRelease != "" && !boundedToken(q.ABI.TargetRelease, maxReleaseTokenLen, releaseTokenRegex) {
		return q.fieldErr("abi.target-release", "must be a bounded release token")
	}
	if q.ABI.ModuleABI != "" && !boundedToken(q.ABI.ModuleABI, maxReleaseTokenLen, releaseTokenRegex) {
		return q.fieldErr("abi.module-abi", "must be a bounded module ABI token")
	}
	return nil
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
	if f.State != StateBuiltIn && f.State != StateModule {
		return q.fieldErr(field("state"), fmt.Sprintf("must be %s or %s", StateBuiltIn, StateModule))
	}
	if !knownProbe(f.Probe) {
		return q.fieldErr(field("probe"), fmt.Sprintf("unknown probe %q", f.Probe))
	}
	if !boundedToken(f.RequiredBy, maxRequiredByLen, requiredByRegex) {
		return q.fieldErr(field("required-by"), "must be a bounded requirement id")
	}
	return nil
}

// knownProbe checks the probe against the KnownProbes allow-list.
func knownProbe(probe string) bool {
	for _, p := range KnownProbes {
		if p == probe {
			return true
		}
	}
	return false
}
