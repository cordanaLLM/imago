// Copyright 2026 Lusoris
package aegis

import (
	"fmt"
	"slices"
	"strings"
)

// Character classes admitted beyond ASCII letters and digits. Validation walks
// bytes with these sets instead of regular expressions, so it is linear in the
// (already bounded) input length and has no backtracking hazard.
const (
	idExtra       = "._-"
	packageExtra  = "._+@-"
	snapshotExtra = "./_:-"
)

// Validate checks the manifest against the documented contract. The first
// violated rule is returned as an *Error; field order follows the manifest.
func (p *ProductInput) Validate() error {
	if err := p.validateIdentity(); err != nil {
		return err
	}
	if err := p.validateDistribution(); err != nil {
		return err
	}
	if err := p.validateDefinitions(); err != nil {
		return err
	}
	if err := p.validatePackages(); err != nil {
		return err
	}
	if err := p.validateKernel(); err != nil {
		return err
	}
	return p.validateRetries()
}

// reject builds the correlated error for one field.
func (p *ProductInput) reject(field, reason string, cause error) error {
	return &Error{CorrelationID: reportedCorrelationID(p.CorrelationID), Field: field, Reason: reason, Err: cause}
}

func (p *ProductInput) validateIdentity() error {
	if p.Schema != Schema {
		return p.reject("schema", fmt.Sprintf("want %q", Schema), ErrSchema)
	}
	if p.CorrelationID == "" {
		return p.reject("correlation-id", "required", ErrMissingField)
	}
	if !isToken(p.CorrelationID, MaxCorrelationIDLen, idExtra) {
		return p.reject("correlation-id", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._-]", MaxCorrelationIDLen), ErrInvalidField)
	}
	if !isLowerHex(p.Revision, RevisionLen) {
		return p.reject("revision", fmt.Sprintf("must be exactly %d lowercase hex characters", RevisionLen), ErrInvalidField)
	}
	return nil
}

func (p *ProductInput) validateDistribution() error {
	if !isToken(p.Distribution.ID, MaxTokenLen, idExtra) {
		return p.reject("distribution.id", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._-]", MaxTokenLen), ErrInvalidField)
	}
	if !isToken(p.Distribution.Snapshot, MaxTokenLen, snapshotExtra) {
		return p.reject("distribution.snapshot", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9./_:-]", MaxTokenLen), ErrInvalidField)
	}
	return nil
}

func (p *ProductInput) validateDefinitions() error {
	paths := [...]struct{ field, value string }{
		{"definitions.repart", p.Definitions.Repart},
		{"definitions.sysupdate", p.Definitions.Sysupdate},
		{"definitions.mkosi", p.Definitions.Mkosi},
		{"definitions.kernel-requirement", p.Definitions.KernelRequirement},
	}
	for _, d := range paths {
		if err := p.validatePath(d.field, d.value); err != nil {
			return err
		}
	}
	return nil
}

// validatePath admits a bounded, slash-separated relative path with no empty
// or parent segment, no leading slash, no backslash, and no control character.
func (p *ProductInput) validatePath(field, value string) error {
	switch {
	case value == "":
		return p.reject(field, "required", ErrMissingField)
	case len(value) > MaxPathLen:
		return p.reject(field, fmt.Sprintf("exceeds %d characters", MaxPathLen), ErrOutOfBounds)
	case value[0] == '/':
		return p.reject(field, "must be relative (no leading slash)", ErrInvalidField)
	case hasControlOrBackslash(value):
		return p.reject(field, "must use forward slashes and contain no control characters", ErrInvalidField)
	}
	// Bounded: at most MaxPathLen+1 segments.
	for _, seg := range strings.Split(value, "/") {
		if seg == "" || seg == ".." {
			return p.reject(field, "must not contain empty or parent (..) segments", ErrInvalidField)
		}
	}
	return nil
}

func (p *ProductInput) validatePackages() error {
	n := len(p.Packages)
	if n < 1 || n > MaxPackages {
		return p.reject("packages", fmt.Sprintf("count %d outside 1..%d", n, MaxPackages), ErrOutOfBounds)
	}
	seen := make(map[string]struct{}, n)
	for i, name := range p.Packages {
		field := fmt.Sprintf("packages[%d]", i)
		if !isPackageName(name) {
			return p.reject(field, fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._+@-] starting alphanumeric", MaxTokenLen), ErrInvalidField)
		}
		if _, dup := seen[name]; dup {
			return p.reject(field, "duplicate package "+name, ErrInvalidField)
		}
		seen[name] = struct{}{}
	}
	return nil
}

func (p *ProductInput) validateKernel() error {
	if !isToken(p.Kernel.Source, MaxTokenLen, idExtra) {
		return p.reject("kernel.source", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._-]", MaxTokenLen), ErrInvalidField)
	}
	if !isPackageName(p.Kernel.DefaultPackage) {
		return p.reject("kernel.default-package", fmt.Sprintf("must be 1..%d characters of [A-Za-z0-9._+@-] starting alphanumeric", MaxTokenLen), ErrInvalidField)
	}
	if !slices.Contains(p.Packages, p.Kernel.DefaultPackage) {
		return p.reject("kernel.default-package", "must be one of packages", ErrInvalidField)
	}
	return nil
}

func (p *ProductInput) validateRetries() error {
	if a := p.Retries.MaxAttempts; a < 1 || a > MaxRetryAttempts {
		return p.reject("retries.max-attempts", fmt.Sprintf("%d outside 1..%d", a, MaxRetryAttempts), ErrOutOfBounds)
	}
	if b := p.Retries.BackoffSeconds; b < 0 || b > MaxBackoffSeconds {
		return p.reject("retries.backoff-seconds", fmt.Sprintf("%d outside 0..%d", b, MaxBackoffSeconds), ErrOutOfBounds)
	}
	return nil
}

// isAlnum reports whether c is an ASCII letter or digit.
func isAlnum(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
}

// isToken reports whether s is 1..limit bytes, each alphanumeric or in extra.
func isToken(s string, limit int, extra string) bool {
	if s == "" || len(s) > limit {
		return false
	}
	for i := 0; i < len(s); i++ {
		if !isAlnum(s[i]) && strings.IndexByte(extra, s[i]) < 0 {
			return false
		}
	}
	return true
}

// isPackageName admits a distribution package name: a bounded token that
// starts alphanumeric and continues with [A-Za-z0-9._+@-].
func isPackageName(s string) bool {
	return isToken(s, MaxTokenLen, packageExtra) && isAlnum(s[0])
}

// isLowerHex reports whether s is exactly n lowercase hexadecimal digits.
func isLowerHex(s string, n int) bool {
	if len(s) != n {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'f') {
			return false
		}
	}
	return true
}

// hasControlOrBackslash reports whether s contains an ASCII control byte
// (including DEL) or a backslash.
func hasControlOrBackslash(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] < 0x20 || s[i] == 0x7f || s[i] == '\\' {
			return true
		}
	}
	return false
}
