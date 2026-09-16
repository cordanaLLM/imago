// Copyright 2026 Lusoris
package aegis

import (
	"encoding/json"
	"fmt"
	"slices"
	"time"
)

// BuildRequest is the imago-side projection of an accepted product input. It
// is deliberately not pkg/builder.Request: that type dispatches Packer flavors
// and has no mkosi/UKI flavor. The executor binding for this request is the
// next planning step (ADR-0020).
type BuildRequest struct {
	CorrelationID string          `json:"correlation_id"`
	Revision      string          `json:"revision"`
	Distribution  Distribution    `json:"distribution"`
	Definitions   DefinitionPaths `json:"definitions"`
	Packages      []string        `json:"packages"`
	KernelSource  string          `json:"kernel_source"`
	KernelPackage string          `json:"kernel_package"`
	Retry         RetryPolicy     `json:"retry"`
}

// DefinitionPaths carries the four validated definition paths.
type DefinitionPaths struct {
	Repart            string `json:"repart"`
	Sysupdate         string `json:"sysupdate"`
	Mkosi             string `json:"mkosi"`
	KernelRequirement string `json:"kernel_requirement"`
}

// RetryPolicy is the bounded retry budget of a request.
type RetryPolicy struct {
	// Attempts is 1..MaxRetryAttempts.
	Attempts int
	// Backoff is 0..MaxBackoffSeconds seconds between attempts.
	Backoff time.Duration
}

// MarshalJSON renders the backoff in its duration form ("30s") instead of nanoseconds.
func (r RetryPolicy) MarshalJSON() ([]byte, error) {
	return json.Marshal(struct {
		Attempts int    `json:"attempts"`
		Backoff  string `json:"backoff"`
	}{Attempts: r.Attempts, Backoff: r.Backoff.String()})
}

// BuildRequest validates the manifest and maps it to the imago-side request.
// The packages slice is copied so the request does not alias the manifest.
func (p *ProductInput) BuildRequest() (BuildRequest, error) {
	if err := p.Validate(); err != nil {
		return BuildRequest{}, err
	}
	return BuildRequest{
		CorrelationID: p.CorrelationID,
		Revision:      p.Revision,
		Distribution:  p.Distribution,
		Definitions: DefinitionPaths{
			Repart:            p.Definitions.Repart,
			Sysupdate:         p.Definitions.Sysupdate,
			Mkosi:             p.Definitions.Mkosi,
			KernelRequirement: p.Definitions.KernelRequirement,
		},
		Packages:      slices.Clone(p.Packages),
		KernelSource:  p.Kernel.Source,
		KernelPackage: p.Kernel.DefaultPackage,
		Retry: RetryPolicy{
			Attempts: p.Retries.MaxAttempts,
			Backoff:  time.Duration(p.Retries.BackoffSeconds) * time.Second,
		},
	}, nil
}

// ResultSchema identifies the result imago returns for an accepted product
// input. It is proposed to Aegis alongside the request/result pair (M09).
const ResultSchema = "imago.p01.product-result.v1"

// Result bounds.
const (
	// DigestPrefix is the algorithm prefix of ImageDigest.
	DigestPrefix = "sha256:"
	// DigestHexLen is the hex length of a SHA-256 digest.
	DigestHexLen = 64
	// MaxReferenceLen bounds the signature and boot-evidence references.
	MaxReferenceLen = 512
)

// Result is the recorded outcome imago returns to Aegis for one request: the
// output digest, the signature reference, and the boot evidence reference the
// stack contract requires. Nothing produces it yet; it pins the shape so the
// contract is symmetric.
type Result struct {
	Schema          string `json:"schema"`
	CorrelationID   string `json:"correlation-id"`
	ImageDigest     string `json:"image-digest"`
	SignatureRef    string `json:"signature-ref"`
	BootEvidenceRef string `json:"boot-evidence-ref"`
}

// Validate checks the result against its contract and returns a correlated *Error.
func (r *Result) Validate() error {
	cid := reportedCorrelationID(r.CorrelationID)
	switch {
	case r.Schema != ResultSchema:
		return &Error{CorrelationID: cid, Field: "schema", Reason: fmt.Sprintf("want %q", ResultSchema), Err: ErrSchema}
	case r.CorrelationID == "":
		return &Error{CorrelationID: cid, Field: "correlation-id", Reason: "required", Err: ErrMissingField}
	case cid == InvalidCorrelationID:
		return &Error{CorrelationID: cid, Field: "correlation-id", Reason: fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._-]", MaxCorrelationIDLen), Err: ErrInvalidField}
	case !isDigest(r.ImageDigest):
		return &Error{CorrelationID: cid, Field: "image-digest", Reason: fmt.Sprintf("must be %q followed by %d lowercase hex characters", DigestPrefix, DigestHexLen), Err: ErrInvalidField}
	}
	if err := validateReference(cid, "signature-ref", r.SignatureRef); err != nil {
		return err
	}
	return validateReference(cid, "boot-evidence-ref", r.BootEvidenceRef)
}

// isDigest reports whether s is DigestPrefix followed by DigestHexLen lowercase hex digits.
func isDigest(s string) bool {
	return len(s) == len(DigestPrefix)+DigestHexLen && s[:len(DigestPrefix)] == DigestPrefix && isLowerHex(s[len(DigestPrefix):], DigestHexLen)
}

// validateReference admits a non-empty locator of at most MaxReferenceLen bytes
// with no control character or backslash.
func validateReference(cid, field, value string) error {
	switch {
	case value == "":
		return &Error{CorrelationID: cid, Field: field, Reason: "required", Err: ErrMissingField}
	case len(value) > MaxReferenceLen:
		return &Error{CorrelationID: cid, Field: field, Reason: fmt.Sprintf("exceeds %d characters", MaxReferenceLen), Err: ErrOutOfBounds}
	case hasControlOrBackslash(value):
		return &Error{CorrelationID: cid, Field: field, Reason: "must contain no control characters or backslashes", Err: ErrInvalidField}
	}
	return nil
}
